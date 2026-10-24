"""Small, strict configuration contract; paths are relative to the TOML file."""
from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Config:
    data_dir: Path
    artifact_dir: Path
    model_dir: Path
    horizon_weeks: int = 1
    random_seed: int = 42
    timezone: str = 'Europe/London'


def load_config(path: Path) -> Config:
    path = path.resolve()
    with path.open('rb') as stream:
        values = tomllib.load(stream)
    allowed = set(Config.__dataclass_fields__)
    if unknown := set(values) - allowed:
        raise ValueError(f'Unknown configuration keys: {sorted(unknown)}')
    for key, default in [('horizon_weeks', 1), ('random_seed', 42)]:
        value = values.get(key, default)
        if type(value) is not int or not 0 <= value <= 2**32 - 1:
            raise ValueError(f'{key} must be an integer between 0 and 4294967295')
    if values.get('horizon_weeks', 1) != 1:
        raise ValueError('horizon_weeks must be 1; multi-week forecasts are not supported')
    if values.get('timezone', 'Europe/London') != 'Europe/London':
        raise ValueError('timezone must be Europe/London for this source-local contract')
    for key, default in [('data_dir', 'data/processed'), ('artifact_dir', 'artifacts'), ('model_dir', 'models')]:
        value = values.get(key, default)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{key} must be a nonempty path string')
        values[key] = (path.parent / value).resolve()
    return Config(**values)
