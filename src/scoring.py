"""Scoring rules shared by batch scoring and the online API."""

import numpy as np
import pandas as pd

from src.features import engineer_features

MODEL_THRESHOLD = 0.50
MODEL_VERSION = "xgboost-v1"  # same label batch scoring writes to Gold


def score_frame(model, df, threshold=MODEL_THRESHOLD):
    """Return df with engineered features and model outputs added."""
    df, features = engineer_features(df)

    matrix = df[features].to_numpy(dtype=float)
    if not np.isfinite(matrix).all():
        raise ValueError("Features contain missing or non-finite values.")

    probabilities = model.predict_proba(df[features])[:, 1]

    df["fraud_probability"] = probabilities
    df["predicted_fraud"] = (probabilities >= threshold).astype(int)
    # Same expression as the batch script, so bands match exactly.
    df["risk_band"] = pd.cut(
        probabilities,
        bins=[-np.inf, 0.30, 0.70, np.inf],
        labels=["Low", "Medium", "High"],
    ).astype(str)
    df["model_threshold"] = threshold
    df["model_version"] = MODEL_VERSION
    return df
