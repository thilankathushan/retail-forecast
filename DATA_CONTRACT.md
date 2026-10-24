# Data contract and provenance

Target: next week's positive sales units after the exclusions below, aggregated by product across all customers and countries. Returns are separate. Transactions do not establish true demand, inventory availability, stockouts or physical returns.

## Official source and rights

[UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), dataset 502. Attribution: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D.

UCI lists **CC BY 4.0** (verified 2026-10-23), and a **43.5 MB** workbook download. Preserve attribution and identify transformations when sharing derived data. The source archive comes from UCI's own download endpoint. `reports/uci_source.json` records the precise URL, UTC retrieval timestamp, byte counts and SHA-256 of the archive, workbook and normalized CSV. Raw data is ignored by Git. No customer-level records are copied into reports.

The workbook's two sheets are `Year 2009-2010` and `Year 2010-2011`. Ingestion requires their exact names and eight columns; it fails on unexpected schema rather than silently skipping a sheet. The source page uses aliases such as InvoiceNo/UnitPrice/CustomerID, while the actual workbook uses Invoice/Price/Customer ID. See [data dictionary](DATA_DICTIONARY.md).

## Time and observation contract

Week = [Monday 00:00, next Monday 00:00) in assumed Europe/London local wall-clock time. Forecasts are issued only after the preceding week is closed and available. Source timezone and extract completeness are not independently established by transactions. Naive ISO timestamps are retained; offset-bearing or invalid timestamps are excluded, never coerced to arbitrary dates. DST does not alter calendar week labels.

Coverage bounds are inclusive dates. The real extraction spans 2009-12-01 through 2011-12-09; both boundary weeks are partial. Accepted records in partial weeks are retained as `recorded_positive_units`, but the forecast target is blank. `--missing-day` marks the entire containing week uncertain and excludes that day's positive sales from the retained sales tally. Returns on such days remain recorded candidates, with an incomplete-week flag.

**Default:** coverage is unverified; all weekly targets are blank. The explicit `--assume-complete` option asserts that the extract contains every relevant transaction inside its coverage interval (apart from declared missing days). Under that assumption, full weeks with no accepted transactions for an already-seen product have zero observed sales. This says nothing about demand or stock availability. This assumption is used for the real run based on UCI's description of the collection; it is not proof of operational uptime.

Days without any valid-timestamp source transactions are listed in the cleaning report and counted on each weekly row. No-activity days can be closures, holidays or missing extracts; they are not automatically diagnosed as outages. Every observed row retains `coverage_reason=assumed_complete_extract`. Uncertain and partial weeks remain distinguishable even when recorded positive units exist.

## Auditable cleaning policy v2

`row_audit.csv` gives every input CSV data row a mutually exclusive outcome, source row number, duplicate reference and overlapping flags. `quality.json` reconciles exclusive outcomes to all input rows. Flags overlap and must not be summed as row counts. Precedence:

1. Reject malformed CSV row widths, missing invoice, missing product and invalid/missing timestamp.
2. Strip surrounding identifier whitespace and uppercase product codes. Exclude the explicit non-product codes below. Quarantine identifiers outside the accepted product formats as `unrecognized_product_code`.
3. Require finite integral quantity and finite numeric price. Reject invalid quantity then invalid price. No rounding, interpolation, magnitude trimming or outlier clipping.
4. Exclude records outside supplied coverage.
5. Negative quantities become `return_or_adjustment` candidates with absolute units, split into cancellation invoices (`C` prefix, case insensitive) and negatives without cancellation. Finite zero/negative prices do not invalidate their unit tally. These may be stock adjustments; do not claim verified returns. No invoice matching or subtraction from positive sales.
6. Remaining C-prefixed invoices are excluded as `cancellation_nonnegative`, even when positive. Remaining zero quantities are excluded.
7. Positive sales require price > 0; free items and negative-price rows are excluded. Declared missing-day sales are excluded as `untrusted_day`.
8. Remaining rows are accepted positive sales.

**Non-product exclusions:** POST and DOT (postage), C2 (carriage), D (discount), M (manual), BANK CHARGES, AMAZONFEE, CRUK (commission), B (bad-debt adjustment), ADJUST/ADJUST2, S (samples), TEST001/TEST002, and GIFT_ prefixed vouchers. These are static semantic rules, frozen after inspecting codes/descriptions, not a ranking based on sales totals.

**Accepted product formats:** five digits optionally followed by one or two letters, DCGS followed by letters/digits, PADS, SP1002. The source contains genuine merchandise descriptions in the latter formats, so numeric-only filtering would lose products. Bare GIFT and C3 are unresolved and quarantined, not automatically labeled merchandise. Missing descriptions do not alone invalidate product records. Description text is not used as a future-informed product-survival filter. Ambiguous DCGS adjustment rows still follow quantity/price rules; classification is imperfect without a catalog.

**Duplicate policy:** preserve all repeated rows. SHA-256 fingerprints of all normalized CSV fields identify exact field-for-field repeats globally across both sheets. Audit rows point to the first identical source CSV row. There is no reliable invoice-line identifier to prove an accidental duplicate. No invoice-only or product/date deduplication. The report separately counts accepted duplicates retained. Case/whitespace normalization of product IDs does not redefine fingerprint equality.

**Missing customer IDs:** retained for otherwise valid sales and separately counted (including accepted rows with missing customers). Customer IDs are not a requirement for a product-sales forecast.

## Product panel and eligibility

A product first enters in its first accepted sale week; no earlier weeks are fabricated. It stays in the panel to the coverage boundary; this does not establish continued assortment or survival. No top-N filter, minimum lifetime sales, future total or last-sale cutoff is used.

For each issue week, `prior_observed_weeks` and `prior_consecutive_observed_weeks` count only earlier complete observed weeks. `history_eligible_at_issue` requires at least `--min-history-weeks` consecutive prior weeks (default 4); missing/partial history resets the streak. The current target's value/availability is not part of this history test. Eligibility for scoring additionally requires an observed target. No global list selected from future performance is produced.

The frozen development evaluator recomputes the common four-week eligibility from past observations for all three baselines. The standalone foundation train/forecast commands remain persistence-state utilities; model-comparison results come from the development evaluator. See EVALUATION_PROTOCOL.md for frozen folds, the seasonal fallback and metric policy.
