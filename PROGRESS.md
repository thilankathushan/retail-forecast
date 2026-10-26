# Project 3 progress

## 2026-10-23 — Milestone 1: validated weekly-series pipeline

Implemented a dependency-free Python CSV pipeline with schema checks, exclusive cleaning-reason counts, source SHA-256, explicit inclusive coverage bounds, known missing-day handling, Monday-start weekly aggregation and deterministic output. Products enter at their first accepted sale, avoiding retrospective panel membership. Partial and missing weeks retain blank targets; fully observed weeks can contain zero sales. Added a synthetic fixture and documented source attribution, cleaning policy and downstream leakage constraints.

Verification (Python 3.14.0, run from `03-retail-forecast`):

```sh
python3 -m unittest discover -s tests -v
python3 -m retail_forecast.pipeline --input tests/fixtures/synthetic_transactions.csv --output-dir artifacts/synthetic-smoke --coverage-start 2024-01-03 --coverage-end 2024-01-30 --missing-day 2024-01-16
```

Six tests passed initially, covering cleaning accounting, zeros versus partial/missing observations, product entry, invalid contracts, deterministic output and future-product isolation. CLI smoke run succeeded: 11 synthetic input rows, 4 accepted rows, 2 products, 8 weekly rows. These are fixture counts, not forecasting metrics. Initial test invocation from the workspace root failed to import the package; the documented command runs from the project directory and passed.

Limitations: no real dataset has been downloaded or evaluated; CSV only, no Excel importer yet. Coverage must be asserted externally. Duplicate transaction lines are retained, non-merchandise codes await audit, and a product remaining in the panel does not imply inventory availability. No forecast quality claims are possible.

Next steps: import both UCI workbook sheets with recorded provenance and row reconciliation; audit product codes and data coverage; implement and test last-week/seasonal-naive rolling-origin backtests with explicit eligibility and MAE/WAPE behavior. Continue with leakage-safe tree features, historical calibration, monitoring and serving according to the implementation plan.

Repository: shared workspace Git repository inspected before read-only status checks. Changes confined to Project 3. No commits, pushes, author configuration changes or publication performed. Future publication author: Thilanka Thushan <158076487+thilankathushan@users.noreply.github.com>; no AI co-author trailers.

## 2026-10-23 — Foundation: package, environment and CLI

Implemented installable `retail-forecast` package metadata and console entry point; project-local `.venv`; pandas and scikit-learn core dependencies; tested runtime constraints; strict TOML settings for processed data, model/artifact paths, one-week horizon, timezone assumption and seed. Paths resolve relative to the configuration file. Added stderr logging, expected-error exit code 2, project-local ignore rules and explicit synthetic fixture documentation. Transaction hashing now streams bytes to avoid loading the full raw file again.

All four commands are functional: prepare preserves cleaning behavior; backtest evaluates the last-week baseline on consecutive observed product/week pairs; train stores persistence state in versioned JSON; forecast validates the artifact's issue week and writes product forecasts. This baseline is deterministic and records the seed for future tree training. Pandas validates weekly tables and scikit-learn computes MAE. WAPE is null for zero total actual sales. Future rows cannot affect the selected preceding-week baseline state; unknown observations are never zero-imputed.

Documented the one-week objective, Monday-local half-open week boundaries, post-close issuance, Europe/London wall-clock assumption and DST behavior. Historical CLI issue dates represent replay origins; data availability is still an operator assertion.

Verification on macOS arm64, Python 3.14.0:

```sh
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install -c requirements-lock.txt -e .
.venv/bin/python -W error -m unittest discover -s tests -v
.venv/bin/python -m pip check
.venv/bin/retail-forecast --help
.venv/bin/retail-forecast prepare --input tests/fixtures/synthetic_transactions.csv --coverage-start 2024-01-03 --coverage-end 2024-01-30
.venv/bin/retail-forecast backtest
.venv/bin/retail-forecast train --issue-week 2024-01-29
.venv/bin/retail-forecast forecast --issue-week 2024-01-29
```

Results: 11 tests passed with warnings treated as errors, including subprocess execution from another working directory, invalid configuration and weekly inputs, temporal gaps, future-row isolation, zero-denominator behavior and stale/corrupt artifact errors. Dependency check passed. All four console commands succeeded on synthetic input (8 weekly rows; 3 eligible backtest rows; 2 product forecasts). These counts are engineering smoke checks, not real benchmark results. Git ignore checks covered the environment, raw and processed data, models, generated artifacts, secrets and model binaries.

