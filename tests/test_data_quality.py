import numpy as np
import pandas as pd

from scripts.prepare_ml_dataset import engineer_features

FIXTURE = "tests/fixtures/silver_transactions_sample.parquet"

ML_FEATURES = [
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


def load_fixture():
    return pd.read_parquet(FIXTURE)


def test_ml_features_have_no_missing_values():
    df = load_fixture()
    engineered, features = engineer_features(df)
    assert engineered[features].notna().all().all()


def test_ml_features_are_numeric():
    df = load_fixture()
    engineered, features = engineer_features(df)

    for feature in features:
        assert pd.api.types.is_numeric_dtype(engineered[feature])


def test_ml_features_are_finite():
    df = load_fixture()
    engineered, _ = engineer_features(df)
    values = engineered[ML_FEATURES].to_numpy()
    assert np.isfinite(values).all()


def test_geographic_coordinates_are_valid():
    df = load_fixture()

    assert df["lat"].between(-90, 90).all()
    assert df["merch_lat"].between(-90, 90).all()
    assert df["long"].between(-180, 180).all()
    assert df["merch_long"].between(-180, 180).all()


def test_transaction_amounts_are_non_negative():
    df = load_fixture()
    assert (df["amt"] >= 0).all()
