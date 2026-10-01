import pandas as pd

from sklearn.ensemble import IsolationForest
from xgboost import XGBClassifier

from scripts.prepare_ml_dataset import engineer_features

FIXTURE = "tests/fixtures/silver_transactions_sample.parquet"

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


def load_features():
    df = pd.read_parquet(FIXTURE)
    engineered, _ = engineer_features(df)
    return engineered[FEATURES]


def test_xgboost_model_smoke():
    X = load_features()

    # Deterministic synthetic target only for model smoke testing.
    y = (X["amt"] > X["amt"].median()).astype(int)

    model = XGBClassifier(
        n_estimators=10,
        max_depth=2,
        learning_rate=0.1,
        random_state=42,
        eval_metric="logloss",
        n_jobs=1,
    )

    model.fit(X, y)

    predictions = model.predict(X)

    assert len(predictions) == len(X)
    assert set(predictions).issubset({0, 1})


def test_isolation_forest_model_smoke():
    X = load_features()

    model = IsolationForest(
        n_estimators=10,
        max_samples=min(32, len(X)),
        random_state=42,
        n_jobs=1,
    )

    model.fit(X)

    predictions = model.predict(X)

    assert len(predictions) == len(X)
    assert set(predictions).issubset({-1, 1})
