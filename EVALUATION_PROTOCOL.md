# Forecast evaluation protocol v1

Frozen on 2026-10-24, before computing development baseline performance. Machine-readable configuration: `evaluation_protocol.json`. Dates derive solely from the known coverage: 104 complete weeks from 2009-12-07 through 2011-11-28. Initial training uses 52 weeks, final holdout reserves 13 weeks, and the intervening 39 weeks are development targets. Partial boundary weeks are excluded.

| Partition | Monday target/training weeks | Purpose |
|---|---|---|
| Initial training | 2009-12-07–2010-11-29 | Initial 52-week history |
| Development targets | 2010-12-06–2011-08-29 | 39 rolling-origin comparisons |
| Final holdout targets | 2011-09-05–2011-11-28 | 13 weeks; evaluated under FINAL_EVALUATION.md on 2026-10-24 |

Each fold issues a one-week forecast at the target week's Monday 00:00 Europe/London, after the previous week fully closes, conditional on its data being available. Local timestamps include the appropriate UTC offset; the target ends at next Monday 00:00 exclusive. No random split. Training starts at the same fixed date and expands up to, but excludes, each origin. Earlier development actuals become historical training observations in later folds; later observations never enter earlier predictions. The development evaluator still excludes holdout. The separate frozen final evaluator now rolls forward on those weeks; see FINAL_RESULTS.md.

## Cohort and history

At an origin, consider products already present in historical data. The panel does not select by lifetime sales totals or survival. Four consecutive complete observed calendar weeks immediately before the origin are required for every model. This is recomputed from the history, not trusted from a precomputed eligibility flag. Missing periods remain missing; calendar gaps are never compressed. New products first seen in the target week are counted retrospectively as `new_product` exclusions, without being added to the origin's forecastable catalog. Products with fewer than four prior observations are `short_history`; other recent gaps are `incomplete_recent_history`.

All-zero histories are retained and forecast normally. Product inactivity is not used as an exclusion or an inferred delisting. Forecasts are generated for all history-eligible products, even if the target is unavailable; those forecasts have blank actuals and `scored=false`. Scoring requires an observed target and uses exactly the same product/week keys for all three models. Target values never determine history eligibility. The eligibility audit records candidate keys, reasons, target availability, prior observation counts and zero-history flags.

Coverage counts all products known by the origin plus products first appearing in that target week. Products not yet observed anywhere are unknowable and outside that denominator. Report candidate coverage, exclusion counts, observed targets, scored rows and seasonal fallback use. Missing/new/short-history cases are visible, not silently dropped to improve apparent performance. This is a shared-cohort comparison, not a claim that every future SKU can be forecast.

## Baselines (fixed before results)

- **Last-observed-week:** most recent prior complete observed week. Shared four-week eligibility ensures it is the immediately preceding calendar week; stale values across recent gaps are not used.
- **Trailing-average:** arithmetic mean of the four immediately preceding observed calendar weeks. Fractional unit forecasts are retained without rounding.
- **Seasonal-naive:** target-week lag of 52 calendar weeks, provided all 52 preceding weeks are observed. Otherwise use the trailing four-week average and mark `seasonal_fallback=true`. This approximates annual seasonality; 52 weeks is not an exact calendar-year/holiday alignment. Seasonal results therefore describe a hybrid baseline, not an exclusively seasonal forecast. Shorter histories do not cause model-specific exclusions.

The expanding window is available history, while each deterministic rule uses the stated lag/window. There is no parameter search or refitting of learned coefficients.

## Metrics

MAE = sum absolute error / number of scored product/week rows, in units. Aggregate WAPE = sum absolute error / sum actual units over all scored rows, expressed as a ratio. It is **not** an average of per-product WAPEs or per-fold WAPEs. Per-product and per-fold tables include counts, actual-unit sums and absolute-error sums so aggregates can be independently reconciled.

If actual sum is zero, WAPE is null/blank even when predictions are also zero; MAE is still defined for nonempty rows. With no scored rows both MAE and WAPE are null. No epsilon denominator, clipping or silent omission. A product with mixed zero/nonzero weeks has WAPE calculated across all its scored weeks. Predictions and actuals must be finite and nonnegative.

## Reproduction and outputs

```sh
.venv/bin/python -W error -m unittest discover -s tests -v
.venv/bin/retail-forecast --config config.uci.toml backtest --protocol evaluation_protocol.json
```

Outputs in ignored `artifacts/uci/development/`: actual `predictions.csv`, complete `eligibility.csv`, `folds.csv`, `per_product.csv`, `per_fold.csv`, and `metrics.json`. Aggregate metrics and fold definitions are also retained under `reports/development/` for review. Predictions are deterministic; protocol and input hashes identify the run. Avoid changing dates or baseline windows after seeing results without explicitly versioning the protocol and disclosing the change.

The loader filters out holdout rows before validating targets or constructing model inputs; CSV bytes may be scanned and the full weekly file is hashed for provenance. No holdout targets are used for fitting, eligibility, forecasts, metrics or tuning. Earlier data-cleaning inspection covered the full source and is not represented as a sealed/raw-data blind test. These statements describe the development loader. The separately frozen final procedure has now evaluated the holdout; it must not be called untouched again.

All results inherit the data pipeline's complete-extract assumption, retained duplicates, exclusion policy and observational limits. Forecasts concern observed positive sales, not unconstrained demand or inventory availability.
