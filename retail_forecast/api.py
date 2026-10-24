"""Read-only local application API. No fitting or inference in request handlers."""
from datetime import date, datetime
from enum import Enum
from functools import lru_cache
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Literal
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)
Units = Annotated[float, Field(ge=0, allow_inf_nan=False)]

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Mode(str, Enum):
    historical = 'historical'
    dataset_edge = 'dataset_edge'
    beyond_dataset = 'beyond_dataset'

class History(Contract):
    week: date
    units: Units | None
    status: Literal['observed','partial_week','missing_observation']

class Baselines(Contract):
    last_observed_week: Units
    trailing_average: Units
    seasonal_naive: Units

class Forecast(Contract):
    product_id: str
    mode: Literal['historical','dataset_edge']
    target_week: date
    issue_time: datetime
    target_end_exclusive: date
    prediction: Units
    actual: Units | None
    lower_80: Units
    upper_80: Units
    lower_95: Units
    upper_95: Units
    baselines: Baselines
    seasonal_fallback: bool
    model_version: str
    data_version: str
    training_cutoff_exclusive: date

    @model_validator(mode='after')
    def coherent(self):
        if not self.lower_95 <= self.lower_80 <= self.prediction <= self.upper_80 <= self.upper_95:
            raise ValueError('Invalid interval order')
        if self.issue_time.tzinfo is None or self.issue_time.date() != self.target_week or self.target_week.weekday() != 0:
            raise ValueError('Invalid forecast clock')
        if self.training_cutoff_exclusive > self.target_week:
            raise ValueError('Training cutoff exceeds origin')
        if self.mode == 'dataset_edge' and self.actual is not None:
            raise ValueError('Incomplete dataset-edge targets cannot be scored')
        return self

class Meta(Contract):
    schema_version: Literal[1]
    built_at: datetime
    coverage_start: date
    coverage_end: date
    edge_week: date
    beyond_week: date
    data_version: str
    freeze_version: str
    quality: dict
    product_count: int
    historical_weeks: list[date]
    disclaimer: str

class ProductList(Contract):
    products: list[str]
    total: int
    limit: int

class ProductHistory(Contract):
    product_id: str
    history: list[History]

class ForecastResult(Contract):
    status: Literal['available','unavailable']
    reason: str | None = None
    forecast: Forecast | None = None

class Monitoring(Contract):
    simulation: Literal[True] = True
    summary: dict
    events: list[dict]
    scores: list[dict]
    availability_assumption: str = 'Assumed at local Monday close; actual delivery times are unknown.'

class Store:
    def __init__(self, path):
        self.path = Path(path)

    @lru_cache(maxsize=1)
    def load(self):
        try:
            manifest = json.loads(self.path.with_name('manifest.json').read_text())
            raw = self.path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest['bundle_sha256']:
                raise ValueError('Bundle hash differs from manifest')
            data = json.loads(raw)
            forecasts = [Forecast.model_validate(r) for r in data['forecasts']]
            history = {p:[History.model_validate(r) for r in rows] for p,rows in data['history'].items()}
            index = {(f.product_id,f.mode,f.target_week.isoformat()):f for f in forecasts}
            if len(index) != len(forecasts):
                raise ValueError('Duplicate forecast key')
            if any(f.data_version != data['data_version'] for f in forecasts):
                raise ValueError('Forecast data version mismatch')
            meta = Meta(**{k:data[k] for k in ('schema_version','built_at','coverage_start','coverage_end','edge_week','beyond_week','data_version','freeze_version','quality')},
                product_count=len(history), historical_weeks=sorted({f.target_week for f in forecasts if f.mode=='historical'}),
                disclaimer='Historical UCI observed sales, not live retail activity. Intervals are estimates; no inventory or demand inference.')
            monitor = Monitoring(**data['monitoring'])
            return meta, history, index, monitor
        except (OSError, ValueError, KeyError, TypeError) as exc:
            LOG.error('Application bundle unavailable: %s', exc)
            raise HTTPException(503, 'Application artifacts are missing or invalid. From the project directory run .venv/bin/python scripts/build_app_bundle.py, then restart the API. See README prerequisites.') from exc


def create_app(bundle_path=None):
    app = FastAPI(title='Retail Forecast', version='1.0.0', description='Historical observed-sales explorer. Read-only saved artifacts; no training on requests.')
    store = Store(bundle_path or os.environ.get('RETAIL_APP_BUNDLE', ROOT/'artifacts/uci/application/bundle.json'))
    app.state.store = store

    @app.get('/health', response_model=dict[str,str])
    def health():
        return {'status':'running'}

    @app.get('/meta', response_model=Meta)
    def meta():
        return store.load()[0]

    @app.get('/products', response_model=ProductList)
    def products(q: str = Query('', max_length=80), limit: int = Query(50, ge=1, le=200)):
        # Literal substring search only; input is never SQL, regex or a file path.
        matches = [p for p in sorted(store.load()[1]) if q.strip().casefold() in p.casefold()]
        return ProductList(products=matches[:limit],total=len(matches),limit=limit)

    def check_product(product_id):
        if product_id not in store.load()[1]:
            raise HTTPException(404,'Unknown product ID. Search /products for available IDs.')

    ProductID = Annotated[str, Query(min_length=1,max_length=40,pattern=r'^[A-Za-z0-9 -]+$')]

    @app.get('/history', response_model=ProductHistory)
    def history(product_id: ProductID, limit: int = Query(104,ge=1,le=200)):
        check_product(product_id)
        return ProductHistory(product_id=product_id,history=store.load()[1][product_id][-limit:])

    @app.get('/forecast', response_model=ForecastResult)
    def forecast(product_id: ProductID, mode: Mode = Mode.dataset_edge, target_week: date | None = None):
        check_product(product_id)
        meta, _, index, _ = store.load()
        if target_week and target_week.weekday() != 0:
            raise HTTPException(422,'target_week must be a Monday date.')
        if mode == Mode.beyond_dataset:
            return ForecastResult(status='unavailable',reason=f'Forecasts from {meta.beyond_week} are withheld: the prior week is incomplete and no subsequent observations exist. This historical dataset cannot support a current retail forecast.')
        if mode == Mode.dataset_edge:
            if target_week and target_week != meta.edge_week:
                raise HTTPException(422,'Dataset-edge mode supports only the saved edge week.')
            week = meta.edge_week
        else:
            if not meta.historical_weeks:
                return ForecastResult(status='unavailable', reason='No historical evaluation folds are present in this bundle.')
            week = target_week or meta.historical_weeks[-1]
            if week not in meta.historical_weeks:
                raise HTTPException(404,'No historical evaluation for this target week.')
        result = index.get((product_id,mode.value,week.isoformat()))
        if result is None:
            return ForecastResult(status='unavailable',reason='No saved forecast for this product/origin. Four consecutive observed prior weeks are required; new or short histories may be excluded.')
        return ForecastResult(status='available',forecast=result)

    @app.get('/monitoring', response_model=Monitoring)
    def monitoring():
        return store.load()[3]

    return app

app = create_app()
