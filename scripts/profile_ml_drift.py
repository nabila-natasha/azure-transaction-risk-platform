from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import numpy as np


STORAGE_ACCOUNT = "sttransactionbello"
FILESYSTEM = "synapse"
SILVER_ROOT = "silver/transactions"


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

    return df


def main():
    filesystem = get_filesystem()

    print("Loading historical batch data...")
    train = load_source(filesystem, "batch")

    print("Loading December streaming data...")
    evaluation = load_source(filesystem, "streaming")

    train = engineer_features(train)
    evaluation = engineer_features(evaluation)

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

    print("\n" + "=" * 80)
    print("ML FEATURE DRIFT DIAGNOSTICS")
    print("=" * 80)

    print("\nTraining period:")
    print(train["event_time"].min())
    print(train["event_time"].max())

    print("\nEvaluation period:")
    print(evaluation["event_time"].min())
    print(evaluation["event_time"].max())

    print("\nFeature distribution comparison:")
    print("-" * 80)

    rows = []

    for feature in features:
        train_mean = train[feature].mean()
        eval_mean = evaluation[feature].mean()

        train_median = train[feature].median()
        eval_median = evaluation[feature].median()

        train_std = train[feature].std()
        eval_std = evaluation[feature].std()

        mean_change_pct = (
            (eval_mean - train_mean)
            / train_mean
            * 100
            if train_mean != 0
            else np.nan
        )

        rows.append(
            {
                "feature": feature,
                "train_mean": train_mean,
                "eval_mean": eval_mean,
                "mean_change_pct": mean_change_pct,
                "train_median": train_median,
                "eval_median": eval_median,
                "train_std": train_std,
                "eval_std": eval_std,
            }
        )

    comparison = pd.DataFrame(rows)

    print(
        comparison.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print("\n" + "=" * 80)
    print("FRAUD RATE COMPARISON")
    print("=" * 80)

    train_fraud_rate = train["is_fraud"].mean()
    eval_fraud_rate = evaluation["is_fraud"].mean()

    print(
        f"Training fraud rate:   {train_fraud_rate:.4%}"
    )

    print(
        f"Evaluation fraud rate: {eval_fraud_rate:.4%}"
    )

    print(
        f"Absolute change:       "
        f"{eval_fraud_rate - train_fraud_rate:.4%}"
    )

    print("\n" + "=" * 80)
    print("DIAGNOSTIC NOTE")
    print("=" * 80)

    print(
        "These comparisons are descriptive diagnostics only."
    )
    print(
        "They are not production drift monitoring and do not "
        "automatically trigger retraining."
    )


if __name__ == "__main__":
    main()
