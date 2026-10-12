from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
import pyarrow.parquet as pq
import argparse
import json
from pathlib import Path

import pyarrow as pa
import pandas as pd
import numpy as np

from xgboost import XGBClassifier


STORAGE_ACCOUNT = "sttransactionbello"
FILESYSTEM = "synapse"

SILVER_ROOT = "silver/transactions"
GOLD_ROOT = "gold/ml/scored_transactions"
ARTIFACT_DIR = Path("artifacts/ml/xgboost")

MODEL_THRESHOLD = 0.50
MODEL_VERSION = "xgboost-v1"


def get_filesystem():
    credential = DefaultAzureCredential(
        exclude_shared_token_cache_credential=True
    )

    service = DataLakeServiceClient(
        account_url=(
            f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net"
        ),
        credential=credential,
    )

    return service.get_file_system_client(
        FILESYSTEM
    )


def read_parquet(filesystem, path):
    client = filesystem.get_file_client(path)

    data = (
        client
        .download_file()
        .readall()
    )

    table = pq.read_table(
        pa.BufferReader(data)
    )

    return table.to_pandas()


def load_source(filesystem, source):
    prefix = f"{SILVER_ROOT}/{source}"

    paths = [
        item["name"]
        for item in filesystem.get_paths(
            path=prefix,
            recursive=True,
        )
        if (
            not item["is_directory"]
            and item["name"].endswith(".parquet")
        )
    ]

    paths.sort()

    return pd.concat(
        [
            read_parquet(
                filesystem,
                path,
            )
            for path in paths
        ],
        ignore_index=True,
    )


