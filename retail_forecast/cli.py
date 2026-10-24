"""Command line boundary: validation, logging, and actionable failures."""
import argparse
from datetime import date
import json
import logging
from pathlib import Path
import tomllib
from zipfile import BadZipFile

from .config import load_config

LOG = logging.getLogger('retail_forecast')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description='One-week-ahead observed-sales forecasts')
    parser.add_argument('--config', type=Path, default=Path('config.toml'))
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO')
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Clean transactions and build weekly series')
    prepare.add_argument('--input', type=Path, required=True)
    prepare.add_argument('--coverage-start', type=date.fromisoformat, required=True)
    prepare.add_argument('--coverage-end', type=date.fromisoformat, required=True)
    prepare.add_argument('--missing-day', type=date.fromisoformat, action='append', default=[])
    prepare.add_argument('--assume-complete', action='store_true', help='Assume complete extraction inside coverage; enables zero-sales weeks')
    prepare.add_argument('--min-history-weeks', type=int, default=4)
    for name in ('download', 'import-uci'):
        command = commands.add_parser(name, help='Official UCI download or two-sheet normalization')
        command.add_argument('--raw-dir', type=Path, default=Path('data/raw'))
    evaluation = commands.add_parser('backtest', help='Run frozen development folds only')
    evaluation.add_argument('--protocol', type=Path, default=Path('evaluation_protocol.json'))
    commands.add_parser('backtest-smoke', help='Legacy synthetic-only one-prior-week smoke check')
    for name in ('train', 'forecast'):
        command = commands.add_parser(name, help=f'{name.capitalize()} last-week baseline state')
        command.add_argument('--issue-week', type=date.fromisoformat, required=True)
    tree = commands.add_parser('tree-backtest', help='Bounded tree tuning on development folds only')
    tree.add_argument('--protocol', type=Path, default=Path('evaluation_protocol.json'))
    tree_forecast = commands.add_parser('tree-forecast', help='Reload selected local tree for development replay')
    tree_forecast.add_argument('--issue-week', type=date.fromisoformat, required=True)
    for name in ('freeze-final', 'evaluate-final'):
        command = commands.add_parser(name, help='Freeze or execute the final chronological procedure')
        command.add_argument('--freeze', type=Path, default=Path('final_freeze.json'))
        command.add_argument('--protocol', type=Path, default=Path('evaluation_protocol.json'))
    commands.add_parser('track-evaluations',help='Register saved versioned evaluations in local MLflow')
    replay = commands.add_parser('monitor-replay',help='Simulated historical monitoring; no installed schedule')
    replay.add_argument('--scenario',default='real',choices=['real','clean','missing_columns','dropped_products','sales_shift','late_data','invalid_quantity','activity_shift'])
    replay.add_argument('--rules',type=Path,default=Path('monitoring_rules.json'))
    replay.add_argument('--as-of',help='Optional timezone-aware simulation clock cutoff')
    replay.add_argument('--track',action='store_true',help='Register this replay in local MLflow')
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format='%(levelname)s %(name)s: %(message)s')
    try:
        config = load_config(args.config)
        from .baseline import backtest, forecast, read_weekly, train
        from .pipeline import build_weekly, save_prepared
        import pandas as pd
        weekly = config.data_dir / 'weekly.csv'
        model = config.model_dir / 'last_week.json'
        if args.command in ('download', 'import-uci'):
            from .source import download, import_workbook
            manifest = download(args.raw_dir) if args.command == 'download' else import_workbook(args.raw_dir)
            LOG.info('Source provenance saved in %s/source.json', args.raw_dir)
            return 0
        if args.command == 'track-evaluations':
            from .tracking_export import track_evaluations
            LOG.info('Local MLflow runs: %s',track_evaluations(config.artifact_dir))
        elif args.command == 'monitor-replay':
            from .monitoring import replay,real_inputs,synthetic_inputs
            rules=json.loads(args.rules.read_text())
            kind='real' if args.scenario=='real' else 'synthetic'
            source=real_inputs(weekly,config.artifact_dir/'final/predictions.csv',Path('final_freeze.json')) if kind=='real' else synthetic_inputs(args.scenario)
            output=config.artifact_dir/'monitoring'/kind/args.scenario
            summary=replay(*source[:2],rules,output,f'{kind}-{args.scenario}-v1',kind,source[2],as_of=args.as_of)
            if args.track:
                from .tracking_export import log_bundle
                log_bundle('monitor-'+args.scenario,kind,{'rules':rules,'source_versions':source[2],'simulation':True},summary,
                           [output/name for name in ('manifest.json','summary.json','forecasts.csv','scores.csv','events.jsonl')],output/'tracking_request.json')
            LOG.info('Simulated monitoring complete: %s',summary)
        elif args.command == 'freeze-final':
            from .final_evaluation import freeze
            freeze(weekly,args.protocol,config.artifact_dir / 'tree',args.freeze)
        elif args.command == 'evaluate-final':
            from .final_evaluation import execute
            execute(weekly,args.freeze,config.artifact_dir / 'final')
        elif args.command == 'tree-backtest':
            from .tree import run_tree
            run_tree(weekly, args.protocol, config.artifact_dir / 'tree', config.model_dir / 'tree.joblib', config.artifact_dir / 'development')
        elif args.command == 'tree-forecast':
            from .tree import forecast_saved
            predictions = forecast_saved(weekly, config.model_dir / 'tree.joblib', args.issue_week)
            config.artifact_dir.mkdir(parents=True, exist_ok=True)
            predictions.to_csv(config.artifact_dir / 'tree_forecast.csv', index=False)
        elif args.command == 'prepare':
            rows, report = build_weekly(args.input, args.coverage_start, args.coverage_end, args.missing_day,
                                        assume_complete=args.assume_complete, min_history_weeks=args.min_history_weeks,
                                        audit_path=config.data_dir / 'row_audit.csv')
            if not rows:
                raise ValueError('No accepted product rows; check schema, cleaning counts and coverage dates')
            config.data_dir.mkdir(parents=True, exist_ok=True)
            save_prepared(rows, report, config.data_dir)
            LOG.info('Prepared %s weekly rows at %s', len(rows), weekly)
        elif args.command == 'backtest':
            from .evaluation import run_development
            report = run_development(weekly, args.protocol, config.artifact_dir / 'development')
            LOG.info('Development evaluation saved at %s; holdout not evaluated', config.artifact_dir / 'development')
        elif args.command == 'backtest-smoke':
            if len(read_weekly(weekly)) > 1000:
                raise ValueError('Smoke backtest limited to small fixtures; use backtest with a frozen protocol')
            pairs, report = backtest(read_weekly(weekly))
            write_json(config.artifact_dir / 'backtest.json', report)
            pairs.to_csv(config.artifact_dir / 'backtest_predictions.csv', index=False)
            LOG.info('Evaluated %s eligible rows; results at %s', len(pairs), config.artifact_dir)
        elif args.command == 'train':
            state = train(read_weekly(weekly), args.issue_week, config, weekly)
            write_json(model, state)
            LOG.info('Saved last-week baseline for %s products at %s', len(state['predictions']), model)
        else:
            if args.issue_week.weekday() != 0:
                raise ValueError('--issue-week must be a Monday')
            predictions = forecast(model, args.issue_week.isoformat(), config)
            config.artifact_dir.mkdir(parents=True, exist_ok=True)
            predictions.to_csv(config.artifact_dir / 'forecast.csv', index=False)
            LOG.info('Forecast saved at %s', config.artifact_dir / 'forecast.csv')
        return 0
    except (OSError, ValueError, tomllib.TOMLDecodeError, BadZipFile) as exc:
        LOG.error('%s. Check --config and input paths; use --help for command options.', exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
