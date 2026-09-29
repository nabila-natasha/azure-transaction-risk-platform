from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import numpy as np

from xgboost import XGBClassifier


STORAGE_ACCOUNT = "sttransactionbello"
FILESYSTEM = "synapse"
SILVER_ROOT = "silver/transactions"
GOLD_ROOT = "gold/ml/scored_transactions"

MODEL_THRESHOLD = 0.50
MODEL_VERSION = "xgboost-v1"


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


def train_model(train, features):
    X_train = train[features]
    y_train = train["is_fraud"]

    fraud = y_train.sum()
    non_fraud = len(y_train) - fraud

    scale_pos_weight = non_fraud / fraud

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="aucpr",
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(
        X_train,
        y_train,
    )

    return model


def main():
    filesystem = get_filesystem()

    print("Loading batch training data...")
    train = load_source(filesystem, "batch")

    print("Loading streaming evaluation data...")
    evaluation = load_source(filesystem, "streaming")

    print(
        f"Training rows:   {len(train):,}"
    )

    print(
        f"Scoring rows:     {len(evaluation):,}"
    )

    print("\nEngineering training features...")
    train, features = engineer_features(train)

    print("Engineering evaluation features...")
    evaluation, _ = engineer_features(evaluation)

    print("Training XGBoost model...")
    model = train_model(
        train,
        features,
    )

    print("Training complete.")

    print("\nScoring evaluation transactions...")

    probabilities = model.predict_proba(
        evaluation[features]
    )[:, 1]

    evaluation["fraud_probability"] = probabilities

    evaluation["predicted_fraud"] = (
        probabilities >= MODEL_THRESHOLD
    ).astype(int)

    evaluation["risk_band"] = pd.cut(
        probabilities,
        bins=[
            -np.inf,
            0.30,
            0.70,
            np.inf,
        ],
        labels=[
            "Low",
            "Medium",
            "High",
        ],
    ).astype(str)

    evaluation["model_threshold"] = (
        MODEL_THRESHOLD
    )

    evaluation["model_version"] = (
        MODEL_VERSION
    )

    output_columns = [
        "trans_num",
        "event_id",
        "event_time",
        "ingestion_time",
        "merchant",
        "category",
        "amt",
        "city",
        "state",
        "zip",
        "lat",
        "long",
        "city_pop",
        "merch_lat",
        "merch_long",
        "is_fraud",
        "fraud_probability",
        "predicted_fraud",
        "risk_band",
        "model_threshold",
        "model_version",
        "source",
    ]

    output = evaluation[
        output_columns
    ].copy()

    output_path = (
        f"{GOLD_ROOT}/scored_transactions.parquet"
    )

    print("\nWriting scored transactions...")

    table = pa.Table.from_pandas(
        output,
        preserve_index=False,
    )

    buffer = pa.BufferOutputStream()

    pq.write_table(
        table,
        buffer,
        compression="snappy",
    )

    filesystem.get_file_client(
        output_path
    ).upload_data(
        buffer.getvalue().to_pybytes(),
        overwrite=True,
    )

    print(
        f"Written successfully: {output_path}"
    )

    print(
        f"\nOutput rows: {len(output):,}"
    )

    print("\nRisk bands:")

    print(
        output["risk_band"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\nPredicted fraud:")

    print(
        output["predicted_fraud"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\nSample:")

    print(
        output[
            [
                "trans_num",
                "amt",
                "fraud_probability",
                "predicted_fraud",
                "risk_band",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