The initial sandbox install could not resolve PyPI; a permitted network-enabled install succeeded with pandas 3.1.0 and scikit-learn 1.9.1. The first test run found a macOS `/var` versus `/private/var` assertion mismatch and pandas deprecated weekday aliases; both were corrected before the clean run. No additional direct runtime dependencies beyond pandas/scikit-learn were introduced; their transitive dependencies are pinned in the runtime snapshot.

Limitations and next steps: real workbook ingestion and source audit are still pending. Last-week persistence is the only model; seasonal-naive, fixed evaluation splits, tree features, interval calibration, monitoring and dashboard remain future work. The runtime snapshot was verified on this laptop only. Weekly panels are held in memory and need profiling before large-catalog use. Generated paths represent one run and are overwritten; use separate configurations to retain runs. No blockers remain for this foundation milestone. No commits or pushes; other projects were preserved.

## 2026-10-23 — UCI data pipeline and real-data cleaning

Verified the official UCI Online Retail II page, CC BY 4.0 license, Daqing Chen attribution/DOI, advertised 43.5 MB workbook and actual schema. Downloaded the official archive; provenance records retrieval at 2026-10-23T18:22:09.733979+00:00 (2026-10-23 in Asia/Colombo), URLs, precise sizes and SHA-256 hashes. Archive: 45,622,418 bytes; workbook: 45,622,278 bytes. Full hashes are preserved in `reports/uci_source.json`. All raw files remain ignored by Git.

Added openpyxl 3.1.5 for read-only streaming workbook conversion. Imported both sheets: 525,461 and 541,910 rows, totaling 1,067,371. Actual workbook headers are Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country. Valid timestamps span 2009-12-01 07:45 through 2011-12-09 12:50. Import fails on unexpected sheets/headers and records normalized CSV provenance.

Implemented auditable policy v2: every record has an exclusive outcome and overlapping flags; all rules appear in the report including zero-count rules. Explicit special-code exclusions, whitespace/case canonicalization, finite/integral numeric checks, timestamp validation, retained duplicates with first-record references, missing-customer retention, separate negative-unit return/adjustment tallies, partial-week suppression and coverage uncertainty flags. Numeric-only product filtering was rejected after inspecting real merchandise descriptions on DCGS/PADS/SP1002 codes. C3 and bare GIFT remain quarantined. No product selection uses sales totals or future survival.

Preparation now defaults to unknown coverage. `--assume-complete` is required for zero-filled full-week targets and remains labeled on each observed row. `--missing-day` preserves explicitly uncertain weeks. Recorded partial sales remain available separately from targets. History columns describe only prior complete weeks, with four consecutive weeks required by the default eligibility flag. The foundation baseline still uses its separately documented one-prior-week rule; common model-comparison eligibility is future work.

Real run with explicit complete-extract assumption:

| Exclusive outcome | Rows |
|---|---:|
| Accepted positive sales | 1,037,021 |
| Return/adjustment candidates | 21,741 |
| Non-product codes | 5,911 |
| Nonpositive sales prices | 2,696 |
| Unrecognized product codes | 2 |
| Total | 1,067,371 |

Produced 421,455 weekly rows for 4,725 products: 414,398 observed-under-assumption and 7,057 partial. Accepted positive units total 11,402,671 (includes recorded units in partial weeks, not all usable targets). Separate recorded negative-unit magnitude totals 1,049,968. Retained 33,664 accepted exact repeats and 234,370 accepted records missing customer IDs. There are 135 dates without source transactions, including 104 Saturdays; absence alone is not proof of missing extracts. These are data-cleaning measurements, not forecasting metrics.

Commands verified from this project directory:

```sh
.venv/bin/python -m pip install -c requirements-lock.txt -e .
.venv/bin/retail-forecast download --raw-dir data/raw
.venv/bin/retail-forecast import-uci --raw-dir data/raw
.venv/bin/retail-forecast --config config.uci.toml prepare --input data/raw/transactions.csv --coverage-start 2009-12-01 --coverage-end 2011-12-09 --assume-complete
.venv/bin/python -W error -m unittest discover -s tests -v
.venv/bin/python -W error scripts/verify_uci.py
.venv/bin/python -m pip check
```

Initial download used curl against the exact official URL, with retrieval time recorded from the completed file; the implemented download command verified its cached hash. Workbook import was executed through the same `import_workbook` function used by the CLI. The final preparation command was run on the full normalized dataset. Fifteen offline tests passed with warnings as errors, including two-sheet import, returns, code rules, duplicate retention, customer missingness, unknown coverage, history eligibility and earlier foundation checks. Real-data checks reconciled every audit outcome to input counts, checked source hashes, summed sales and return units, validated unique product/week rows, target nullability and eligibility flags. Dependency and Git-ignore checks passed. A one-off inspection initially emitted pandas' mixed-ID dtype warning; the saved verification script explicitly preserves product IDs as text.

