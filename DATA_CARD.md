# Data card — UCI Online Retail II

## Source and rights

Chen, D. (2012). **Online Retail II** [Dataset]. UCI Machine Learning Repository. DOI: [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). [Official source](https://archive.ics.uci.edu/dataset/502/online+retail+ii); CC BY 4.0, rechecked 2026-10-24. Attribution and identification of transformations are required when sharing derived data. This dataset license does not license this project's code.

UCI describes transactions for a UK-based non-store retailer from December 2009 to December 2011. The source is historical, from one business, and includes wholesale activity; it is not a representative sample of today's retail sector. It contains customer identifiers and transaction-level information. The application and release reports do not expose those identifiers or invoice-level rows.

The listed workbook size is 43.5 MB. The retrieved official ZIP is 45,622,418 bytes; the workbook is 45,622,278 bytes. Retrieval: 2026-10-23T18:22:09.733979+00:00. ZIP SHA-256: `572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb`. Normalized CSV SHA-256: `834ba7c3c25bcd1d4fdc20b969b6f4f6da5e84b611036bbd18ba47ce3569e542`. Exact official download URL, workbook hash and sheet counts: [source manifest](reports/uci_source.json). Raw data stays outside Git and the Docker context.

## Unit of analysis and target

Ingest both workbook sheets and all eight columns: Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country. Schema aliases on UCI's website differ from actual workbook headers; ingestion validates the workbook schema explicitly.

Forecast one product's next-week **positive observed sales units after exclusions**, summed across customers and countries. This is not net sales, revenue or latent demand. Returns/negative adjustments are tracked separately; transaction records alone cannot establish stockouts, inventory availability or verified physical returns.

Weeks are Monday 00:00 to the next Monday, end-exclusive, in assumed Europe/London wall-clock time. The source does not establish timezone or delivery times. Coverage is 2009-12-01–2011-12-09, with incomplete first/last weeks. Their recorded positive totals are retained for audit, but targets are null.

## Cleaning and observation decisions

Full precedence and code lists: [DATA_CONTRACT.md](DATA_CONTRACT.md); fields: [DATA_DICTIONARY.md](DATA_DICTIONARY.md). Rules are explicit and auditable, rather than a claim that every suspicious row is erroneous.

| Condition | Decision |
|---|---|
| Missing invoice/product or invalid timestamp | Exclude; retain reason in row audit |
| Non-product codes (postage, discounts, manual charges, vouchers etc.) | Exclude by documented static rules; quarantine unresolved formats |
| Invalid/nonfinite/noninteger quantity or invalid numeric price | Exclude; no rounding or magnitude clipping |
| Negative quantity | Separate absolute-unit return/adjustment candidate; never subtract silently from target |
| Cancellation invoice with nonnegative quantity | Exclude |
| Zero quantity or nonpositive price on positive units | Exclude from positive-sales target |
| Repeated complete record | Retain and flag; no reliable line identifier proves duplication is erroneous |
| Missing customer ID/description | Does not alone invalidate product-sales records |
| Declared missing day/partial boundary week | Unknown target; never silently fill zero |

The measured cleaning run processed 1,067,371 rows; accepted 1,037,021 sales lines; separately tracked 21,741 negative-unit candidates; retained 33,664 accepted duplicate lines and 234,370 accepted lines without customer IDs. See [cleaning report](reports/uci_cleaning.json). Counts of overlapping flags must not be added together as exclusive exclusions.

A zero target requires the explicit `--assume-complete` extraction assumption. Lack of transactions may reflect closures, missing extracts or no sales; it is not evidence of no demand. There are 135 dates with no source transactions, mostly Saturdays. They are flagged, not automatically diagnosed as outages.

## Coverage, selection and risks

The panel contains 421,455 product-weeks for 4,725 product IDs, including 7,057 partial-week rows and 414,398 observed rows. Products enter at their first accepted sale. No top-selling product filter, future survival filter or lifetime-sales ranking is used. Products remain in the panel to the coverage boundary; this is an operational assumption, not proof of continuing assortment. Every origin independently requires four consecutive prior observed weeks. New/sparse products can be excluded; cohort exclusions are reported.

Limitations include ambiguous stock codes, undocumented extraction completeness, retained possible accidental duplicates, mixed retail/wholesale purchasing, dated seasonal behavior and lack of inventory/catalog information. Product IDs can change meaning over time; descriptions are not used as future-informed features. No causal, customer-level or protected-group claims are supported.

Synthetic fixtures and incident scenarios are manually invented, clearly labeled, stored separately and unsuitable as benchmark evidence. Published summaries are derived aggregates; raw workbooks, customer-level CSVs, row audits and model binaries remain ignored. Review derived artifact redistribution and preserve CC BY attribution before publishing downloads.
