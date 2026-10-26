# Public historical demo aggregates

observed-sales.zip contains derived product-week observations and saved forecasts, indexed by product for low-memory access. It contains no customer IDs, invoice records, model binaries or credentials. The manifest records its hash and source application-bundle hash. These are real historical results, not synthetic benchmark data.

Attribution: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D. Source data licensed CC BY 4.0: https://creativecommons.org/licenses/by/4.0/. Cleaning, exclusions and weekly aggregation are documented in DATA_CARD.md and DATA_CONTRACT.md. Forecasts are derived using the documented frozen evaluation and separate dataset-edge refit. No endorsement implied.

Regenerate after the documented application export with `.venv/bin/python scripts/build_cloud_demo.py`. This exports existing results; it does not fit or evaluate models. Historical observed sales are not demand or current retail activity.