Updated README, DATA_CONTRACT.md, new DATA_DICTIONARY.md, aggregate reports and dependency snapshot. Generated row-level audits and data remain under ignored paths. No commits or pushes; other projects unchanged.

Limitations: source completeness/timezone remain assumptions; repeats may inflate totals if some are accidental; negative lines include inventory adjustments; merchandise classification lacks an authoritative catalog; no real forecast evaluation yet. Next: freeze chronological folds, define shared model eligibility, implement seasonal-naive and compare baselines before tree training, calibration, monitoring and dashboard work.

## 2026-10-24 — Frozen evaluation protocol and simple baselines

Recorded `evaluation_protocol.json` before inspecting baseline performance. Coverage supplies 104 complete Monday weeks: initial 52 weeks start 2009-12-07; 39 development target weeks span 2010-12-06–2011-08-29; final 13 holdout weeks span 2011-09-05–2011-11-28. Expanding training ends strictly before every forecast origin. Fold definitions were saved before execution. No random split or performance-driven date selection.

Implemented last-observed-week, trailing four-week average, and 52-week seasonal-naive with trailing-average fallback unless all preceding 52 weeks are observed. Every model shares a four-consecutive-prior-observed-week eligibility rule computed at the origin. New, short and gapped histories are audited; all-zero histories remain eligible. Predictions are produced even for eligible products with unknown targets, with scoring restricted identically across models. The eligibility flag from preparation is not trusted as a substitute for origin-time recomputation.

Added pooled MAE/WAPE, per-product/per-fold metrics and explicit zero-denominator behavior (null WAPE; MAE defined for nonempty groups). Forecast timestamps are Monday 00:00 Europe/London with DST-aware offsets. The normal backtest command now runs only frozen development folds; the older synthetic helper is `backtest-smoke`, restricted to small inputs. Standalone train/forecast remain foundation persistence utilities, separate from evaluation.

Commands run:

```sh
.venv/bin/python -W error -m unittest discover -s tests -v
.venv/bin/retail-forecast --config config.uci.toml backtest --protocol evaluation_protocol.json
.venv/bin/python -W error scripts/verify_development.py
```

Twenty tests passed. Known-answer examples cover forecast values, seasonal fallback, split boundaries, DST timestamps, short/new/gapped/zero histories, missing targets and zero denominators. Future and holdout mutations do not change earlier predictions. Holdout numeric values are filtered before validation/model input construction. Saved-artifact verification checks identical scored keys, per-product sums versus pooled metrics, forecast dates and unused holdout folds.

Development results (same 163,986 scored product/week rows for every model):

| Baseline | MAE | Aggregate WAPE ratio |
|---|---:|---:|
| Last observed week | 18.67186833022331 | 0.9643442156984092 |
| Trailing average (4 weeks) | 17.542296293586038 | 0.9060053156761425 |
| Seasonal naive (52 weeks + fallback) | 26.10305910260632 | 1.3481422218946773 |

Coverage: 165,617 candidate rows, 163,986 scored (99.0152%); 413 new-product and 1,218 short-history exclusions; no eligible missing targets in this real run. Included 1,211 all-zero-history rows. Seasonal fallback used on 27,312 scored rows. Aggregate actual units = 3,175,137; model-specific skipping is not allowed. No parameter or date changes were made in response to these results.

Actual predictions, complete eligibility audit, fold definitions, metrics and per-product/per-fold tables are saved at `artifacts/uci/development/`. Aggregate metrics, fold definitions and per-fold metrics are copied to `reports/development/`; protocol/input/quality hashes link the run to exact inputs. Updated README, evaluation protocol documentation, data contract and implementation plan.

The holdout remains unused: no holdout predictions, scores, eligibility computation or model selection. CSV bytes are scanned and the input file is hashed for provenance; prior cleaning inspected overall data coverage, so this is not described as a completely blind raw-data holdout. Limits: the results are development-only, inherit complete-extract assumptions/retained duplicates, and seasonal-naive is a hybrid with fallback. Next: leakage-safe tree features and model comparison on the same development cohort, then calibration and a separately authorized final evaluation. No commits or pushes; other projects preserved.

## 2026-10-24 — Global tree model and causal features

Implemented a scikit-learn histogram gradient boosting Pipeline shared across products. LightGBM was unnecessary: the installed core stack completed the bounded comparison quickly. Directly declared already-installed numpy, joblib and threadpoolctl dependencies. Native histogram bins and pipeline imputation fit separately inside each expanding training window; early stopping is disabled to avoid a randomized validation split. CPU execution is limited to two threads.

