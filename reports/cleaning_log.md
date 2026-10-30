# Cleaning Log

Produced by `sql/03_standardize.sql` (types, formats, spellings) and `src/clean_data.py` (duplicates, recovery, imputation, outliers). Removed rows are kept in the `rejected_rows` table with their reason; fixed rows carry their fixes in the `dq_flags` column.

## Summary

| Table | Rows in | Removed | Rows fixed (flags) | Rows out |
|---|---:|---:|---:|---:|
| vendors | 155 | 5 | 7 | 150 |
| items | 800 | 0 | 26 | 800 |
| purchase_orders | 51,000 | 1,029 | 3,330 | 49,971 |
| deliveries | 54,493 | 947 | 833 | 53,546 |
| sales | 28,944 | 144 | 127 | 28,800 |
| inventory | 1,600 | 0 | 9 | 1,600 |

## vendors

| Action | Rule | Rows |
|---|---|---:|
| removed | duplicate registration of V014 | 1 |
| removed | duplicate registration of V115 | 1 |
| removed | duplicate registration of V129 | 1 |
| removed | duplicate registration of V140 | 1 |
| removed | duplicate registration of V142 | 1 |
| fixed | payment_terms_unknown | 7 |

## items

| Action | Rule | Rows |
|---|---|---:|
| fixed | uom_from_similar_items | 26 |

## purchase_orders

| Action | Rule | Rows |
|---|---|---:|
| removed | exact duplicate row | 1,000 |
| fixed | vendor_remapped | 251 |
| fixed | vendor_from_po | 1,203 |
| fixed | vendor_from_name | 277 |
| fixed | vendor_from_core_name | 1 |
| fixed | order_date_from_po | 155 |
| removed | order_date missing and not recoverable from the same PO | 28 |
| fixed | qty_sign_fixed | 79 |
| fixed | qty_from_receipts | 73 |
| removed | quantity 0 and nothing received | 1 |
| fixed | price_fixed_x100 | 162 |
| fixed | price_imputed | 119 |
| fixed | promised_imputed | 1,010 |

## deliveries

| Action | Rule | Rows |
|---|---|---:|
| removed | exact duplicate row | 805 |
| removed | orphan: PO line does not exist | 110 |
| removed | parent PO line removed during cleaning | 32 |
| fixed | year_fixed | 169 |
| fixed | rejected_invalid | 150 |
| fixed | rejected_blank_set_0 | 514 |

## sales

| Action | Rule | Rows |
|---|---|---:|
| removed | exact duplicate row | 144 |
| fixed | qty_imputed | 127 |

## inventory

| Action | Rule | Rows |
|---|---|---:|
| fixed | qty_sign_fixed | 9 |

## Removed rows by reason

| Source table | Reason | Rows |
|---|---|---:|
| purchase_orders | exact duplicate row | 1,000 |
| deliveries | exact duplicate row | 805 |
| sales | exact duplicate row | 144 |
| deliveries | orphan: PO line does not exist | 110 |
| deliveries | parent PO line removed during cleaning | 32 |
| purchase_orders | order_date missing and not recoverable from the same PO | 28 |
| vendors | duplicate registration of V014 | 1 |
| vendors | duplicate registration of V115 | 1 |
| vendors | duplicate registration of V129 | 1 |
| vendors | duplicate registration of V140 | 1 |
| vendors | duplicate registration of V142 | 1 |
| purchase_orders | quantity 0 and nothing received | 1 |
