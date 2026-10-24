import json
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest
import pandas as pd
from retail_forecast.monitoring import replay,synthetic_inputs,week_close,Ledger,validate_delivery

RULES=json.loads((Path(__file__).parents[1]/'monitoring_rules.json').read_text())

class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def run_scenario(self,scenario,as_of=None):
        deliveries,forecasts,refs=synthetic_inputs(scenario)
        return replay(deliveries,forecasts,RULES,self.root/scenario,scenario,'synthetic',refs,as_of=as_of)

    def test_no_errors_before_week_close_and_availability(self):
        early=self.run_scenario('late_data','2024-01-14T12:00:00Z')
        self.assertEqual(early['scored_weeks'],0)
        final=self.run_scenario('late_data')
        scores=pd.read_csv(self.root/'late_data/scores.csv')
        self.assertTrue(final['event_counts']['late_data']>0)
        self.assertTrue(final['event_counts']['missing_data']>0)
        for r in scores.itertuples():
            self.assertGreaterEqual(pd.Timestamp(r.scored_at),week_close(r.target_week))
            self.assertGreaterEqual(pd.Timestamp(r.scored_at),pd.Timestamp(r.actual_available_at))
        late=scores[scores.target_week.eq('2024-01-22')].iloc[0]
        self.assertEqual(pd.Timestamp(late.scored_at),pd.Timestamp('2024-01-31T00:00:00Z'))
        with self.assertRaises(ValueError):self.run_scenario('late_data','2024-01-14T12:00:00Z')

    def test_idempotency_and_conflicting_forecast(self):
        a=self.run_scenario('clean');b=self.run_scenario('clean')
        self.assertEqual(a,b)
        with closing(sqlite3.connect(self.root/'clean/ledger.sqlite')) as db:
            count=db.execute("SELECT COUNT(*) FROM entries WHERE kind='forecast'").fetchone()[0]
        self.assertEqual(count,140)
        ledger=Ledger(self.root/'test.sqlite')
        ledger.put('s','forecast','w:p',{'prediction':1})
        self.assertFalse(ledger.put('s','forecast','w:p',{'prediction':1}))
        with self.assertRaises(ValueError):ledger.put('s','forecast','w:p',{'prediction':2})
        ledger.finish(True)

    def test_incidents_and_recovery(self):
        for scenario,signal in [('missing_columns','schema_failure'),('dropped_products','dropped_product_records'),
                                ('sales_shift','sales_distribution_signal'),('invalid_quantity','data_quality_failure'),
                                ('activity_shift','product_activity_signal')]:
            with self.subTest(scenario=scenario):
                result=self.run_scenario(scenario)
                self.assertGreater(result['event_counts'][signal],0)
                self.assertEqual(result['kind'],'synthetic')
        score=pd.read_csv(self.root/'sales_shift/scores.csv')
        shifted=score[score.target_week.eq('2024-01-22')].iloc[0]
        self.assertEqual(shifted.mae,200)
        self.assertEqual(shifted.coverage_95,0)
        self.assertEqual(self.run_scenario('missing_columns')['forecasts'],120)

    def test_invalid_delivery_is_not_zero_imputed(self):
        deliveries,_,_=synthetic_inputs('clean')
        f=deliveries[0]['frame'].copy();f.loc[0,'observed_units']=float('nan')
        self.assertEqual(validate_delivery(f,'2024-01-01')[0],'data_quality_failure')