One feature function serves historical training and forecast inference. For every row's own forecast origin it computes lag 1/2/4/13/52 sales, shifted mean 4/13 and standard deviation 4, prior observed/active history counts, activity fraction, history age and target-calendar month/week cycles. Product IDs are grouping keys only, never encoded or fitted; unseen IDs with sufficient prior history work without future catalog knowledge. No target-week sales/prices, future totals, or future eligibility enter features. Training labels must precede the current fit origin and each historical example must satisfy four-prior-week eligibility at its own origin.

Frozen bounded search: 30 iterations/7 leaves and 60 iterations/15 leaves, absolute-error loss, learning rate 0.1, minimum leaf size 20, seed 42. Selection is minimum pooled development MAE (name tie-break). Every candidate ran all 39 frozen development folds and matched the exact baseline scored keys. No configuration changes followed model-performance inspection.

Initial environment/implementation failures: sandbox physical-core detection emitted a warning, and the installed histogram implementation failed on entirely missing 52-week lag columns in early training. Explicit CPU limits and a fitted constant -1 imputer with missing indicators resolved these before successful tuning. The successful run had zero failed folds; failures abort rather than silently reducing coverage.

Results on the same 163,986 scored rows (3,175,137 actual units) per model:

| Model | MAE | Aggregate WAPE | Fit/predict seconds across 39 folds |
|---|---:|---:|---:|
| Small tree | 14.179368054498399 | 0.7323204793320649 | 24.3769 |
| Medium tree (selected) | 13.767925017899529 | 0.7110707197784764 | 44.1594 |

Compare baseline MAEs: last-week 18.6719, trailing-average 17.5423, seasonal-hybrid 26.1031. All share 99.0152% candidate coverage, including all-zero-history cases and the same documented new/short-history exclusions. End-to-end tree run took 71.9635 seconds. A separately timed three-baseline/shared-cohort recomputation took 25.4955 seconds and reproduced all saved baseline metrics; this excludes file loading and is not directly identical in scope to the full tree search.

Saved predictions, per-product errors, per-fold runtime/training counts, configuration metrics and failure report under `artifacts/uci/tree/`. Largest-error inspection shows continued spike failures: product 84568, week 2011-07-25, actual 4,384 versus prediction 103.1859 (absolute error 4,280.8141). Top 20 absolute errors are saved; no unsupported causal explanation is asserted.

Persisted selected pipeline at `models/uci/tree.joblib` with readable schema, configuration, seed, training cutoff/rows, Python/dependency versions and model/source/weekly/protocol/feature-code hashes. The exclusive cutoff is 2011-08-29 for a final development-origin replay. Selection uses all development folds; replay is a reload check, not an independent accuracy estimate. Holdout prediction dates are rejected, and the holdout remains unevaluated. Only locally generated trusted pickle-based artifacts should be loaded.

Verification commands:

```sh
.venv/bin/python -W error -m unittest discover -s tests -v
.venv/bin/retail-forecast --config config.uci.toml tree-backtest --protocol evaluation_protocol.json
.venv/bin/retail-forecast --config config.uci.toml tree-forecast --issue-week 2011-08-29
.venv/bin/python -W error scripts/verify_tree.py
```

Twenty-two tests passed, including known lag/rolling values, changing target/future observations without changing past features or forecasts, shared historical/inference feature parity, unseen-ID behavior, artifact reload equality and corruption rejection. Real saved-artifact checks passed: exact baseline cohorts, recomputed metrics, persisted model replay matching the selected final-fold predictions, and holdout command rejection. Official scikit-learn estimator and persistence documentation consulted; rationale and exact commands are in TREE_MODEL.md/README.md. Readable summaries and manifest are in reports/tree.

Limitations/next steps: results are tuned development estimates; no final generalization claim. No target-price features, inventory information, intervals or monitoring yet. Pipeline coverage/duplicate assumptions still apply. Next implement strictly historical interval calibration and monitoring; final holdout use remains a separate authorized milestone. No commits or pushes; other projects preserved.

## 2026-10-24 — Historical intervals and completed frozen holdout

Declared the final method in FINAL_EVALUATION.md before accessing final targets, then wrote final_freeze.json and interval_calibration.json before the final run's STARTED marker. The freeze records features, selected medium-tree configuration, baseline rules, four-week eligibility, segments, metrics, weekly expanding retraining schedule, seed, dependencies, data/code hashes and fixed interval settings. The immutable declaration is retained unchanged. No hyperparameter/method changes were made after opening the holdout.

