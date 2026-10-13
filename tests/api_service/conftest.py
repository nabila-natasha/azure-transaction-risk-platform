"""Fixtures for the API tests. SYNTHETIC model only - not your real model."""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from xgboost import XGBClassifier

from api.main import create_app
from src.features import FEATURES, engineer_features
from src.model_store import Settings

API_KEY = "test-key"
RUN_ID = "TESTRUN"
NUMERIC = ["amt", "city_pop", "lat", "long", "merch_lat", "merch_long"]


def synthetic_raw(n=300, seed=0):
    rng = np.random.default_rng(seed)
    event = pd.Timestamp("2020-12-01") + pd.to_timedelta(rng.integers(0, 30 * 86400, n), unit="s")
    dob = pd.Timestamp("1950-01-01") + pd.to_timedelta(rng.integers(0, 15000, n), unit="D")
    lat = rng.uniform(25, 48, n)
    long = rng.uniform(-120, -75, n)
    return pd.DataFrame({
        "event_time": event, "dob": dob,
        "amt": rng.gamma(2, 40, n), "city_pop": rng.integers(500, 3_000_000, n).astype(float),
        "lat": lat, "long": long,
        "merch_lat": lat + rng.normal(0, 0.5, n), "merch_long": long + rng.normal(0, 0.5, n),
    })


def to_payload(row):
    return {"event_time": row["event_time"].isoformat(), "dob": row["dob"].isoformat(),
            **{k: float(row[k]) for k in NUMERIC}}


@pytest.fixture(scope="session")
def model_dir(tmp_path_factory):
    df, feats = engineer_features(synthetic_raw())
    y = ((df["amt"] > 120) | (df["distance_km"] > 60)).astype(int)
    model = XGBClassifier(n_estimators=20, max_depth=3, eval_metric="logloss")
    model.fit(df[feats], y)
    d = tmp_path_factory.mktemp("model")
    model.save_model(d / "model.json")
    (d / "manifest.json").write_text(json.dumps({"run_id": RUN_ID, "features": FEATURES}))
    return d


@pytest.fixture(scope="session")
def raw_frame():
    return synthetic_raw(60, seed=1)


@pytest.fixture()
def settings(model_dir):
    return Settings(api_key=API_KEY, model_source="local",
                    model_dir=str(model_dir), model_run_id=RUN_ID)


@pytest.fixture()
def client(settings):
    with TestClient(create_app(settings)) as c:
        c.headers.update({"X-API-Key": API_KEY})
        yield c


@pytest.fixture()
def payload():
    return to_payload
