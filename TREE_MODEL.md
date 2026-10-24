# Global tree model v1

One global scikit-learn HistGradientBoostingRegressor is fit across all eligible products per origin. Histogram binning is suitable for the weekly table on this laptop; two CPU threads bound compute. No LightGBM dependency is needed for this first measured comparison. See the official [estimator documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html).

## Causal feature contract

`retail_forecast.tree.features` is the single training/inference feature path. It reindexes calendar weeks and shifts sales **before** computing historical features. Each historical training row uses its own origin's information, not aggregates computed at the current fit cutoff.

- Unit lags: 1, 2, 4, 13 and 52 calendar weeks.
- Shifted rolling means: 4 weeks (all required) and 13 weeks (available observations); shifted 4-week population standard deviation.
- Cumulative counts of prior observed and positive-sales weeks; active/observed fraction; weeks since first observed history in the training range.
- Target month and sine/cosine of target ISO week using a fixed 52-week seasonal approximation (week 53 is approximate).

No realized target-week sales, prices, future aggregates or catalog metadata enters X. Product ID is a grouping/output key only; no fitted product vocabulary, ordinal ID or target encoding. Previously unseen IDs with four observed prior weeks can be forecast. Products without that history are excluded under the frozen common cohort rule. All-zero histories remain included. Missing periods are not treated as zero.

Every fold fits a fresh Pipeline: constant -1 imputation plus learned missingness indicators, then histogram trees with absolute-error loss. Imputation and binning are fit only on historical training examples. The constant sentinel is outside valid nonnegative sales and makes entirely missing long-lag columns safe in the installed estimator. Unavailable values are not discarded or replaced by future values. Scaling is unnecessary for these trees. Tree predictions are clipped to nonnegative units without rounding.

## Bounded development tuning

Same frozen 39 expanding-window origins and four-prior-week eligibility as all baselines. Two candidates were fixed before tree results: small = 30 boosting iterations / 7 leaves; medium = 60 iterations / 15 leaves. Both use learning rate 0.1, minimum leaf size 20, absolute-error loss, seed 42, and no randomized early stopping. Select minimum pooled development MAE, ties by candidate name. This is development tuning, not an unbiased test estimate or nested-CV result.

All eligible historical examples with known targets before each origin are used for training. Candidate folds cannot silently fail or skip cases: failures are written to a diagnostic file and abort the run. Scored product/week keys must equal the saved baseline keys exactly. Candidate metrics, per-product errors and fit/predict timings are saved alongside predictions. Baseline runtimes, when reported, time all three deterministic rules together including their shared cohort construction; they are not individual model-fit measurements.

## Persistence and forecast replay

```sh
.venv/bin/retail-forecast --config config.uci.toml tree-backtest --protocol evaluation_protocol.json
.venv/bin/retail-forecast --config config.uci.toml tree-forecast --issue-week 2011-08-29
.venv/bin/python scripts/verify_tree.py
```

The selected pipeline is persisted at ignored `models/uci/tree.joblib` with a readable `tree.json` manifest: ordered numeric feature schema, dependency versions, Python version, seed/configuration, source/weekly/protocol/code hashes, training-row count and exclusive cutoff. It is refit through 2011-08-28, retaining 2011-08-29 as a development replay origin. Selection used all development outcomes, so replay is only a serialization/parity check, not a new independent evaluation. This development replay command still rejects holdout dates. The separately frozen final evaluator has now refit/evaluated the selected procedure on the holdout; see FINAL_RESULTS.md.

The forecast command uses only history before the requested origin and the same feature builder. It validates local artifact hash, schema, dependency versions and weekly-data version, and rejects origins before the training cutoff or inside/after the reserved holdout. New datasets require explicit versioning/retraining. Only load locally generated trusted joblib files: pickle-based loading can execute code, and cross-version loading is unsupported ([scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html)).

Initial engineering failures were resolved before successful tuning: physical-core detection was unavailable in the sandbox (fixed with an explicit CPU limit), and an all-missing 52-week lag triggered an installed histogram-binning failure (fixed with pipeline imputation). These were implementation/environment failures, not failed candidate folds excluded from a score.