Implemented conformal-style normalized absolute residual intervals from 163,986 saved out-of-sample development predictions only. Scale is max(1, prior 13-week available mean), recomputed at each forecast origin. Pooling provides stable residual estimates for sparse products; 4–12-week histories use available observations. Finite-sample order statistic ranks were 131,190 (80%) and 155,788 (95%), giving fixed quantiles 0.6408995149395663 and 2.6666666666666665. No in-sample residuals or holdout outcomes entered calibration. Intervals clip the lower bound at zero and are not rounded. Serial/cross-product dependence, distribution changes, rolling refits and development selection optimism preclude an exact exchangeability-based guarantee.

Ran all 13 frozen holdout origins, 2011-09-05–2011-11-28. Each point-model refit saw only targets before its origin; earlier completed holdout weeks entered later training as predeclared. Forecasts were made before joining current targets for scoring. Interval quantiles stayed unchanged. Saved predictions include all four point methods, actuals, origin-time segments/scales, timestamps and 80%/95% bounds. The final evaluator refuses an existing run directory and marks exposure before reading targets.

Results on the same 59,395 scored product-weeks for all models (4,693 products; 1,884,478 actual units):

| Model | MAE | Aggregate WAPE |
|---|---:|---:|
| Global tree | 18.9451745693 | 0.5971142372 |
| Trailing average | 20.5285588012 | 0.6470193603 |
| Last observed week | 23.8326458456 | 0.7511576150 |
| Seasonal + fallback | 34.4262311642 | 1.0850463630 |

Candidate coverage: 59,395 / 60,389 = 98.3540%; excluded 237 new-product and 757 short-history rows, with no eligible missing targets. Seasonal fallback applied to 7,677 scored rows. The tree improved pooled error by about 7.71% over trailing-average but lost on one of 13 weekly MAEs and 868 of 4,693 product MAEs (1,508 ties). All-zero-history rows were included; 403 had zero actual units and undefined WAPE, with MAE zero.

Interval results: 80% nominal achieved 75.4542% coverage, mean width 32.0983, median width 1.3804; 95% nominal achieved 94.1796%, mean width 92.9250, median 4.9231. The medium-scale (>5–25 prior units) segment undercovered at 55.3940%/90.3392%. Per-history, scale, activity, product and origin point/interval metrics and exclusion coverage are saved. The largest error (23084, 2011-10-24) was actual 5,593 versus tree 38.6692, above the 95% upper bound 544.3102. Of 3,457 misses at 95%, 3,446 were above the upper bound. No calibration adjustment was applied in response.

Measured wall time on macOS arm64, Python 3.14.0/scikit-learn 1.9.1, two threads and sequential folds: 5.1837 s feature creation, 19.4463 s tree training, 0.0937 s tree inference, 0.4723 s all baseline inference including panel preparation; 27.5129 s whole evaluation including data/report I/O, excluding calibration and plots. Runtime scopes are explicitly documented rather than claiming a universal speed benchmark. No final fold failed.

Commands executed:

```sh
.venv/bin/python -W error -m unittest discover -s tests -v
.venv/bin/retail-forecast --config config.uci.toml freeze-final
.venv/bin/retail-forecast --config config.uci.toml evaluate-final
.venv/bin/python -W error scripts/verify_final.py
.venv/bin/python scripts/plot_final.py
.venv/bin/python -m pip check
```

Twenty-six tests passed, including corrected quantile order statistics, scale invariance, interval endpoints/scores, origin-time segments, baseline parity and future-observation rejection. Saved artifact verification passed: freeze precedes exposure, cohorts match, point/interval metrics reconcile and every bound matches the fixed historical quantiles. Added matplotlib 3.11.2 for the requested static plots and refreshed the runtime dependency snapshot. Point-error, scale-coverage/width and largest-error plots were visually inspected.

Artifacts: complete machine-readable outputs and exposure/completion markers at artifacts/uci/final; compact reports/plots at reports/final; FINAL_RESULTS.md contains error analysis, runtime conditions, segment tables and reproducibility guidance. README and implementation status updated. Old development reports remain clearly labeled. Raw data/generated bulk outputs stay ignored; no commits or pushes and no other projects edited.

The final holdout is now exposed and must never be described as untouched again. Any later feature/model/interval changes are exploratory and require separate versioning and new evaluation data for a fresh final claim. Remaining work: simulated monitoring, dashboard and release packaging. Undercoverage, especially at 80%, is an unresolved empirical limitation rather than a reason to tune on the same holdout.

## 2026-10-24 — Local tracking and simulated historical monitoring