def engineer_features(df):
    df = df.copy()

    # --------------------------------------------------------------
    # Datetime fields
    # --------------------------------------------------------------

    df["event_time"] = pd.to_datetime(
        df["event_time"],
        errors="coerce",
    )

    df["dob"] = pd.to_datetime(
        df["dob"],
        errors="coerce",
    )

    # --------------------------------------------------------------
    # Temporal features
    # --------------------------------------------------------------

    df["transaction_hour"] = (
        df["event_time"].dt.hour
    )

    df["day_of_week"] = (
        df["event_time"].dt.dayofweek
    )

    df["month"] = (
        df["event_time"].dt.month
    )

    # --------------------------------------------------------------
    # Customer age
    # --------------------------------------------------------------

    df["customer_age"] = (
        (
            df["event_time"]
            - df["dob"]
        ).dt.days
        / 365.25
    )

    # --------------------------------------------------------------
    # Customer-to-merchant geographic distance
    # --------------------------------------------------------------

    lat1 = np.radians(
        df["lat"].astype(float)
    )

    lon1 = np.radians(
        df["long"].astype(float)
    )

    lat2 = np.radians(
        df["merch_lat"].astype(float)
    )

    lon2 = np.radians(
        df["merch_long"].astype(float)
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    a = np.clip(a, 0, 1)

    df["distance_km"] = (
        6371
        * 2
        * np.arcsin(
            np.sqrt(a)
        )
    )

    # --------------------------------------------------------------
    # Exact model feature contract
    # --------------------------------------------------------------

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


def load_saved_model(features):
    manifest_path = ARTIFACT_DIR / "manifest.json"
    model_path = ARTIFACT_DIR / "model.json"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing model manifest: {manifest_path}")
    if not model_path.is_file():
        raise FileNotFoundError(f"Missing saved model: {model_path}")

    with manifest_path.open(encoding="utf-8") as file:
        manifest = json.load(file)

    if manifest.get("features") != features:
        raise ValueError(
            "Feature contract mismatch. "
            f"Manifest: {manifest.get('features')}; scoring: {features}"
        )

    model = XGBClassifier()
    model.load_model(str(model_path))

    saved_features = model.get_booster().feature_names
    if saved_features is not None and saved_features != features:
        raise ValueError(
            f"Saved model feature names differ: {saved_features}"
        )

    print(f"Loaded saved model: {model_path}")
    print(f"Model run ID: {manifest.get('run_id')}")
    print(f"Validated feature count: {len(features)}")

    return model


def main():
    parser = argparse.ArgumentParser(
        description="Score streaming transactions with the saved XGBoost model."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate scoring output without writing to Gold.",
    )
    args = parser.parse_args()

    filesystem = get_filesystem()

    print("Loading streaming evaluation data...")
    evaluation = load_source(filesystem, "streaming")

    print(f"Scoring rows: {len(evaluation):,}")

    print("\nEngineering evaluation features...")
    evaluation, features = engineer_features(evaluation)

    model = load_saved_model(features)

    # Score
    # --------------------------------------------------------------

    print(
        "\nScoring evaluation transactions..."
    )

    probabilities = model.predict_proba(
        evaluation[features]
    )[:, 1]

    evaluation["fraud_probability"] = (
        probabilities
    )

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

    # --------------------------------------------------------------
    # Gold serving contract
    # --------------------------------------------------------------

    output_columns = [

        # Transaction identity / timing
        "trans_num",
        "event_id",
        "event_time",
        "ingestion_time",

        # Customer / transaction context
        "merchant",
        "category",
        "amt",
        "first",
        "last",
        "gender",
        "street",
        "city",
        "state",
        "zip",
        "dob",

        # Original geographic features
        "lat",
        "long",
        "city_pop",
        "merch_lat",
        "merch_long",

        # Engineered model features
        "transaction_hour",
        "day_of_week",
        "month",
        "customer_age",
        "distance_km",

        # Ground truth
        "is_fraud",

        # Model outputs
        "fraud_probability",
        "predicted_fraud",
        "risk_band",

        # Model metadata
        "model_threshold",
        "model_version",

        # Source metadata
        "source",
    ]

    output = evaluation[
        output_columns
    ].copy()

    # --------------------------------------------------------------
    # Validate output contract before any write
    if len(output.columns) != 32:
        raise ValueError(
            f"Expected 32 Gold columns, got {len(output.columns)}"
        )

    if output.columns.duplicated().any():
        raise ValueError("Duplicate columns found in scoring output.")

    probabilities_check = output["fraud_probability"].to_numpy(dtype=float)

    if not np.isfinite(probabilities_check).all():
        raise ValueError("Fraud probabilities contain non-finite values.")

    if not output["fraud_probability"].between(0, 1).all():
        raise ValueError("Fraud probabilities fall outside [0, 1].")

    if args.dry_run:
        print("\nDRY RUN: Gold was NOT modified.")
        print(f"Would write: {GOLD_ROOT}/scored_transactions.parquet")
    else:
        output_path = f"{GOLD_ROOT}/scored_transactions.parquet"

        print("\nWriting scored transactions...")
        table = pa.Table.from_pandas(output, preserve_index=False)
        buffer = pa.BufferOutputStream()
        pq.write_table(table, buffer, compression="snappy")

        filesystem.get_file_client(output_path).upload_data(
            buffer.getvalue().to_pybytes(),
            overwrite=True,
        )

        print(f"Written successfully: {output_path}")

    print(f"\nOutput rows: {len(output):,}")

    # --------------------------------------------------------------

    # Verification
    # --------------------------------------------------------------

    print(
        "\nOutput columns:"
    )

    for column in output.columns:
        print(
            f"  - {column}"
        )

    print(
        "\nRisk bands:"
    )

    print(
        output["risk_band"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print(
        "\nPredicted fraud:"
    )

    print(
        output["predicted_fraud"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print(
        "\nRequired engineered features:"
    )

    required_features = [
        "dob",
        "transaction_hour",
        "day_of_week",
        "month",
        "customer_age",
        "distance_km",
    ]

    for column in required_features:
        print(
            f"  - {column}: "
            f"{'OK' if column in output.columns else 'MISSING'}"
        )

    print(
        "\nSample:"
    )

    print(
        output[
            [
                "trans_num",
                "amt",
                "transaction_hour",
                "customer_age",
                "distance_km",
                "fraud_probability",
                "predicted_fraud",
                "risk_band",
            ]
        ]
        .head(10)
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
