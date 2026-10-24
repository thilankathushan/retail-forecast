# Model card — Global weekly observed-sales forecaster

**Status:** portfolio research/demo; final chronological holdout already exposed. Owner: Thilanka Thushan. Evaluation frozen 2026-10-24. No production effectiveness claim.

## Intended use

Compare transparent baselines with a global tree on next-week positive observed product units; demonstrate causal feature generation, chronological evaluation, uncertainty, artifact versioning and simulated monitoring. Serve saved historical predictions and a dataset-edge snapshot locally. Not intended for current retail activity, estimating unconstrained demand, inventory optimization, purchase recommendations or autonomous decisions.

## Model and inputs

scikit-learn HistGradientBoostingRegressor, absolute-error loss; selected configuration 60 iterations, 15 leaves, learning rate 0.1, minimum leaf size 20, early stopping disabled, random seed 42. One model pools products. Missing features use a constant -1 imputer with indicators. All preprocessing fits within each training window. No product-ID encoding or future catalog metadata is used.

Features: lags 1/2/4/13/52; shifted 4/13-week means and 4-week standard deviation; observed/active history counts, activity fraction and age; target-week month and cyclical week-of-year. No realized target-week price, quantity or future aggregate is an input. Training examples use features available at their own origins. Shared feature code drives training and inference; future-perturbation tests protect this contract.

Data and exclusions are in [DATA_CARD.md](DATA_CARD.md). Four consecutive prior observed weeks are required. New/short histories are excluded and counted; all-zero histories remain eligible. Baselines: last observed week, trailing four-week mean, and seasonal naive at 52 weeks with trailing-mean fallback when a complete seasonal history is unavailable.

## Evaluation protocol

Dates were selected from coverage before inspecting model performance. Expanding training starts 2009-12-07; first 52 weeks initialize history. Development: 39 weekly origins 2010-12-06–2011-08-29. Final: 13 weekly origins 2011-09-05–2011-11-28. No random splitting. Two bounded tree configurations were compared on development folds; medium selected by pooled development MAE. All models use identical eligible product-week cohorts.

The final procedure froze features, model/baseline settings, eligibility, intervals, metrics and weekly rolling retraining before exposure. Every final fit sees only targets strictly before its issue week. Final data was not used for hyperparameters or interval quantiles. Later application refitting is separate from that evaluation and has no new accuracy claim. Any further model changes are exploratory; the same holdout cannot become untouched again.

## Measured results

| Model | Final MAE (units) | Aggregate WAPE |
|---|---:|---:|
| Global tree | 18.9452 | 59.7114% |
| Trailing mean | 20.5286 | 64.7019% |
| Last week | 23.8326 | 75.1158% |
| Seasonal + fallback | 34.4262 | 108.5046% |

59,395 scored product-weeks across 4,693 products; 98.354% of 60,389 candidates. Excluded: 237 new-product and 757 short-history rows. Tree pooled error is about 7.71% lower than trailing mean, but loses on one of 13 weekly MAEs and 868 product MAEs, with 1,508 ties. WAPE = total absolute error / total actual units, not mean product WAPE. Zero denominator is null; MAE remains defined for nonempty cohorts.

Development tree MAE 13.7679/WAPE 71.1071% was used for selection, so it is not an independent generalization estimate. Runtime: final evaluation 27.51 seconds including feature/report I/O, with 19.45 seconds refitting across 13 sequential origins; macOS arm64, Python 3.14.0/scikit-learn 1.9.1, two threads. These are measured laptop timings, not service-latency guarantees. Full segment/product metrics and error analysis: [FINAL_RESULTS.md](FINAL_RESULTS.md), [reports/final](reports/final).

## Uncertainty and failure modes

Fixed quantiles of absolute OOS development error normalized by `max(1, prior 13-week mean)` use 163,986 historical predictions. Quantiles: 0.6408995 (80%) and 2.6666667 (95%); endpoints clipped at zero. Sparse scales fall back to one. No fitted training residuals or final outcomes calibrate intervals. Time dependence, changing product activity and shifts invalidate simple exchangeability assumptions; no formal coverage guarantee is claimed.

| Nominal | Observed final coverage | Mean width (units) |
|---|---:|---:|
| 80% | 75.4542% | 32.0983 |
| 95% | 94.1796% | 92.9250 |

Medium-scale products (>5–25 prior mean units) achieve only 55.394% coverage at 80% nominal. Large spikes dominate failures: product 23084, 2011-10-24, actual 5,593 versus forecast 38.67 and upper 95% bound 544.31. Of 3,457 misses at 95%, 3,446 are above the upper bound. Pooled results hide this asymmetry and segment variation. No post-holdout recalibration was applied.

## Artifact and operational boundaries

Frozen procedure: [final_freeze.json](final_freeze.json); data hashes/dependency versions and code hashes are retained. Development model is saved separately from the application model. Historical API model versions combine freeze hash and origin (not individual rolling model-binary hashes). Application model is a separate post-evaluation refit with binary hash and training cutoff 2011-12-05. Its forecast target is incomplete and unscored. Forecasts from 2011-12-12 are withheld because the prior week is incomplete.

Local MLflow records evaluation/version artifacts. Monitoring replays observations under assumed arrival times; synthetic incidents are separate. Operational thresholds are explicit examples, not holdout-tuned alarms or evidence of real model failure. No notifications, live retraining or scheduler is installed. Original code uses the MIT License; dataset attribution obligations remain separate.
