# Reproduction and artifact setup

Run commands from the project root. Use Python 3.14 for the supplied snapshots. The frozen numerical dependencies were tested on Python 3.14.0/macOS arm64; other platforms must be verified, not assumed bit-identical. Package installation needs network access. Once dependencies are installed, fixture tests need neither network nor UCI data.

## 1. Create isolated environments

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -c requirements-lock.txt -e .
python3 -m venv .venv-app
.venv-app/bin/python -m pip install -c requirements-app-lock.txt -r requirements-app.txt
.venv/bin/python -m pip check
.venv-app/bin/python -m pip check
.venv/bin/python -W error -m unittest discover -s tests -v
.venv-app/bin/python -W error -m unittest discover -s app_tests -v
```

The foundation suite performs a complete synthetic prepare → backtest-smoke → train → forecast run in a temporary directory and checks known results. Tree tests fit small fictional examples and verify reload and temporal invariance. API tests construct their own fictional bundle. These are software tests, not accuracy benchmarks.

## 2. Raw source → audited weekly data

```sh
.venv/bin/retail-forecast download --raw-dir data/raw
.venv/bin/retail-forecast import-uci --raw-dir data/raw
.venv/bin/retail-forecast --config config.uci.toml prepare \
  --input data/raw/transactions.csv \
  --coverage-start 2009-12-01 --coverage-end 2011-12-09 \
  --assume-complete --min-history-weeks 4
.venv/bin/python scripts/verify_uci.py
```

Both source sheets are used. The first official download is about 45.6 MB compressed; workbook parsing, normalized transactions, row audits and generated artifacts need substantially more disk space. The extraction assumption is essential: without it full-week absence remains unknown. Raw data, audits and normalized customer-level rows stay ignored. Preserve source.json and quality.json with local artifacts.

## 3. Development backtesting and training

```sh
.venv/bin/retail-forecast --config config.uci.toml backtest --protocol evaluation_protocol.json
.venv/bin/python scripts/verify_development.py
.venv/bin/retail-forecast --config config.uci.toml tree-backtest --protocol evaluation_protocol.json
.venv/bin/python scripts/verify_tree.py
.venv/bin/retail-forecast --config config.uci.toml tree-forecast --issue-week 2011-08-29
```

The last command reloads the saved development model. It intentionally cannot forecast the reserved-final range through this older command. Application forecasts are exported in step 5. `train` and `forecast` without the `tree-` prefix are foundation last-week persistence utilities, not the selected global tree.

## 4. Reproduce the already-published frozen final procedure

**The holdout is already exposed.** A fresh checkout may reproduce the recorded procedure, but this does not create a new untouched test. The committed `final_freeze.json` and `interval_calibration.json` preserve the original declaration, dates and quantiles. Do not regenerate or overwrite them for reproduction. Never delete an existing final directory to bypass the one-time guard.

On a fresh checkout with **no** `artifacts/uci/final` directory:

```sh
.venv/bin/retail-forecast --config config.uci.toml evaluate-final --freeze final_freeze.json
.venv/bin/python scripts/verify_final.py
.venv/bin/python scripts/plot_final.py
```

If final artifacts already exist, run **only verification**, not evaluate-final. The evaluator checks numerical dependencies, code/data/calibration hashes and refuses an existing output directory. A changed environment or method needs separate exploratory versioning, never relabeling as the original final test. Runtime and wall-clock metadata will vary between reproductions. Calibration regeneration would require the original development residuals and constitutes a separate provenance exercise; it is not necessary to reproduce inference from the committed quantiles.

## 5. Monitoring → saved application model and bundle

```sh
.venv/bin/retail-forecast --config config.uci.toml monitor-replay --scenario real
for scenario in clean missing_columns dropped_products sales_shift late_data invalid_quantity activity_shift; do
  .venv/bin/retail-forecast --config config.uci.toml monitor-replay --scenario "$scenario"
done
.venv/bin/python scripts/verify_monitoring.py
.venv/bin/python scripts/build_app_bundle.py
.venv/bin/python scripts/verify_application.py
```

The bundle builder is an explicit offline refit/export using the frozen selected configuration. It saves a separate model trained strictly before 2011-12-05, not a new benchmark, plus the archived final predictions. It does not update frozen evaluation outputs. It generates `artifacts/uci/application/bundle.json` (~59 MiB) and `manifest.json`; the manifest's hash must match. Model binaries and raw transactions are unnecessary for serving these JSON files.

Optional local tracking:

```sh
python3 -m venv .venv-tracking
.venv-tracking/bin/python -m pip install -c requirements-tracking-lock.txt -r requirements-tracking.txt
.venv/bin/retail-forecast --config config.uci.toml track-evaluations
.venv/bin/retail-forecast --config config.uci.toml monitor-replay --scenario real --track
```

See [MONITORING.md](MONITORING.md) for separate synthetic runs, versioned run imports, retry behavior and a scheduling example. No recurring job is installed.

## 6. Native application or Docker

Native: start the two commands from README in separate terminals. Read-only smoke check:

```sh
.venv-app/bin/python scripts/smoke_application.py
```

Docker uses the same saved bundle; it does not download UCI data, fit models or include raw data in its image. After step 5:

```sh
cp .env.example .env  # optional; inspect before changing local settings
# Stop native services on 8000/8501 first, or use alternate ports as below.
docker compose config --quiet
RETAIL_API_PORT=8001 RETAIL_DASHBOARD_PORT=8502 docker compose up --build -d --wait
.venv-app/bin/python scripts/smoke_application.py --api http://127.0.0.1:8001 --dashboard http://127.0.0.1:8502
RETAIL_API_PORT=8001 RETAIL_DASHBOARD_PORT=8502 docker compose down
```

`RETAIL_ARTIFACT_DIR` is a host directory containing bundle.json and manifest.json; it is mounted read-only in the API container. No auto-created empty mount directory hides missing setup. Missing/invalid artifacts keep readiness unhealthy and prevent the dashboard dependency from becoming ready. The image runs as a non-root user with a read-only root filesystem, a temporary /tmp and dropped capabilities. Only localhost ports are published. The dashboard calls `http://api:8000` inside Compose; never point it at its own localhost for the API. Streamlit telemetry is disabled.

The Docker context is allowlisted and contains application source/configuration and dependency pins only. Rebuild images to update code; restart services to update a mounted bundle. No external authentication, TLS, reverse proxy or production load validation is provided. Image base tags and upstream package availability may change; validated local versions are recorded, not claimed to be a bit-for-bit reproducible image.

## CI placement

`.github/workflows/ci.yml` runs fixture-only core and application jobs on Python 3.14/Ubuntu, with read-only repository permissions and 15-minute timeouts. It installs pinned dependencies but never downloads UCI data, trains on real data, opens the holdout, starts MLflow or needs secrets.

Project 3 has its own standalone repository, with this workflow at the repository root. The enclosing workspace and other projects are unchanged. Hosted execution status and local equivalents are recorded in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
