# Frozen final evaluation v1 — declared before opening holdout

Frozen 2026-10-24. Evaluate the existing 13 weekly target origins, 2011-09-05 through 2011-11-28, with one-week horizon. Initial training begins 2009-12-07. Keep all features, selected medium histogram tree (60 iterations, 15 leaves, absolute-error loss, learning rate 0.1, leaf minimum 20, seed 42, early stopping disabled), fitted pipeline preprocessing and two-thread limit unchanged. Retrain from scratch each Monday using only labeled weeks ending before that origin; previously closed holdout weeks may join subsequent training. No hyperparameter changes after holdout access.

Baselines remain last observed week, trailing four-week average, and 52-week seasonal-naive with four-week average fallback unless all 52 prior weeks are observed. All methods require four consecutive observed weeks before the origin; include all-zero histories, exclude new/short/gapped histories with audited counts. No future catalog or sales-total selection. The target remains observed positive sales under the complete-extract assumption.

## Interval rule frozen before results

Use only the selected model's saved chronological out-of-sample development predictions (39 folds). Reconstruct each prediction's scale from its own historical features: `s = max(1, mean of available prior 13 calendar weeks)`. The four-week eligibility rule guarantees at least four observations; shorter-than-13 histories use available prior weeks. The one-unit floor handles zero/low sales. Pool `abs(actual - prediction) / s` across products. Pooling avoids unreliable per-product residual quantiles for sparse products while normalization accounts for sales scale. No product-specific fitted scale or target-week information.

For nominal levels 80% and 95%, use sorted score at 1-based rank `ceil((n+1)*level)`; fail if the pool is too small for a finite rank. Prediction interval = `[max(0, forecast - q*s), forecast + q*s]`. Do not round endpoints. Hold these quantiles fixed throughout the holdout: no recalibration from holdout outcomes, even though point-model retraining uses past closed weeks. No in-sample fitted residuals are used.

This is a conformal-style empirical residual interval, not a claim of exact distribution-free coverage. Serial/cross-product dependence, drift, pooling, and refitting violate simple exchangeability assumptions. The model configuration was selected using the same development folds whose out-of-sample errors are calibrated, adding selection optimism. Empirical holdout coverage and segment diagnostics, rather than formal guarantees, are the evidence. Time-series limitations are discussed by [Zaffran et al. (2022)](https://proceedings.mlr.press/v162/zaffran22a.html); our method does not implement their adaptive procedure.

## Frozen reports and segments

Point metrics: pooled MAE and aggregate WAPE, sum absolute errors / sum actual units. Zero denominator means null WAPE; MAE remains defined for nonempty rows. Never average product WAPEs into overall WAPE. Every baseline/tree uses the same scored product/week keys.

Intervals: empirical coverage (inclusive endpoints), mean/median width in units, mean interval score `width + 2/alpha * distance outside interval`, and counts. Report aggregate, per-product, per-origin and the following origin-time segments, for every point model and tree intervals:

- History: new/no observations, 1–3, 4–12, 13–51, 52+ observed prior weeks.
- Scale: prior mean-13 ≤5 units, >5–25, >25 (using floored interval scale).
- Activity: all previously observed weeks zero versus some positive history.

Report forecast coverage and exclusion reasons by segment, including target availability; target-week actuals do not define segments. Retain sparse per-product metrics with row counts, without interpreting them as reliable long-run estimates.

Measure wall-clock feature creation, tree training, tree inference, baseline inference and total evaluation on this laptop, sequential folds, two model threads, no parallel hyperparameter search. Timing scopes and machine/software metadata accompany results. Plots: per-fold point error, nominal/empirical interval coverage, interval width by historical scale, and largest-error examples. Error analysis will include undercoverage and where a baseline outperforms the tree, without changing the frozen model.

`final_freeze.json` and `interval_calibration.json` will be written before final targets are loaded, with source, data, development-prediction, code and dependency hashes. The final evaluator refuses an existing run directory, leaving a started marker even if execution fails. Subsequent model/method changes must be labeled exploratory; this holdout cannot be described as untouched again.
