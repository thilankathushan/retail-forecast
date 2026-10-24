# Retail Forecast: implementation plan

**Objective:** Weekly observed-sales forecasting with monitoring.

**Proposed stack:** Python, pandas, SQL, scikit-learn, MLflow, FastAPI, Docker.

**Data:** UCI Online Retail II; verify license and document transaction cleaning.

## Foundation: package and command line

**Status:** Implemented 2026-10-23. Installable Python package, isolated environment, pandas/scikit-learn runtime snapshot, strict TOML settings, prepare/backtest/train/forecast commands, project-local ignore rules and offline tests. Training/forecasting currently use last-week persistence; this is not completion of the tree-model milestone.

## Milestone 1: Data pipeline

**Status:** Implemented and real-data verified on 2026-10-23. Official UCI acquisition, two-sheet workbook import, audited cleaning, separate negative-unit tracking and coverage/history flags are implemented. Forecast benchmarks remain pending. See DATA_CONTRACT.md and PROGRESS.md.

Validate schema; handle cancellations, returns, missing product IDs and incomplete weeks; create weekly series.

**Acceptance gate:** Fixtures exercise cleaning decisions; missing observations are distinguished from zero sales.

## Milestone 2: Backtesting baseline

**Status:** Implemented 2026-10-24: frozen expanding-window development/holdout dates, last-observed-week, trailing-average and seasonal-naive with explicit fallback, common origin-time eligibility, coverage audit and pooled/per-product metrics. Real development evaluation completed; final 13-week evaluation subsequently completed under the separately frozen procedure.

Implement last-week and seasonal-naive forecasts with chronological rolling-origin folds.

**Acceptance gate:** Document horizon, seasonal period, eligibility and MAE/WAPE including zero-denominator behavior.

## Milestone 3: ML features

**Status:** Implemented 2026-10-24: shared causal features, two bounded global histogram-tree configurations evaluated on all development folds, pipeline persistence and forecast reload checks. Medium configuration selected by development MAE; holdout subsequently evaluated without hyperparameter changes.

Build lag/rolling/calendar features using only data available at forecast time; train a tree model.

**Acceptance gate:** Same folds and eligible products compare baseline and model without future leakage.

## Milestone 4: Uncertainty and monitoring

**Status:** Historical OOS normalized-residual intervals and frozen final evaluation completed 2026-10-24, with product/segment coverage, widths, runtime, plots and error analysis. The 80% intervals undercovered; no post-holdout recalibration was applied. Local MLflow tracking and simulated chronological monitoring completed 2026-10-24: versioned saved-evaluation imports, idempotent forecast ledgers, delayed scoring, explicit operational investigation thresholds and seven separate fictional incident scenarios. Thirty tests and real replay reconciliation passed. See MONITORING.md; no recurring job or external notifications were installed.

Calibrate intervals on historical validation errors; log experiment/data versions and replay data-quality and error alerts.

**Acceptance gate:** Report interval coverage/width and per-product metrics on held-out time periods.

## Milestone 5: Serving and release

**Status:** Local FastAPI/Streamlit application implemented and browser-verified 2026-10-24. Separate saved application refit, validated read-only API, product/history/interval/baseline explorer and monitoring view. Dataset-edge and beyond-dataset states explicitly distinguish unavailable observations. Six API tests, original 30 tests and artifact reconciliation passed; actual screenshots captured. Release preparation subsequently added fixture CI, a verified Docker application image/Compose smoke, environment examples, data/model cards, a case study, recording guide and release audit. The release API suite now has seven tests. Code-license selection, standalone repository setup, hosted CI and authorized publication remain gates; see RELEASE_CHECKLIST.md.

Expose forecasts and a dashboard; containerize scheduled batch prediction and publish a reproducible report.

**Acceptance gate:** Fresh checkout reproduces a backtest; label outputs as observed-sales forecasts, not unconstrained demand.

## Portfolio deliverables

README with architecture and setup; reproducible evaluation command; baseline comparison; error analysis; screenshot/demo; short case study describing engineering decisions and limitations. Results are added only after experiments run.
