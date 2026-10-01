import pandas as pd

from scripts.prepare_ml_dataset import engineer_features as prepare_features
from scripts.train_xgboost import engineer_features as xgboost_features
from scripts.train_isolation_forest import (
    engineer_features as isolation_features,
)


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


def test_all_ml_scripts_use_same_feature_contract():
    df = load_fixture()

    _, prepare = prepare_features(df)
    _, xgboost = xgboost_features(df)
    _, isolation = isolation_features(df)

    assert prepare == EXPECTED_FEATURES
    assert xgboost == EXPECTED_FEATURES
    assert isolation == EXPECTED_FEATURES


def test_all_ml_scripts_produce_same_feature_values():
    df = load_fixture()

    prepared_df, _ = prepare_features(df)
    xgboost_df, _ = xgboost_features(df)
    isolation_df, _ = isolation_features(df)

    for feature in EXPECTED_FEATURES:
        pd.testing.assert_series_equal(
            prepared_df[feature],
            xgboost_df[feature],
            check_names=False,
        )

        pd.testing.assert_series_equal(
            prepared_df[feature],
            isolation_df[feature],
            check_names=False,
        )
