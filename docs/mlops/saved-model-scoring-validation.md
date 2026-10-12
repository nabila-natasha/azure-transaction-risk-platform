# Saved XGBoost Model Scoring Validation

## Objective

Verify that the saved XGBoost model reproduces the existing Gold
transaction-risk predictions before any production data refresh.

## Validation approach

1. Read the existing Gold scored-transactions Parquet dataset.
2. Load the streaming Silver transactions.
3. Apply the production feature-engineering function.
4. Load the versioned XGBoost model and validate its feature contract.
5. Recalculate fraud probabilities without writing to Gold.
6. Compare transaction IDs, fraud probabilities, predicted-fraud labels,
   and risk bands.

## Results

| Check | Result |
|---|---:|
| Existing Gold rows | 139,538 |
| Gold columns | 32 |
| Duplicate transaction IDs | 0 |
| Matched transaction IDs | 139,538 |
| Transactions only in existing Gold | 0 |
| Transactions only in new scoring | 0 |
| Maximum probability difference | 0 |
| Mean probability difference | 0 |
| Predicted-fraud disagreements | 0 |
| Risk-band disagreements | 0 |

## Conclusion

The saved XGBoost model reproduced the existing Gold fraud probabilities
exactly for all 139,538 streaming transactions. Predicted-fraud labels and
risk bands also matched exactly.

The comparison was read-only. Gold data was not modified, and the existing
32-column output contract was preserved.

## Model artifact

- Model run ID: `20261012T024013Z`
- Model type: `XGBClassifier`
- Validated input features: 11
- Feature contract: validated against the scoring pipeline

## Engineering significance

This validation demonstrates saved-model loading, feature-contract
validation, prediction reproducibility, transaction-level reconciliation,
and a safe verification process before modifying production-style outputs.
