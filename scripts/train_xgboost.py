import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
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

ARTIFACT_DIR = Path("artifacts/ml/xgboost")
THRESHOLDS = [0.30, 0.50, 0.70]


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
    return pq.read_table(pa.BufferReader(data)).to_pandas()


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

    if not paths:
        raise RuntimeError(f"No Parquet files found under {prefix}")

    return pd.concat(
        [read_parquet(filesystem, path) for path in paths],
        ignore_index=True,
    )


def engineer_features(df):
    df = df.copy()

    df["event_time"] = pd.to_datetime(
        df["event_time"], errors="coerce"
    )
    df["dob"] = pd.to_datetime(
        df["dob"], errors="coerce"
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

    # Guard against floating-point rounding outside [0, 1].
    a = np.clip(a, 0, 1)

    df["distance_km"] = 6371 * 2 * np.arcsin(np.sqrt(a))

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


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def timestamp_range(series):
    values = pd.to_datetime(series, errors="coerce").dropna()

    if values.empty:
        return {"start": None, "end": None}

    return {
        "start": values.min().isoformat(),
        "end": values.max().isoformat(),
    }


def calculate_threshold_metrics(y_true, probabilities, threshold):
    predictions = (probabilities >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        predictions,
        labels=[0, 1],
    ).ravel()

    return {
        "threshold": threshold,
        "precision": float(
            precision_score(y_true, predictions, zero_division=0)
        ),
        "recall": float(
            recall_score(y_true, predictions, zero_division=0)
        ),
        "true_positive": int(tp),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_negative": int(tn),
    }


def main():
    run_started = datetime.now(timezone.utc)
    run_id = run_started.strftime("%Y%m%dT%H%M%SZ")

    print("Connecting to ADLS...")
    filesystem = get_filesystem()

    print("Loading historical batch Silver...")
    train = load_source(filesystem, "batch")

    print("Loading later streaming Silver...")
    evaluation = load_source(filesystem, "streaming")

    train, features = engineer_features(train)
    evaluation, evaluation_features = engineer_features(evaluation)

    if features != evaluation_features:
        raise ValueError("Training and evaluation feature lists differ.")

    X_train = train[features]
    y_train = train["is_fraud"].astype(int)
    X_eval = evaluation[features]
    y_eval = evaluation["is_fraud"].astype(int)

    if y_train.nunique() < 2:
        raise ValueError("Training data must contain both target classes.")

    if y_eval.nunique() < 2:
        raise ValueError("Evaluation data must contain both target classes.")

    fraud = int(y_train.sum())
    non_fraud = int(len(y_train) - fraud)

    if fraud == 0:
        raise ValueError("Training data contains no fraud-positive rows.")

    scale_pos_weight = non_fraud / fraud

    parameters = {
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "scale_pos_weight": scale_pos_weight,
        "random_state": 42,
        "n_jobs": -1,
    }

    print("\n" + "=" * 70)
    print("XGBOOST FRAUD MODEL")
    print("=" * 70)
    print(f"Training rows:      {len(X_train):,}")
    print(f"Evaluation rows:    {len(X_eval):,}")
    print(f"Training fraud:     {fraud:,}")
    print(f"Training non-fraud: {non_fraud:,}")
    print(f"scale_pos_weight:   {scale_pos_weight:.2f}")

    model = XGBClassifier(**parameters)

    print("\nTraining XGBoost...")
    model.fit(X_train, y_train)
    print("Training complete.")

    probabilities = model.predict_proba(X_eval)[:, 1]

    roc_auc = roc_auc_score(y_eval, probabilities)
    pr_auc = average_precision_score(y_eval, probabilities)

    threshold_results = {
        str(threshold): calculate_threshold_metrics(
            y_eval, probabilities, threshold
        )
        for threshold in THRESHOLDS
    }

    predictions_050 = (
        probabilities >= 0.50
    ).astype(int)

    feature_importance = {
        name: float(value)
        for name, value in zip(
            features,
            model.feature_importances_,
        )
    }

    metrics = {
        "run_id": run_id,
        "evaluation_rows": int(len(y_eval)),
        "evaluation_fraud_rows": int(y_eval.sum()),
        "evaluation_fraud_rate": float(y_eval.mean()),
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "threshold_metrics": threshold_results,
        "feature_importance": feature_importance,
        "classification_report": classification_report(
            y_eval,
            predictions_050,
            output_dict=True,
            zero_division=0,
        ),
    }

    predictions_df = pd.DataFrame({
        "event_time": evaluation["event_time"].reset_index(drop=True),
        "y_true": y_eval.reset_index(drop=True),
        "fraud_probability": probabilities,
        "prediction_at_030": (probabilities >= 0.30).astype(int),
        "prediction_at_050": (probabilities >= 0.50).astype(int),
        "prediction_at_070": (probabilities >= 0.70).astype(int),
    })

    manifest = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "storage_account": STORAGE_ACCOUNT,
        "filesystem": FILESYSTEM,
        "training_source": f"{SILVER_ROOT}/batch",
        "evaluation_source": f"{SILVER_ROOT}/streaming",
        "training_rows": int(len(train)),
        "evaluation_rows": int(len(evaluation)),
        "training_period": timestamp_range(train["event_time"]),
        "evaluation_period": timestamp_range(evaluation["event_time"]),
        "training_fraud_rows": fraud,
        "training_non_fraud_rows": non_fraud,
        "training_fraud_rate": float(y_train.mean()),
        "evaluation_fraud_rate": float(y_eval.mean()),
        "features": features,
        "model_type": "XGBClassifier",
        "model_parameters": parameters,
        "default_report_threshold": 0.50,
        "thresholds_reported": THRESHOLDS,
        "metrics_file": "metrics.json",
        "model_file": "model.json",
        "predictions_file": "predictions.parquet",
        "notes": (
            "Evaluation metrics are calculated from this run's predictions. "
            "The streaming period is used for evaluation, not threshold tuning."
        ),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    model.save_model(str(ARTIFACT_DIR / "model.json"))

    with (ARTIFACT_DIR / "metrics.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(metrics, file, indent=2, allow_nan=False)

    with (ARTIFACT_DIR / "manifest.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(manifest, file, indent=2, allow_nan=False)

    predictions_df.to_parquet(
        ARTIFACT_DIR / "predictions.parquet",
        index=False,
    )

    print("\n" + "=" * 70)
    print("EVALUATION RESULTS — THRESHOLD 0.50")
    print("=" * 70)
    print(f"ROC-AUC:   {roc_auc:.4f}")
    print(f"PR-AUC:    {pr_auc:.4f}")
    print(f"Precision: {threshold_results['0.5']['precision']:.4f}")
    print(f"Recall:    {threshold_results['0.5']['recall']:.4f}")

    print("\nThreshold analysis:")
    for threshold, result in threshold_results.items():
        print(
            f"Threshold {float(threshold):.2f} | "
            f"Precision {result['precision']:.4f} | "
            f"Recall {result['recall']:.4f} | "
            f"TP {result['true_positive']:,} | "
            f"FP {result['false_positive']:,} | "
            f"FN {result['false_negative']:,} | "
            f"TN {result['true_negative']:,}"
        )

    print("\nArtifacts saved:")
    for path in sorted(ARTIFACT_DIR.iterdir()):
        print(f"  {path} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
