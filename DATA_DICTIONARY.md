# Data dictionary

## Source workbook / normalized CSV

All eight columns are preserved during streaming conversion of both sheets. Excel datetimes become naive ISO local timestamps; missing cells become empty CSV fields. Sheet counts and hashes are in the provenance manifest.

| Column | Meaning and handling |
|---|---|
| Invoice | Transaction/invoice ID, kept as text; C prefix signals cancellation |
| StockCode | Product or special transaction code; text, stripped and uppercased for aggregation |
| Description | Item description; missing allowed; used for policy audit, not a model feature |
| Quantity | Units; must be finite integral numeric value; negatives tracked separately |
| InvoiceDate | Naive source-local datetime; assumed UK local calendar; invalid/offset timestamps excluded |
| Price | Unit price in pounds sterling; positive required for sales; finite required for return candidate processing |
| Customer ID | Customer identifier; missing allowed; not exported into weekly data or audit |
| Country | Customer country; all countries pooled; not used to infer timezone |

UCI's textual schema names InvoiceNo, UnitPrice and CustomerID refer to workbook Invoice, Price and Customer ID respectively. The implementation validates actual workbook column names.

## weekly.csv

One product/calendar-week row from the first accepted sale onward; deterministic product/week order.

| Column | Meaning |
|---|---|
| product_id | Canonical product code |
| week_start | Monday date, ISO YYYY-MM-DD |
| observed_units | Forecast target: accepted positive units for an assumed complete week; blank when partial/unverified/missing |
| recorded_positive_units | Accepted units actually present, even for partial/unverified weeks; **not a substitute target** |
| accepted_sale_rows | Number of accepted lines including retained duplicates |
| status | observed, partial_week, missing_observation |
| coverage_reason | assumed_complete_extract, coverage_boundary, declared_missing_day, coverage_unverified |
| days_without_source_transactions | Calendar days in this week with no valid-timestamp source rows (not proof of outage; outside-coverage days also count) |
| prior_observed_weeks | Count of earlier complete observed product weeks |
| prior_consecutive_observed_weeks | Consecutive observed weeks immediately before this issue week |
| history_eligible_at_issue | Boolean: prior consecutive history meets configured minimum; scoring also requires an observed target |

## returns_weekly.csv

Separate sparse product/week/kind table, including return-only products. `recorded_return_units` is the sum of absolute negative quantities, not subtracted from sales. `kind` is cancellation or negative_without_cancellation. `complete_week_assumed` is false for boundaries, declared gaps and unverified coverage. Absence of a returns row means no accepted candidate record, not independently confirmed zero returns. No causal link to an earlier sale is asserted.

## row_audit.csv

`source_row`: normalized CSV record number including the header, starting at 2 (not a physical line number for multiline fields); `outcome`: exclusive cleaning result; `duplicate_of_row`: first exact matching input row or blank; `flags`: pipe-separated overlapping conditions. It contains no invoice or customer IDs. Rows are not removed from this audit, including rejected records.

## quality.json and source.json

Quality schema version 2 stores input hash, inclusive coverage, assumption, declared gaps, min/max valid timestamps, no-activity dates, minimum history, exclusive row outcomes, overlapping flags, excluded-code frequencies, product/week/status totals, positive units and return-candidate units. Partial recorded sales contribute to positive-unit totals but not observed targets.

Source provenance stores official page/download URLs, retrieval timestamp in UTC, license/attribution, archive/workbook sizes and SHA-256 hashes, normalized CSV SHA-256, sheet row counts, actual schema and timestamp extent. `reports/` holds copies of these aggregate/provenance records; row-level files stay ignored under `data/`.
