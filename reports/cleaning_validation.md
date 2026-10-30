# Cleaning Validation — Cleaned Data vs Ground Truth

`data/truth/` holds the data as it was before the data-quality problems were injected. It is not used by the cleaning; this report only measures the result.

**Overall: 699,855 of 699,855 cleaned values (100.00%) exactly match the true values** (imputed values are scored separately below).

## Row coverage

| table           |   truth_rows |   clean_rows |   matched |   recall |
|:----------------|-------------:|-------------:|----------:|---------:|
| vendors         |          150 |          150 |       150 |  100.00% |
| items           |          800 |          800 |       800 |  100.00% |
| purchase_orders |        50000 |        49971 |     49971 |   99.94% |
| deliveries      |        53688 |        53546 |     53546 |   99.74% |
| sales           |        28800 |        28800 |     28800 |  100.00% |
| inventory       |         1600 |         1600 |      1600 |  100.00% |

Rows in the truth but not in the clean data were removed on purpose: PO lines with no recoverable order date, and receipts whose PO number was corrupted (orphans), so they can't be linked to an order.

## Field accuracy (values not imputed)

| table           | field           |   compared |   matching |   accuracy |
|:----------------|:----------------|-----------:|-----------:|-----------:|
| vendors         | vendor_name     |        150 |        150 |    100.00% |
| vendors         | category        |        150 |        150 |    100.00% |
| vendors         | city            |        150 |        150 |    100.00% |
| vendors         | state           |        150 |        150 |    100.00% |
| vendors         | onboarding_date |        150 |        150 |    100.00% |
| items           | item_name       |        800 |        800 |    100.00% |
| items           | category        |        800 |        800 |    100.00% |
| items           | unit_of_measure |        800 |        800 |    100.00% |
| items           | standard_price  |        800 |        800 |    100.00% |
| purchase_orders | order_date      |      49971 |      49971 |    100.00% |
| purchase_orders | vendor_id       |      49971 |      49971 |    100.00% |
| purchase_orders | item_id         |      49971 |      49971 |    100.00% |
| purchase_orders | quantity        |      49898 |      49898 |    100.00% |
| purchase_orders | unit_price      |      49852 |      49852 |    100.00% |
| purchase_orders | order_type      |      49971 |      49971 |    100.00% |
| purchase_orders | promised_date   |      48961 |      48961 |    100.00% |
| purchase_orders | buyer_id        |      49971 |      49971 |    100.00% |
| deliveries      | po_id           |      53546 |      53546 |    100.00% |
| deliveries      | line_no         |      53546 |      53546 |    100.00% |
| deliveries      | received_date   |      53546 |      53546 |    100.00% |
| deliveries      | qty_received    |      53546 |      53546 |    100.00% |
| deliveries      | qty_rejected    |      52882 |      52882 |    100.00% |
| sales           | qty_sold        |      28673 |      28673 |    100.00% |
| inventory       | qty_on_hand     |       1600 |       1600 |    100.00% |

## Imputed values (estimates, so judged by closeness)

| table           | field         | rule                 |   rows |   exact | median_error   | within_tolerance   |
|:----------------|:--------------|:---------------------|-------:|--------:|:---------------|:-------------------|
| purchase_orders | quantity      | qty_from_receipts    |     73 |      69 | 0.0 units      | 94.5% (≤ 0 units)  |
| purchase_orders | unit_price    | price_imputed        |    119 |       0 | 2.1 %          | 98.3% (≤ 10 %)     |
| purchase_orders | promised_date | promised_imputed     |   1010 |     206 | 1.0 days       | 95.0% (≤ 3 days)   |
| deliveries      | qty_rejected  | rejected_blank_set_0 |    514 |     494 | 0.0 units      | 96.1% (≤ 0 units)  |
| sales           | qty_sold      | qty_imputed          |    127 |      16 | 17.6 %         | 63.8% (≤ 25 %)     |
