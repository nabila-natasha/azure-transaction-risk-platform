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

    frames = []

    for path in paths:
        frames.append(read_parquet(filesystem, path))

    return pd.concat(
        frames,
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

    print("Loading historical batch Silver...")
    train_df = load_source(filesystem, "batch")

    print("Loading later streaming Silver...")
    eval_df = load_source(filesystem, "streaming")

    print("\nApplying identical feature engineering...")
    train_df, features = engineer_features(train_df)
    eval_df, _ = engineer_features(eval_df)

    print("\n" + "=" * 80)
    print("CHRONOLOGICAL ML DATASET")
    print("=" * 80)

    print(f"Training rows:   {len(train_df):,}")
    print(f"Evaluation rows: {len(eval_df):,}")

    print("\nTraining period:")
    print(train_df["event_time"].min())
    print(train_df["event_time"].max())

    print("\nEvaluation period:")
    print(eval_df["event_time"].min())
    print(eval_df["event_time"].max())

    print("\nTraining fraud distribution:")
    print(
        train_df["is_fraud"]
        .value_counts()
        .to_string()
    )

    print("\nEvaluation fraud distribution:")
    print(
        eval_df["is_fraud"]
        .value_counts()
        .to_string()
    )

    print("\nTraining fraud rate:")
    print(f"{train_df['is_fraud'].mean():.4%}")

    print("\nEvaluation fraud rate:")
    print(f"{eval_df['is_fraud'].mean():.4%}")

    print("\nFeatures:")
    for feature in features:
        print(f"  {feature}")

    print("\nTraining feature null counts:")
    print(
        train_df[features]
        .isna()
        .sum()
        .to_string()
    )

    print("\nEvaluation feature null counts:")
    print(
        eval_df[features]
        .isna()
        .sum()
        .to_string()
    )


if __name__ == "__main__":
    main()
