# Release checklist — 2026-10-24

**Status: publication authorized; local checks pass.** MIT selected under the owner’s delegated choice. Project 3 has an isolated repository; hosted CI verification is pending the initial push.

## Verified locally

- [x] **30 core tests** pass with warnings as errors: configuration, transaction cleaning, temporal splits, metrics, causal features/reload, intervals and monitoring/idempotency. Fixture CLI exercises prepare → backtest → train → forecast.
- [x] **7 API tests** pass with warnings as errors: validated responses, missing/corrupt artifacts, bounded literal input, unknown/missing forecasts, empty historical folds and read-only caching.
- [x] Same suites pass in a temporary copy of release candidate files with no raw data, model binaries or generated artifacts, using the existing installed environments. This checks fixture isolation, not a fresh dependency installation.
- [x] Real-data application verification reconciles 4,703 dataset-edge forecasts with the persisted/reloaded model and 59,395 historical predictions with frozen evaluation outputs.
- [x] Frozen evaluation provenance, common cohorts and fixed historical interval calculations still verify. No evaluation-affecting change; no final rerun was necessary or performed.
- [x] All eight monitoring ledgers pass duplicate/timing/metric reconciliation checks.
- [x] Native HTTP smoke passes: readiness, product search/history, historical/edge/beyond-dataset modes, monitoring and Streamlit health. Actual browser workflow/screenshots were verified in the application milestone; this release changes no dashboard behavior.
- [x] Docker Compose configuration parses; application image builds using the constrained dependency snapshot; both containers become healthy on localhost 8001/8502; real-data HTTP smoke passes through Docker. Temporary containers/network were removed afterward. Native app was left undisturbed.
- [x] Image is non-root; Compose uses read-only root filesystems and artifact mount, tmpfs, dropped capabilities and localhost-only ports. Docker context allowlists application source/config and pins; no raw data/model binaries/secrets are copied.
- [x] CI YAML parses and defines two timed, fixture-only Python 3.14 jobs with read-only repository permissions and no UCI downloads or secrets. Local equivalent suites pass.
- [x] README, exact reproduction/container setup, environment example, data/model cards, case study, recording script and notices are present.
- [x] Official UCI source/license rechecked: CC BY 4.0; attribution, retrieval metadata, transformations and hashes documented.
- [x] Candidate-file pattern/size/path audit reports no findings; raw/customer-level data, models, local environments and tracking stores remain excluded. No release candidate exceeds 5 MiB. Actual screenshots show only the project UI/product aggregates, not credentials or customer identifiers.
- [x] Core/application/tracking dependency metadata inventories recorded. No unsupported live-demand, inventory, fresh-holdout or formal-coverage claims in the new release narrative.

## Publication gates

- [x] **Code license:** MIT selected under owner-delegated choice; LICENSE and package metadata added. UCI data attribution remains separate.
- [x] **Standalone repository:** Git initialized inside Project 3; parent repository, other projects and existing local artifacts preserved. The workflow is at the new repository root.
- [x] **Publication authorization:** owner explicitly requested a public retail-forecast repository and push; no force-push or overwrite of remote work is permitted.
- [ ] **Hosted CI:** verify both Linux jobs after the initial push and record the run URL.

## Explicit verification limits / future work

- Full raw-download-through-final rerun was not repeated: all needed local artifacts exist and no model/evaluation rules changed. The documented fresh-checkout route uses the committed freeze to reproduce an already-exposed period, not a new independent test.
- Docker base image is a mutable Python 3.14 slim tag, and dependency locks are environment snapshots rather than hash-locked universal supply-chain manifests. The tested image is local; no image was pushed.
- The release-file scan checks current tracked/unignored candidates and common credential patterns. It is not an exhaustive secret, Git-history, dependency-vulnerability or legal audit. Installed license metadata may be abbreviated or unspecified.
- UI and HTTP checks establish a usable local demo, not production authentication, concurrent-load capacity, real ingestion timing or business value. No recurring job or external notifications are configured.
- Sparse/new-product exclusions, extraction completeness, retained possible duplicates, historical source bias and interval undercoverage remain substantive limitations. New evaluation data is required for future final claims.

## Recheck commands

```sh
.venv/bin/python -W error -m unittest discover -s tests -v
.venv-app/bin/python -W error -m unittest discover -s app_tests -v
.venv/bin/python scripts/verify_final.py
.venv/bin/python scripts/verify_application.py
.venv/bin/python scripts/verify_monitoring.py
.venv-app/bin/python scripts/smoke_application.py
python3 scripts/audit_release.py
docker compose config --quiet
```

Container startup/smoke/teardown commands: [REPRODUCING.md](REPRODUCING.md). Source audit: [reports/release/audit.json](reports/release/audit.json). Historical measured results: [FINAL_RESULTS.md](FINAL_RESULTS.md).
