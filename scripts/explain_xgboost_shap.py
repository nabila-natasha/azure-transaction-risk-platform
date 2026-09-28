from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import numpy as np
import shap

from xgboost import XGBClassifier


STORAGE_ACCOUNT = "sttransactionbello"
FILESYSTEM = "synapse"
SILVER_ROOT = "silver/transactions"

RANDOM_STATE = 42
SHAP_SAMPLE_SIZE = 5_000


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
    y_train = train["is_fraud"]

    X_eval = evaluation[features]
    y_eval = evaluation["is_fraud"]

    fraud = y_train.sum()
    non_fraud = len(y_train) - fraud

    scale_pos_weight = non_fraud / fraud

    print("\n" + "=" * 80)
    print("XGBOOST SHAP EXPLANATIONS")
    print("=" * 80)

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="aucpr",
        scale_pos_weight=scale_pos_weight,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    print("Training XGBoost...")

    model.fit(
        X_train,
        y_train,
    )

    print("Training complete.")

    sample_size = min(
        SHAP_SAMPLE_SIZE,
        len(X_eval),
    )

    shap_sample = X_eval.sample(
        n=sample_size,
        random_state=RANDOM_STATE,
    )

    print(
        f"Calculating SHAP values for "
        f"{sample_size:,} evaluation transactions..."
    )

    explainer = shap.TreeExplainer(model)

    shap_values = explainer.shap_values(
        shap_sample
    )

    print("SHAP calculation complete.")

    print("\n" + "=" * 80)
    print("GLOBAL SHAP IMPORTANCE")
    print("=" * 80)

    mean_abs_shap = pd.Series(
        np.abs(shap_values).mean(axis=0),
        index=features,
    ).sort_values(
        ascending=False
    )

    print(
        mean_abs_shap.to_string()
    )

    # Calculate fraud probability for the SHAP sample.
    probabilities = model.predict_proba(
        shap_sample
    )[:, 1]

    shap_results = shap_sample.copy()

    shap_results["fraud_probability"] = probabilities

    shap_results["actual_fraud"] = (
        y_eval.loc[shap_sample.index]
        .values
    )

    shap_results["mean_abs_shap"] = (
        np.abs(shap_values).sum(axis=1)
    )

    print("\n" + "=" * 80)
    print("TOP 10 HIGHEST FRAUD-PROBABILITY TRANSACTIONS")
    print("=" * 80)

    top_transactions = (
        shap_results[
            [
                "fraud_probability",
                "actual_fraud",
                "amt",
                "transaction_hour",
                "customer_age",
                "distance_km",
            ]
        ]
        .sort_values(
            "fraud_probability",
            ascending=False,
        )
        .head(10)
    )

    print(
        top_transactions.to_string(
            index=False
        )
    )

    print("\n" + "=" * 80)
    print("TOP SHAP CONTRIBUTORS FOR HIGHEST-PROBABILITY TRANSACTION")
    print("=" * 80)

    top_index = np.argmax(probabilities)

    local_shap = pd.DataFrame(
        {
            "feature": features,
            "feature_value": shap_sample.iloc[
                top_index
            ].values,
            "shap_value": shap_values[
                top_index
            ],
        }
    )

    local_shap["absolute_shap"] = (
        local_shap["shap_value"].abs()
    )

    print(
        local_shap
        .sort_values(
            "absolute_shap",
            ascending=False,
        )
        .drop(
            columns=["absolute_shap"]
        )
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