Implemented separate-environment MLflow 3.17.2 tracking with local SQLite metadata/artifacts, hashed import requests, artifact verification and retry reuse. Logged exact configurations, source/version references, training cutoffs, metrics and artifacts for saved development/tree/final evaluations. Core frozen forecasting dependencies and hashed evaluation modules remain unchanged. Added tracking dependency pins and ignore rules for tracking storage/environment.

Implemented chronological delivery/forecast/scoring replay, timezone-aware issue/closure timestamps, weekly schema/quantity validation, missing/late/dropped-product gates, sales/activity investigation signals, delayed errors and rolling interval coverage. Forecast SQLite keys prevent accidental duplicates and reject conflicting payloads. Forward-only incremental replay supports an explicit as-of clock. Operational thresholds were declared explicitly in monitoring_rules.json, not optimized against final holdout outcomes. Archived forecasts are replayed; this is not a new final evaluation or a production service.

Executed real replay: 59,395 forecasts, 13 scored weeks, no delivery/threshold alerts under the explicit on-time complete-extract assumption. Pooled MAE 18.9451745693, WAPE 0.5971142372 and 95% coverage 0.9417964475 reconcile with frozen results. Executed seven separate fictional scenarios: clean, missing columns, dropped products, sales shift, late data, invalid quantity and activity shift. Clean has 140 forecasts; delivery incidents withhold one origin and retain 120. Missing/invalid batches recover after 48 hours, permitting delayed scoring without backdating forecasts. Sales shift produces two distribution and four rolling coverage signals. These are synthetic monitoring checks, never real-data findings.

Verification: 30 lightweight tests passed, including no pre-closure scoring, late availability, forward resume, no duplicate forecasts, conflicting payload rejection, incident recovery and known MAE/coverage. Fixed a test SQLite connection cleanup warning. scripts/verify_monitoring.py verified eight ledgers/exports, timing and pooled real metrics; scripts/verify_final.py verified unchanged freeze provenance/cohorts/intervals. MLflow client inspection verified four real and seven synthetic finished runs with parameters, metrics and artifacts. Retried all three evaluation imports, real replay and missing-column replay: all five reused their existing run IDs and no forecasts duplicated. Tracking pip check passed. Batch wrapper executed manually; ignored tracking/generated paths verified.

Commands: core unittest discover with -W error; track-evaluations; monitor-replay --scenario real --track; monitor-replay --scenario each of the seven synthetic scenarios --track; scripts/verify_monitoring.py; scripts/verify_final.py; .venv-tracking/bin/python -m pip check; scripts/monitor_batch.sh --scenario clean. Exact setup/reproduction and a non-installed cron example are in MONITORING.md and linked from README.

Limitations: actual arrival times are unavailable and assumed at local week close; input checks cover prepared weekly panels; a complete-panel product-drop rule needs a production retirement policy. Synthetic forecasts are fixed illustrative values, not counterfactual ML refits. SQLite is authoritative; exports can be rebuilt after interruption. Logical per-origin model versions reference the freeze and cutoff, not separately persisted rolling binaries. Distribution changes invite investigation and do not prove model failure. Final holdout remains exposed; subsequent model changes are exploratory. Next: dashboard and portfolio/release packaging. No recurring job, external notifications, commit or push was configured; other projects preserved.

## 2026-10-24 — Local FastAPI and Streamlit application

Implemented a read-only FastAPI service and Streamlit dashboard in a separate `.venv-app` environment. Endpoints expose bounded literal product-ID search, weekly history, saved forecasts/baselines/80% and 95% intervals, model/data versions, issue/target/cutoff timestamps, data-quality status and simulated monitoring. Pydantic response validation rejects invalid intervals/nonfinite units or malformed artifacts. Missing/hash-mismatched artifacts return actionable 503 errors; unsafe/invalid inputs return 422, unknown products/origins 404, and unavailable forecasts have explicit reasons with no zero substitution. Dashboard loading, connection/retry, no-match and withheld-forecast states are implemented.

Added offline scripts/build_app_bundle.py using the established feature/fit/predict/interval path. It separately refits the selected frozen configuration with training targets strictly before 2011-12-05, saving a versioned application model and manifest. Partial target-week observations are excluded entirely from features/training. Exported 4,703 dataset-edge forecasts plus 59,395 unchanged original historical predictions. The API reads the hashed ~59 MiB JSON bundle once and serves it without fitting or loading pickle files. Neither frozen evaluation code nor results were modified.

