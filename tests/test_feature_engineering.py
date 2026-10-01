import numpy as np
import pandas as pd

from scripts.prepare_ml_dataset import engineer_features


FIXTURE = "tests/fixtures/silver_transactions_sample.parquet"

EXPECTED_FEATURES = [
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


def test_fixture_has_required_source_columns():
    df = load_fixture()

    required = {
        "event_time",
        "dob",
        "amt",
        "city_pop",
        "lat",
        "long",
        "merch_lat",
        "merch_long",
    }

    assert required.issubset(df.columns)
    assert len(df) > 0


def test_feature_contract():
    df = load_fixture()

    _, features = engineer_features(df)

    assert features == EXPECTED_FEATURES
    assert len(features) == 11


def test_temporal_features_are_created():
    df = load_fixture()

    result, _ = engineer_features(df)

    assert result["transaction_hour"].between(0, 23).all()
    assert result["day_of_week"].between(0, 6).all()
    assert result["month"].between(1, 12).all()


def test_customer_age_is_created():
    df = load_fixture()

    result, _ = engineer_features(df)

    assert "customer_age" in result.columns

    valid_age = result["customer_age"].dropna()

    assert len(valid_age) > 0
    assert (valid_age >= 0).all()
    assert (valid_age < 120).all()


def test_distance_is_created_and_non_negative():
    df = load_fixture()

    result, _ = engineer_features(df)

    assert "distance_km" in result.columns

    valid_distance = result["distance_km"].dropna()

    assert len(valid_distance) > 0
    assert (valid_distance >= 0).all()


def test_feature_values_are_finite():
    df = load_fixture()

    result, features = engineer_features(df)

    feature_matrix = result[features]

    assert np.isfinite(feature_matrix.to_numpy()).all()


def test_input_dataframe_is_not_modified():
    df = load_fixture()
    original = df.copy(deep=True)

    engineer_features(df)

    pd.testing.assert_frame_equal(df, original)
