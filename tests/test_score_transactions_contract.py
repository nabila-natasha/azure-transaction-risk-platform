import json

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier

from scripts import score_transactions as scoring


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


@pytest.fixture
def saved_test_model(tmp_path, monkeypatch):
    artifact_dir = tmp_path / "xgboost"
    artifact_dir.mkdir()

    rng = np.random.default_rng(42)
    X = pd.DataFrame(
        rng.random((40, len(FEATURES))),
        columns=FEATURES,
    )
    y = np.array([0, 1] * 20)

    model = XGBClassifier(
        n_estimators=3,
        max_depth=2,
        random_state=42,
        n_jobs=1,
        eval_metric="logloss",
    )
    model.fit(X, y)
    model.save_model(str(artifact_dir / "model.json"))

    manifest = {
        "run_id": "test-run",
        "features": FEATURES,
    }
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    monkeypatch.setattr(scoring, "ARTIFACT_DIR", artifact_dir)
    return artifact_dir


def test_load_saved_model_uses_matching_feature_contract(saved_test_model):
    model = scoring.load_saved_model(FEATURES)

    assert model.get_booster().feature_names == FEATURES


def test_load_saved_model_rejects_feature_mismatch(saved_test_model):
    wrong_features = FEATURES.copy()
    wrong_features[0] = "wrong_feature"

    with pytest.raises(ValueError, match="Feature contract mismatch"):
        scoring.load_saved_model(wrong_features)


def test_load_saved_model_rejects_missing_model(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"features": FEATURES}),
        encoding="utf-8",
    )
    monkeypatch.setattr(scoring, "ARTIFACT_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="Missing saved model"):
        scoring.load_saved_model(FEATURES)