Date semantics: the next-week snapshot is issued 2011-12-05 after the last complete week; target December 5–11 has incomplete source coverage and is unscored. Beyond-dataset forecasts starting 2011-12-12 are withheld because the immediately preceding week is incomplete. No fabricated completed week or today's retail forecast is shown. The application refit is post-evaluation, with no new accuracy claim. Monitoring uses real observations with assumed historical arrival times, not evidence of live operational reliability.

Verification completed: original 30 core tests passed with warnings treated as errors; six API tests passed with warnings treated as errors, including missing/corrupt/invalid artifacts, literal search limits, mode/date validation, unknown products, null actuals, unavailable forecasts, read-only requests and cached artifacts. Current Starlette 1.9.0 prefers httpx2 for TestClient; installed the official recommended dependency after strict validation caught its deprecated httpx fallback. App dependency check passed; versions pinned in requirements-app-lock.txt (FastAPI 0.162.0, Streamlit 1.66.1, Uvicorn 0.54.0, Plotly 6.9.0, Pydantic 2.14.1). Existing core and tracking environments preserved.

scripts/verify_application.py verified all 4,703 predictions match the reloaded persisted model and all 59,395 historical predictions/actuals match frozen final results. scripts/verify_final.py passed unchanged provenance/cohort/interval checks. Browser verification through the actual localhost UI exercised product 22423 search, historical week switching (2011-11-28 to 2011-09-05), charts/baselines, expanded provenance, real monitoring, beyond-dataset withholding and empty-search recovery. Captured actual PNG screenshots under reports/application: next-week, historical-chart, monitoring, beyond-dataset and empty-search. No mock screenshots or fabricated metrics.

Working commands are documented in README: isolated app install, offline bundle generation/verification, API tests, uvicorn on 127.0.0.1:8000 and Streamlit on 127.0.0.1:8501. Both foreground servers were started for verification and the dashboard left open. Stop with Ctrl-C; no recurring job installed. README and implementation status updated.

Limitations/next steps: product search uses IDs, not unversioned descriptions; catalog browsing is retrospective. One API worker caches the full bundle in memory; rebuild requires an API restart, while dashboard cache expires after 60 seconds. Local-only demo has no public deployment/authentication. Intervals remain estimates with documented undercoverage, and observed sales do not establish inventory or demand. Containerization, release packaging and portfolio case study remain future milestones. No commit or push; only Project 3 files edited.

## 2026-10-24 — Release preparation (no publication)

Added project-local fixture-only GitHub Actions jobs for Python 3.14 core/API suites; no UCI downloads, real-data training, MLflow or secrets needed. Added a non-root application Dockerfile, allowlisted build context, read-only Compose services and artifact mounts, readiness/health checks, localhost-only ports and .env.example. Rewrote README around the problem, architecture, verified results, setup, raw-data/training/evaluation route, forecasting semantics, monitoring, API/dashboard and actual screenshots. Added REPRODUCING.md, DATA_CARD.md, MODEL_CARD.md, CASE_STUDY.md, DEMO_SCRIPT.md, THIRD_PARTY_NOTICES.md and RELEASE_CHECKLIST.md.

Material fix: API historical mode now returns an explicit unavailable response when a valid bundle contains no historical folds, rather than indexing an empty list. Added a regression fixture. This is a serving-only change; no feature, model, interval, eligibility or evaluation code changed. Frozen final checks pass, so no evaluation was rerun. Original final exposure and undercoverage remain documented.

Verified: 30 core tests and 7 API tests pass with warnings as errors. Same suites passed in a temporary release-candidate copy without raw/generated artifacts using installed environments. Application reload/prediction reconciliation, final freeze/cohort/interval verification and all eight monitoring ledgers pass. Native real-data HTTP smoke checks readiness, search/history, every forecast mode, monitoring and Streamlit health. Docker Desktop initially was unavailable/startup timed out, then became available: image built successfully, both Compose services became healthy on alternate localhost ports 8001/8502, and the same real-data HTTP smoke passed. Temporary containers/network removed after checking; native application left undisturbed. Compose and CI YAML parsed. Full raw-to-final evaluation was not repeated because no existing results were invalidated.

Release audit: inspected Git layout (shared parent repository; Project 3 untracked), then scanned only tracked/unignored Project 3 candidates for common secrets, private/generated paths and files >5 MiB. No findings. Added repeatable scripts/audit_release.py and read-only scripts/smoke_application.py. Dependency license metadata inventories include core, app and tracking environments; these are not legal clearance or a vulnerability scan. Official UCI CC BY 4.0 source/license rechecked, source attribution and transformation obligations documented. Raw/customer-level data, weights, .env, environments, tracking DBs and the ~59 MiB serving bundle remain excluded from Git/Docker build context.

