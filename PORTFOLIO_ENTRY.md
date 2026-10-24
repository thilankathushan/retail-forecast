# Retail Forecast — ML Engineering

[Public GitHub repository](https://github.com/thilankathushan/retail-forecast)

Built a reproducible pipeline for one-week-ahead **observed product sales** using UCI Online Retail II. Compared simple baselines with a global scikit-learn tree using expanding-window chronological backtests, origin-time product eligibility and leakage-tested features.

On 59,395 common product-week observations in the frozen 13-week final evaluation, the tree achieved **MAE 18.95 units and aggregate WAPE 59.71%**, reducing pooled absolute error by **7.71%** versus a trailing-average baseline. Reported uncertainty honestly: 80% intervals achieved **75.45%** coverage, with weaker coverage for medium-scale products and large sales spikes.

Engineered local MLflow tracking, idempotent historical monitoring with delayed scoring, a validated FastAPI API, a Streamlit explorer, Docker support and fixture-only CI. Documented data provenance, exclusions, model limitations and reproducible artifact generation.

**Stack:** Python, pandas, scikit-learn, MLflow, FastAPI, Streamlit, SQLite, Docker, GitHub Actions.

**Demo availability:** runs locally or through Docker; this is a public code repository, not a publicly hosted application. The dataset is historical (2009–2011), and observed sales do not establish demand, stockouts or inventory availability.
