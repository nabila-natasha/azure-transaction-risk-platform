from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import numpy as np

from xgboost import XGBClassifier
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    confusion_matrix,
    classification_report,
)


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

    # np.radian() - converts angles from degrees to radians
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

    print("Loading training data...")
    train = load_source(filesystem, "batch")

    print("Loading evaluation data...")
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
    print("XGBOOST FRAUD MODEL")
    print("=" * 80)

    print(f"Training rows:       {len(X_train):,}")
    print(f"Evaluation rows:     {len(X_eval):,}")
    print(f"Training fraud:      {fraud:,}")
    print(f"Training non-fraud:  {non_fraud:,}")
    print(f"scale_pos_weight:    {scale_pos_weight:.2f}")

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

    print("\nTraining XGBoost...")

    model.fit(
        X_train,
        y_train,
    )

    print("Training complete.")

    probabilities = model.predict_proba(
        X_eval
    )[:, 1]

    predictions = (
        probabilities >= 0.50
    ).astype(int)

    roc_auc = roc_auc_score(
        y_eval,
        probabilities,
    )

    pr_auc = average_precision_score(
        y_eval,
        probabilities,
    )

    precision = precision_score(
        y_eval,
        predictions,
        zero_division=0,
    )

    recall = recall_score(
        y_eval,
        predictions,
        zero_division=0,
    )

    matrix = confusion_matrix(
        y_eval,
        predictions,
    )

    print("\n" + "=" * 80)
    print("EVALUATION RESULTS — THRESHOLD 0.50")
    print("=" * 80)

    print(f"ROC-AUC:    {roc_auc:.4f}")
    print(f"PR-AUC:     {pr_auc:.4f}")
    print(f"Precision:  {precision:.4f}")
    print(f"Recall:     {recall:.4f}")

    print("\nConfusion matrix:")
    print(matrix)

    print("\nClassification report:")
    print(
        classification_report(
            y_eval,
            predictions,
            digits=4,
            zero_division=0,
        )
    )

    print("\nFeature importance:")
    importance = pd.Series(
        model.feature_importances_,
        index=features,
    ).sort_values(
        ascending=False
    )

    print(
        importance.to_string()
    )

    print("\n" + "=" * 80)
    print("THRESHOLD ANALYSIS")
    print("=" * 80)

    for threshold in [0.30, 0.50, 0.70]:
        predictions = (
            probabilities >= threshold
        ).astype(int)

        precision = precision_score(
            y_eval,
            predictions,
            zero_division=0,
        )

        recall = recall_score(
            y_eval,
            predictions,
            zero_division=0,
        )

        matrix = confusion_matrix(
            y_eval,
            predictions,
        )

        tn, fp, fn, tp = matrix.ravel()

        print(f"\nThreshold: {threshold:.2f}")
        print(f"Precision:  {precision:.4f}")
        print(f"Recall:     {recall:.4f}")
        print(f"TP:         {tp:,}")
        print(f"FP:         {fp:,}")
        print(f"FN:         {fn:,}")
        print(f"TN:         {tn:,}")


if __name__ == "__main__":
    main()
