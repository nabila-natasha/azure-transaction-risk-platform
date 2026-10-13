"""Single source of truth for the model's feature contract.

Batch scoring, training, the API and the tests should all import from here.
The logic is the same as scripts/score_transactions.py (including the clip
that guards arcsin against floating-point overshoot).
"""

import numpy as np
import pandas as pd

FEATURES = [
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

# Raw transaction fields a caller must supply; everything else is derived.
RAW_FIELDS = [
    "event_time",
    "dob",
    "amt",
    "city_pop",
    "lat",
    "long",
    "merch_lat",
    "merch_long",
]


def engineer_features(df):
    df = df.copy()

    df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce")
    df["dob"] = pd.to_datetime(df["dob"], errors="coerce")

    df["transaction_hour"] = df["event_time"].dt.hour
    df["day_of_week"] = df["event_time"].dt.dayofweek
    df["month"] = df["event_time"].dt.month

    # Age at the time of the transaction, never "today".
    df["customer_age"] = (df["event_time"] - df["dob"]).dt.days / 365.25

    lat1 = np.radians(df["lat"].astype(float))
    lon1 = np.radians(df["long"].astype(float))
    lat2 = np.radians(df["merch_lat"].astype(float))
    lon2 = np.radians(df["merch_long"].astype(float))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    a = np.clip(a, 0, 1)

    df["distance_km"] = 6371 * 2 * np.arcsin(np.sqrt(a))

    return df, list(FEATURES)
