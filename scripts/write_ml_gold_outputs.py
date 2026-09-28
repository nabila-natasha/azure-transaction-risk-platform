from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
import io
import pandas as pd


STORAGE_ACCOUNT = "sttransactionbello"
FILESYSTEM = "synapse"
GOLD_ROOT = "gold/ml"


def get_filesystem():
    credential = DefaultAzureCredential(
        exclude_shared_token_cache_credential=True
    )

    service = DataLakeServiceClient(
        account_url=f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net",
        credential=credential,
    )

    return service.get_file_system_client(FILESYSTEM)


def write_parquet(filesystem, path, dataframe):
    buffer = io.BytesIO()

    dataframe.to_parquet(
        buffer,
        index=False,
    )

    buffer.seek(0)

    client = filesystem.get_file_client(path)

    client.upload_data(
        buffer.getvalue(),
        overwrite=True,
    )


def main():
    filesystem = get_filesystem()

    # ------------------------------------------------------------------
    # XGBoost validated evaluation results
    # ------------------------------------------------------------------

    xgboost_metrics = pd.DataFrame(
        [
            {
                "metric_type": "overall",
                "threshold": 0.50,
                "roc_auc": 0.9826,
                "pr_auc": 0.3622,
                "precision": 0.0606,
                "recall": 0.8450,
                "true_positive": 218,
                "false_positive": 3380,
                "false_negative": 40,
                "true_negative": 135900,
            },
            {
                "metric_type": "threshold_analysis",
                "threshold": 0.30,
                "roc_auc": 0.9826,
                "pr_auc": 0.3622,
                "precision": 0.0374,
                "recall": 0.8992,
                "true_positive": 232,
                "false_positive": 5979,
                "false_negative": 26,
                "true_negative": 133301,
            },
            {
                "metric_type": "threshold_analysis",
                "threshold": 0.50,
                "roc_auc": 0.9826,
                "pr_auc": 0.3622,
                "precision": 0.0606,
                "recall": 0.8450,
                "true_positive": 218,
                "false_positive": 3380,
                "false_negative": 40,
                "true_negative": 135900,
            },
            {
                "metric_type": "threshold_analysis",
                "threshold": 0.70,
                "roc_auc": 0.9826,
                "pr_auc": 0.3622,
                "precision": 0.0973,
                "recall": 0.7713,
                "true_positive": 199,
                "false_positive": 1846,
                "false_negative": 59,
                "true_negative": 137434,
            },
        ]
    )

    # ------------------------------------------------------------------
    # Isolation Forest validated evaluation results
    # ------------------------------------------------------------------

    isolation_forest_metrics = pd.DataFrame(
        [
            {
                "metric": "roc_auc",
                "value": 0.8198,
            },
            {
                "metric": "pr_auc",
                "value": 0.0125,
            },
            {
                "metric": "evaluation_rows",
                "value": 139538,
            },
            {
                "metric": "anomalies_detected",
                "value": 16381,
            },
            {
                "metric": "normal_transactions",
                "value": 123157,
            },
            {
                "metric": "anomaly_rate",
                "value": 0.117395,
            },
            {
                "metric": "normal_group_fraud_rate",
                "value": 0.000820,
            },
            {
                "metric": "anomaly_group_fraud_rate",
                "value": 0.009584,
            },
        ]
    )

    # ------------------------------------------------------------------
    # Validated global SHAP importance from 5,000 evaluation transactions
    # ------------------------------------------------------------------

    shap_feature_importance = pd.DataFrame(
        [
            ("amt", 3.370900),
            ("transaction_hour", 1.121264),
            ("month", 0.552961),
            ("customer_age", 0.372982),
            ("city_pop", 0.257780),
            ("day_of_week", 0.171224),
            ("long", 0.116711),
            ("lat", 0.107139),
            ("merch_lat", 0.070166),
            ("merch_long", 0.069404),
            ("distance_km", 0.063416),
        ],
        columns=[
            "feature",
            "mean_absolute_shap",
        ],
    )

    shap_feature_importance["rank"] = (
        shap_feature_importance["mean_absolute_shap"]
        .rank(
            ascending=False,
            method="min",
        )
        .astype(int)
    )

    # ------------------------------------------------------------------
    # Write Gold outputs
    # ------------------------------------------------------------------

    write_parquet(
        filesystem,
        f"{GOLD_ROOT}/xgboost_metrics.parquet",
        xgboost_metrics,
    )

    write_parquet(
        filesystem,
        f"{GOLD_ROOT}/isolation_forest_metrics.parquet",
        isolation_forest_metrics,
    )

    write_parquet(
        filesystem,
        f"{GOLD_ROOT}/shap_feature_importance.parquet",
        shap_feature_importance,
    )

    print("\n" + "=" * 80)
    print("ML GOLD OUTPUTS CREATED")
    print("=" * 80)

    print(
        f"gold/ml/xgboost_metrics.parquet"
    )

    print(
        f"gold/ml/isolation_forest_metrics.parquet"
    )

    print(
        f"gold/ml/shap_feature_importance.parquet"
    )


if __name__ == "__main__":
    main()
