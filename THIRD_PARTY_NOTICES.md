# Attribution and license boundaries

## Project code — MIT

Original project code is licensed under the [MIT License](LICENSE), copyright 2026 Thilanka Thushan. The owner delegated the license choice before publication. This code license does not replace the separate dataset attribution/license or upstream software notices.

## Dataset

Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D. [Official dataset](https://archive.ics.uci.edu/dataset/502/online+retail+ii), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Rechecked 2026-10-24. This project transforms transactions through the documented cleaning rules and weekly aggregation; derived charts, summaries and served observations must retain attribution and identify these transformations. Neither UCI nor the dataset author endorses this project.

Raw workbooks, customer-level transactions and model binaries are not release files. The application bundle contains derived product-week observations and forecasts and is generated locally. Do not publish an artifact download without checking its attribution and redistribution requirements. The dataset license is distinct from the license for original code; generated weights also should not be assigned an unsupported blanket license.

## Software dependencies

Installed name/version/license metadata inventories are in `reports/release/core-dependencies.json`, `app-dependencies.json` and `tracking-dependencies.json`. These inventories include transitive packages and may contain incomplete or abbreviated metadata. They are not a legal clearance, SBOM vulnerability attestation or substitute for each distribution's LICENSE/NOTICE files.

The stack uses Python, pandas, NumPy/SciPy, scikit-learn, FastAPI/Starlette, Streamlit, Plotly, MLflow and their dependencies. Preserve upstream notices when redistributing software or images. pip-installed distributions retain their license metadata in the application image; review upstream notices and platform libraries before public container distribution. No third-party code was copied from web examples into a claim of exclusive ownership. Screenshots are actual local application captures; plots use the recorded experiment results.