Release checklist separation:
- VERIFIED: local fixture suites, artifact reconciliation, native HTTP smoke, actual application screenshots from preceding milestone, Docker build/healthy startup/HTTP smoke/teardown, Compose/CI parsing, current-file hygiene audit, source attribution and release documentation.
- BLOCKERS: owner must select code license and add LICENSE/package metadata; publish Project 3 at repository root (or explicitly authorize a parent workflow) for CI discovery; run hosted CI; obtain user authorization before any commit/push/publication.
- LIMITS: no new full raw-to-final rerun or fresh untouched-holdout claim; no exhaustive history/vulnerability/legal audit, production authentication/load proof, real arrival-time monitoring or business-value claim. Docker base tag is mutable. Further model changes require exploratory labeling/new evaluation data.

Exact commands and artifacts are linked in RELEASE_CHECKLIST.md and REPRODUCING.md. No recurring jobs or external notifications configured. No commit, push, image publication or changes to other project files.

## 2026-10-24 — Publication authorized and staged

User requested a separate public GitHub repository named retail-forecast and delegated the outstanding license choice. Selected MIT for original code; added LICENSE/package metadata and retained separate CC BY 4.0 UCI attribution. Inspected the shared parent Git layout, confirmed no existing Project 3 repository, then initialized Git only inside 03-retail-forecast on main with author Thilanka Thushan <158076487+thilankathushan@users.noreply.github.com>. Parent/other projects and existing ignored local artifacts remain unchanged.

GitHub authentication verified as thilankathushan using the system keyring; the requested repository did not exist. All 30 core and 7 API tests passed again, frozen-result verification passed, and the release candidate audit reported no findings. No evaluation rerun was needed. Publication proceeds with source/tests/docs, aggregate reports and screenshots only; raw data, models, environments and tracking stores remain excluded. Hosted CI is to be checked after push. The Streamlit demo remains local, not publicly hosted.

## 2026-10-24 — Public repository published

Published https://github.com/thilankathushan/retail-forecast as a separate PUBLIC repository with main as the default branch and GitHub-recognized MIT licensing. Initial release commit: 0cf911dcd94b602eef798e8ba684786f4f73ccfe. Author/committer: Thilanka Thushan <158076487+thilankathushan@users.noreply.github.com>; no co-author trailers or other authorship credits. The first creation attempt was not executed because automatic approval review hit a usage limit. After the user requested continuation, authentication and repository absence were rechecked, then creation and push succeeded. No force-push or remote overwrite occurred.

Both hosted Linux/Python 3.14 CI jobs passed: https://github.com/thilankathushan/retail-forecast/actions/runs/40094646080 (core and application). Published only audited source, tests, documentation, aggregate evaluation reports, provenance, fixture data and actual screenshots. Raw/customer-level data, large models, generated serving bundle, environments, secrets and local tracking databases remain excluded; regeneration is documented. Parent repository and other projects remain unchanged.

Updated release checklist, repository clone instructions, CI badge and PORTFOLIO_ENTRY.md with verified results. Public code availability does not mean a hosted dashboard: FastAPI/Streamlit still run locally or in local Docker. No new evaluation, deployment, recurring job or external notifications were introduced.

## 2026-10-26 — Streamlit Community Cloud deployment repair

User's deployed screenshot showed ModuleNotFoundError importing httpx. Root cause: the cloud host did not discover requirements-app.txt automatically, and the dashboard still depended on a localhost API. Added root requirements.txt plus standalone default saved-data access; RETAIL_API_URL explicitly opts into the original HTTP API mode. Exported existing application aggregates into an indexed 7,992,686-byte compressed demo archive with SHA-256/source provenance and CC BY attribution. Reads one selected product at a time, without model loading, retraining, raw/customer records or the full expanded application bundle. The release audit has an explicit size exception only for this documented demo asset.

Eight application/cloud-data tests passed. Standalone Streamlit AppTest verifies startup/metrics without an API; frozen evaluation verification remains required before push. No numerical model/evaluation code changed. Cloud instructions specify Python 3.13, dashboard.py and no secrets/external API. Actual hosted recovery is to be checked after GitHub push; do not infer successful deployment from local testing alone.

Hosted recovery verified after commit ab4315b: the public URL https://retail-forecast-demo-thushan.streamlit.app loaded successfully in a browser without authentication. Product search 22423 returned the saved 2011-12-05 forecast 220.5, 80% interval 79.0–362.1 and 95% interval 0.0–809.5, with actual explicitly unscored. Actual hosted screenshot saved as reports/application/cloud-live.png. Standalone AppTest and frozen evaluation verification both passed. The deployment is now a public historical demo, not live retail forecasting.
