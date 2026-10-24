# Simulated historical monitoring and local tracking

This workflow replays archived forecasts and weekly data deliveries in chronological order. It is **simulated historical monitoring**, not a live deployment, a new backtest, or evidence of real delivery incidents. The final holdout has already been evaluated. Its frozen predictions and interval parameters are reused without tuning or refitting.

## Reproduce

From the project directory, after the core setup and saved evaluations described in README:

```sh
python3 -m venv .venv-tracking
.venv-tracking/bin/python -m pip install -c requirements-tracking-lock.txt -r requirements-tracking.txt
.venv-tracking/bin/python -m pip check
.venv/bin/retail-forecast --config config.uci.toml track-evaluations
.venv/bin/retail-forecast --config config.uci.toml monitor-replay --scenario real --track
for scenario in clean missing_columns dropped_products sales_shift late_data invalid_quantity activity_shift; do
  .venv/bin/retail-forecast --config config.uci.toml monitor-replay --scenario "$scenario" --track
done
.venv/bin/python scripts/verify_monitoring.py
.venv/bin/python -W error -m unittest discover -s tests -v
```

MLflow 3.17.2 runs in its own environment so installing tracking does not alter the frozen forecasting dependencies. Tested pins describe this laptop, not a cross-platform lock. Tracking is optional for replay: omit `--track` for offline core-only execution. SQLite metadata and copied artifacts live under ignored `.tracking/`; no remote tracking service is used. To view locally, start this foreground process manually and stop it with Ctrl-C:

```sh
MLFLOW_ENABLE_TELEMETRY=false .venv-tracking/bin/mlflow ui \
  --backend-store-uri "sqlite:///$(pwd)/.tracking/mlflow.db" \
  --host 127.0.0.1 --port 5000
```

Saved development, tree and final evaluations are imported as runs explicitly labeled as saved-result imports, not new training runs. Parameters include evaluation configuration/hash, weekly data hash and training-cutoff policy; artifacts include exact configuration, metrics, predictions, dependency snapshot, fold/runtime records and the saved development tree model where applicable. Final runs include the freeze and interval calibration. Monitor runs include source references, rules and code hashes, ledger exports and summaries. Every artifact is hash-checked before logging. Request fingerprints and a serialized local registration database reuse completed runs on retries. Separate `retail-forecast-real` and `retail-forecast-synthetic` experiments prevent fictional results being confused with UCI findings.

## Replay contract

Weeks use Europe/London local Monday boundaries, with timezone-aware UTC event times, including DST. The dataset does not contain actual ingestion timestamps. For the real replay, each complete weekly extract is **assumed** available exactly at the following Monday boundary. Arrivals are processed before forecasts at the same instant. Scores are computed only after target-week closure and receipt of valid observations. Missing or invalid prior-week data withholds that origin's archived forecast; later repair does not backdate a forecast. Repair can unlock scoring of an already-issued forecast.

The monitored input is the prepared weekly product feed, not raw transaction rows. Required columns, unique product/week records, valid identifiers, exact week labels, observed status and finite nonnegative integer units are checked. A decrease in previously present product records quarantines the batch under an explicit complete-panel contract. This rule would need a versioned retirement policy for a production catalog. Unknown observations are never silently turned into zero sales. Actual revisions require a new versioned stream rather than overwriting history.

Each persisted forecast has issue time, target week/end, model version, data version, previous delivery hash, training cutoff and interval bounds. Real logical model versions combine the freeze hash and rolling origin; they are not hashes of separately saved per-origin model binaries. The whole-corpus data hash identifies the evaluated dataset, while the delivery hash identifies the historical input snapshot. Future corpus identifiers are provenance only, not model features or scoring inputs.

SQLite is the authoritative ledger. `(stream, kind, key)` uniqueness and an immediate transaction serialize writes; forecast keys use target week/product, so a changed model/data payload cannot silently create another forecast for that key. Identical reruns are no-ops; conflicting payloads fail. CSV/JSON exports are rebuilt on rerun and are not the transactional source of truth. An `--as-of` timezone-aware timestamp supports forward incremental replay; a completed stream cannot be rewound. Use a separately versioned stream/output for changed rules or source data; the CLI's supplied scenarios have fixed v1 stream names.

## Rules and interpretation

`monitoring_rules.json` declares explicit illustrative operational rules, not thresholds optimized on final results: missing expected products tolerance zero; delivery overdue after 24 hours; smoothed weekly mean-sales ratio outside 0.5–2; active-product fraction change at least 0.20; WAPE above 1; and weighted 95% interval coverage below 0.85 over the last four scored weeks with at least 20 rows. WAPE is pooled absolute error divided by pooled actual units; zero denominators remain undefined. Sales and activity changes are investigation signals, not proof of model failure. There is no automatic retraining, notification, or claim of formal drift significance.

Outputs are `artifacts/uci/monitoring/real/real/` and `artifacts/uci/monitoring/synthetic/<scenario>/`, each containing a ledger, forecasts, weekly scores, events, manifest and summary. The real replay produced 59,395 forecasts and 13 scored weeks, matching frozen tree MAE 18.9451745693, aggregate WAPE 0.5971142372 and 95% interval coverage 0.9417964475. Under assumed complete/on-time deliveries, no operational threshold alert fired. This does not negate the segment undercoverage documented in FINAL_RESULTS.md.

All synthetic scenarios use 20 fictional products over eight weeks with fixed forecasts of 100; they do not use or benchmark UCI data. Clean replay yields 140 forecasts over seven target weeks. Missing columns, dropped product rows, invalid quantities and 48-hour late delivery each yield 120 forecasts, six scored weeks and one withheld origin. Invalid batches receive a valid repair after 48 hours. A single sales jump to 300 produces two distribution signals (jump and reversal) and four rolling coverage signals; the affected week has MAE 200 and zero 95% coverage. A zero-sales activity incident additionally triggers activity signals. These scenarios exercise monitoring and delivery gates; they do not simulate counterfactual model retraining.

## Scheduling example — not installed

The wrapper can be run manually:

```sh
./scripts/monitor_batch.sh --scenario real --track
```

For illustration only, this crontab line would repeat the historical batch at 07:00 Monday in the machine's scheduler timezone. It is not a live forecast service and repeated completed runs reuse records:

```cron
0 7 * * 1 /bin/sh '/Users/thilankathushan/Documents/ChatGPT/AI & ML Projects/03-retail-forecast/scripts/monitor_batch.sh' --scenario real --track >> '/Users/thilankathushan/Documents/ChatGPT/AI & ML Projects/03-retail-forecast/artifacts/monitor-batch.log' 2>&1
```

No recurring job or external notification has been configured. A real deployment would require measured arrival timestamps, an operational source, versioned catalog/actual-revision policies, and an actual forecast-generation job behind these gates.
