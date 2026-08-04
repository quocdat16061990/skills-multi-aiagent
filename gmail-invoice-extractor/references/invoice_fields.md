# Invoice fields

The workbook contains exactly five sheets: `Summary`, `Invoices`, `Attachments`, `Duplicates`, and `Review_Errors`.

## Invoice fields

- `source`: local extracted file path.
- `seller_name`, `seller_tax_id`: issuing organization and tax identifier.
- `buyer_name`, `buyer_tax_id`: recipient organization and tax identifier.
- `symbol`: invoice series/symbol.
- `invoice_number`: invoice sequence identifier.
- `invoice_date`: source value; no speculative normalization.
- `currency`: source currency code/value.
- `subtotal`, `tax`, `total`: source strings; no locale-unsafe numeric coercion.
- `confidence`: `high` for recognized XML tags, `medium` for unambiguous labeled text, otherwise `low`.
- `notes`: missing, ambiguous, or extraction-related review notes.

## Deduplication

1. Exact attachment bytes are deduplicated by SHA-256.
2. Parsed invoices are then deduplicated only when all three normalized-by-trimming values are present: `seller_tax_id + symbol + invoice_number`.

The runner never silently merges partial keys. Duplicate evidence is retained in `Duplicates`.

## Safety and review

XML containing `DOCTYPE` or `ENTITY` declarations is rejected before stdlib `ElementTree` parsing. ZIP members are constrained by count, per-member size, total expanded size, extension, and traversal checks. Workbook strings beginning with `=`, `+`, `-`, or `@` are prefixed with an apostrophe, then the saved workbook is reopened and verified. Regex extraction is intentionally conservative; unresolved records belong in `Review_Errors`.
