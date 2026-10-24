# Two-minute recording guide

Start the API and dashboard using README. Use product **22423**. Record the real localhost UI; do not overlay invented numbers. Keep the historical-data notice visible. No camera or recording automation is installed by this project.

| Time | Screen/action | Narration |
|---|---|---|
| 0:00–0:15 | Next-week snapshot, search 22423 | “This predicts observed positive sales, not demand. The data is from 2009–2011; this is not a live retail forecast.” |
| 0:15–0:35 | Forecast cards, chart and baselines | “The snapshot was issued December 5, 2011 after the previous week closed. Both intervals are estimates. The target week is incomplete, so there is no scored actual.” |
| 0:35–0:55 | Historical backtest, select 2011-11-28, expand provenance | “These are frozen past-only rolling forecasts. This product's actual was 236 units. Model and data versions and issue times are inspectable. The API serves saved artifacts without training.” |
| 0:55–1:15 | Open FINAL_RESULTS.md or its diagnostic plot | “The tree reduced pooled error about 7.71% versus a trailing mean, but 80% intervals covered only 75.45%. Medium-scale products and spikes were particularly difficult.” |
| 1:15–1:35 | Monitoring view | “This is a historical replay with assumed delivery times. Errors appear only after the week closes. Repeated batches do not duplicate forecasts. Synthetic incidents are separate, not real outages.” |
| 1:35–1:50 | Beyond dataset; then search a nonexistent ID | “Beyond December 12 is withheld because prior-week observations are incomplete. Missing evidence produces a clear unavailable state rather than a plausible-looking forecast.” |
| 1:50–2:00 | Return to snapshot | “The project emphasizes reproducibility and honest limits: no inventory recommendations, no fresh-holdout claim after tuning, and no production monitoring claim.” |

Before recording: check `scripts/smoke_application.py`; use a clean viewport; close unrelated tabs; verify displayed metrics against saved reports. Source credit in video description: Chen, D. (2012), Online Retail II, UCI, DOI 10.24432/C5CG6D, CC BY 4.0. Do not claim Docker or hosted CI passed unless the release checklist has subsequently recorded those executions.
