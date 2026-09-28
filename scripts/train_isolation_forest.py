from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import numpy as np

from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score, average_precision_score


STORAGE_ACCOUNT = "sttransactionbello"
FILESYSTEM = "synapse"
SILVER_ROOT = "silver/transactions"

RANDOM_STATE = 42
FIT_SAMPLE_SIZE = 100_000


def get_filesystem():
    credential = DefaultAzureCredential(
        exclude_shared_token_cache_credential=True
    )

    service = DataLakeServiceClient(
        account_url=f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net",
        credential=credential,
    )

    return service.get_file_system_client(FILESYSTEM)


def read_parquet(filesystem, path):
    client = filesystem.get_file_client(path)
    data = client.download_file().readall()

    table = pq.read_table(pa.BufferReader(data))
    return table.to_pandas()


def load_source(filesystem, source):
    prefix = f"{SILVER_ROOT}/{source}"

    paths = [
        item["name"]
        for item in filesystem.get_paths(
            path=prefix,
            recursive=True,
        )
        if not item["is_directory"]
        and item["name"].endswith(".parquet")
    ]

    paths.sort()

    return pd.concat(
        [read_parquet(filesystem, path) for path in paths],
        ignore_index=True,
    )


def engineer_features(df):
    df = df.copy()

    df["event_time"] = pd.to_datetime(
        df["event_time"],
        errors="coerce",
    )

    df["dob"] = pd.to_datetime(
        df["dob"],
        errors="coerce",
    )

    df["transaction_hour"] = df["event_time"].dt.hour
    df["day_of_week"] = df["event_time"].dt.dayofweek
    df["month"] = df["event_time"].dt.month

    df["customer_age"] = (
        (df["event_time"] - df["dob"]).dt.days / 365.25
    )

    lat1 = np.radians(df["lat"])
    lon1 = np.radians(df["long"])
    lat2 = np.radians(df["merch_lat"])
    lon2 = np.radians(df["merch_long"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    df["distance_km"] = (
        6371
        * 2
        * np.arcsin(np.sqrt(a))
    )

    features = [
        "amt",
        "city_pop",
        "lat",
        "long",
        "merch_lat",
        "merch_long",
        "transaction_hour",
        "day_of_week",
        "month",
        "customer_age",
        "distance_km",
    ]

    return df, features


def main():
    filesystem = get_filesystem()

    print("Loading historical batch data...")
    train = load_source(filesystem, "batch")

    print("Loading streaming evaluation data...")
    evaluation = load_source(filesystem, "streaming")

    train, features = engineer_features(train)
    evaluation, _ = engineer_features(evaluation)

    X_train = train[features]
    X_eval = evaluation[features]

    y_eval = evaluation["is_fraud"]

    print("\n" + "=" * 80)
    print("ISOLATION FOREST ANOMALY DETECTION")
    print("=" * 80)

    print(f"Training rows available:   {len(X_train):,}")
    print(f"Evaluation rows:            {len(X_eval):,}")
    print(f"Features:                   {len(features)}")

    # Use a fixed-size sample for efficient unsupervised fitting.
    sample_size = min(
        FIT_SAMPLE_SIZE,
        len(X_train),
    )

    fit_sample = X_train.sample(
        n=sample_size,
        random_state=RANDOM_STATE,
    )

    print(f"Isolation Forest fit sample: {len(fit_sample):,}")

    model = IsolationForest(
        n_estimators=200,
        max_samples=10_000,
        contamination="auto",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    print("\nTraining Isolation Forest...")

    model.fit(fit_sample)

    print("Training complete.")

    # Isolation Forest's decision_function gives higher values
    # to observations considered more normal.
    # Negating it makes higher values represent greater anomaly.
    anomaly_scores = -model.decision_function(
        X_eval
    )

    predictions = model.predict(X_eval)

    anomaly_flags = (
        predictions == -1
    ).astype(int)

    print("\n" + "=" * 80)
    print("ANOMALY RESULTS")
    print("=" * 80)

    print(
        f"Anomalies detected: "
        f"{anomaly_flags.sum():,}"
    )

    print(
        f"Normal transactions: "
        f"{(anomaly_flags == 0).sum():,}"
    )

    print(
        f"Anomaly rate: "
        f"{anomaly_flags.mean():.4%}"
    )

    # These metrics are diagnostic only.
    # Isolation Forest was NOT trained using is_fraud.
    roc_auc = roc_auc_score(
        y_eval,
        anomaly_scores,
    )

    pr_auc = average_precision_score(
        y_eval,
        anomaly_scores,
    )

    print("\nDiagnostic comparison against known fraud labels:")
    print(f"ROC-AUC: {roc_auc:.4f}")
    print(f"PR-AUC:  {pr_auc:.4f}")

    print("\nAnomaly score summary:")
    print(
        pd.Series(anomaly_scores).describe(
            percentiles=[
                0.50,
                0.90,
                0.95,
                0.99,
            ]
        )
    )

    evaluation["anomaly_score"] = anomaly_scores
    evaluation["anomaly_flag"] = anomaly_flags

    print("\nFraud rate by anomaly flag:")

    fraud_by_flag = (
        evaluation
        .groupby("anomaly_flag")["is_fraud"]
        .agg(
            transactions="count",
            fraud_count="sum",
            fraud_rate="mean",
        )
    )

    print(fraud_by_flag)

    print("\nTop 10 most anomalous transactions:")

    top_anomalies = (
        evaluation[
            [
                "event_time",
                "amt",
                "is_fraud",
                "anomaly_score",
            ]
        ]
        .sort_values(
            "anomaly_score",
            ascending=False,
        )
        .head(10)
    )

    print(
        top_anomalies.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
