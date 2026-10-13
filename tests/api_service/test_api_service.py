import json

import numpy as np
import pandas as pd
import pytest

from src.features import FEATURES, engineer_features
from src.model_store import build_bundle, load_adls, load_local
from src.scoring import score_frame

RUN_ID = "TESTRUN"


def legacy_engineer_features(df):
    """Frozen copy of the batch-script logic, to guard against drift."""
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce")
    df["dob"] = pd.to_datetime(df["dob"], errors="coerce")
    df["transaction_hour"] = df["event_time"].dt.hour
    df["day_of_week"] = df["event_time"].dt.dayofweek
    df["month"] = df["event_time"].dt.month
    df["customer_age"] = (df["event_time"] - df["dob"]).dt.days / 365.25
    lat1, lon1 = np.radians(df["lat"].astype(float)), np.radians(df["long"].astype(float))
    lat2, lon2 = np.radians(df["merch_lat"].astype(float)), np.radians(df["merch_long"].astype(float))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    df["distance_km"] = 6371 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    return df


def test_health_needs_no_key(client):
    r = client.get("/health", headers={"X-API-Key": ""})
    assert r.status_code == 200 and r.json() == {"status": "ok"}


@pytest.mark.parametrize("key", ["", "wrong"])
def test_predict_rejects_bad_key(client, raw_frame, key, payload):
    r = client.post("/predict", json=payload(raw_frame.iloc[0]), headers={"X-API-Key": key})
    assert r.status_code == 401


def test_model_info_limited_fields(client):
    r = client.get("/model-info")
    assert r.status_code == 200
    assert set(r.json()) == {"model_version", "model_run_id", "features", "threshold"}
    assert r.json()["model_run_id"] == RUN_ID


def test_predict_shape_and_request_id(client, raw_frame, payload):
    r = client.post("/predict", json=payload(raw_frame.iloc[0]))
    assert r.status_code == 200
    body = r.json()
    assert body["request_id"] == r.headers["X-Request-ID"]
    assert 0 <= body["fraud_probability"] <= 1
    assert body["risk_band"] in {"Low", "Medium", "High"}
    assert body["model_version"] == "xgboost-v1" and body["threshold"] == 0.5


def test_api_matches_batch_scoring(client, raw_frame, model_dir, payload):
    bundle = load_local(model_dir, RUN_ID)
    legacy = legacy_engineer_features(raw_frame)
    expected = bundle.model.predict_proba(legacy[FEATURES])[:, 1]
    for i in range(len(raw_frame)):
        body = client.post("/predict", json=payload(raw_frame.iloc[i])).json()
        assert body["fraud_probability"] == pytest.approx(float(expected[i]), abs=1e-6)
        assert body["predicted_fraud"] == int(expected[i] >= 0.5)


def test_feature_module_matches_legacy(raw_frame):
    new, _ = engineer_features(raw_frame)
    old = legacy_engineer_features(raw_frame)
    pd.testing.assert_frame_equal(new[FEATURES].astype(float), old[FEATURES].astype(float))


@pytest.mark.parametrize("p,band,pred", [(0.30, "Low", 0), (0.3001, "Medium", 0),
                                         (0.50, "Medium", 1), (0.70, "Medium", 1), (0.7001, "High", 1)])
def test_band_boundaries(raw_frame, p, band, pred):
    class Fake:
        def predict_proba(self, X):
            return np.array([[1 - p, p]] * len(X))
    out = score_frame(Fake(), raw_frame.iloc[:1])
    assert out["risk_band"].iloc[0] == band and out["predicted_fraud"].iloc[0] == pred


def test_invalid_payloads_and_no_echo(client, raw_frame, payload):
    good = payload(raw_frame.iloc[0])
    bad = {**good, "amt": -5}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422
    details = json.dumps(r.json()["detail"])  # excludes the random request_id
    assert "-5" not in details and "input" not in details
    assert all(set(e) == {"loc", "msg", "type"} for e in r.json()["detail"])
    assert client.post("/predict", json={**good, "cc_num": "4111"}).status_code == 422
    missing = {k: v for k, v in good.items() if k != "dob"}
    assert client.post("/predict", json=missing).status_code == 422
    assert client.post("/predict", json={**good, "lat": 123}).status_code == 422
    assert client.post("/predict", json={**good, "dob": good["event_time"]}).status_code == 422
    assert client.post("/predict", json={**good, "dob": "1800-01-01T00:00:00"}).status_code == 422
    assert client.post("/predict", content='{"amt": NaN}',
                       headers={"content-type": "application/json"}).status_code == 422


def test_tz_aware_timestamp_uses_wall_clock(client, raw_frame, payload):
    p = payload(raw_frame.iloc[0])
    a = client.post("/predict", json=p).json()["fraud_probability"]
    b = client.post("/predict", json={**p, "event_time": p["event_time"] + "+08:00"}).json()["fraud_probability"]
    assert a == b


def test_logs_exclude_payload(client, raw_frame, caplog, payload):
    import logging
    logging.getLogger("risk_api").propagate = True
    with caplog.at_level(logging.INFO, logger="risk_api"):
        client.post("/predict", json=payload(raw_frame.iloc[0]))
    text = " ".join(caplog.messages)
    assert "request_id" in text and "latency_ms" in text
    assert "amt" not in text and "dob" not in text


def test_fails_closed_without_api_key(model_dir):
    from fastapi.testclient import TestClient
    from api.main import create_app
    from src.model_store import Settings
    with pytest.raises(RuntimeError):
        with TestClient(create_app(Settings(api_key="", model_dir=str(model_dir)))):
            pass


def test_model_contract_failures(model_dir):
    manifest = json.loads((model_dir / "manifest.json").read_text())
    data = (model_dir / "model.json").read_bytes()
    with pytest.raises(ValueError, match="run ID"):
        build_bundle(manifest, data, "t", expected_run_id="OTHER")
    with pytest.raises(ValueError, match="Feature contract"):
        build_bundle({**manifest, "features": FEATURES[::-1]}, data, "t")


class FakeFS:
    def __init__(self, files):
        self.files = files
    def get_file_client(self, path):
        outer = self
        class C:
            def download_file(self_):
                class D:
                    def readall(_):
                        return outer.files[path]
                return D()
        return C()


def test_adls_loader_with_fake_filesystem(model_dir):
    base = f"gold/ml/artifacts/xgboost/{RUN_ID}"
    fs = FakeFS({f"{base}/manifest.json": (model_dir / "manifest.json").read_bytes(),
                 f"{base}/model.json": (model_dir / "model.json").read_bytes()})
    b = load_adls(fs, "gold/ml/artifacts/xgboost", RUN_ID)
    assert b.manifest["run_id"] == RUN_ID and b.source.startswith("adls:")


# ---- startup failures: the service must refuse to run with a bad model ----

def test_startup_fails_when_artifacts_missing(tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app
    from src.model_store import Settings
    s = Settings(api_key="k", model_dir=str(tmp_path), model_run_id=RUN_ID)
    with pytest.raises(FileNotFoundError):
        with TestClient(create_app(s)):
            pass


def test_startup_fails_on_run_id_mismatch(settings):
    from fastapi.testclient import TestClient
    from api.main import create_app
    settings.model_run_id = "20261012T024013Z"  # manifest says TESTRUN
    with pytest.raises(ValueError, match="run ID"):
        with TestClient(create_app(settings)):
            pass


def test_startup_fails_on_manifest_feature_mismatch(model_dir, tmp_path):
    import shutil
    from fastapi.testclient import TestClient
    from api.main import create_app
    from src.model_store import Settings
    shutil.copy(model_dir / "model.json", tmp_path / "model.json")
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": RUN_ID, "features": FEATURES[:-1]}))
    s = Settings(api_key="k", model_dir=str(tmp_path), model_run_id=RUN_ID)
    with pytest.raises(ValueError, match="Feature contract"):
        with TestClient(create_app(s)):
            pass


def test_adls_requires_run_id():
    from src.model_store import Settings, load_bundle
    with pytest.raises(ValueError, match="MODEL_RUN_ID"):
        load_bundle(Settings(api_key="k", model_source="adls"))


# ---- the real entry point: uvicorn --factory api.main:create_app ----

def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_uvicorn(env_extra, port):
    import os, subprocess, sys
    env = {**os.environ, **env_extra}
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--factory", "api.main:create_app",
         "--host", "127.0.0.1", "--port", str(port)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def test_uvicorn_factory_starts_and_serves(model_dir, raw_frame, payload):
    import time
    import httpx
    port = _free_port()
    proc = _run_uvicorn({"API_KEY": "k", "MODEL_SOURCE": "local",
                         "MODEL_DIR": str(model_dir), "MODEL_RUN_ID": RUN_ID}, port)
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(50):
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            proc.terminate()
            out, _ = proc.communicate(timeout=10)
            raise AssertionError(
                f"server did not answer /health. uvicorn output:\\n{out}"
            )
        r = httpx.post(f"{base}/predict", json=payload(raw_frame.iloc[0]), headers={"X-API-Key": "k"})
        assert r.status_code == 200 and r.json()["model_run_id"] == RUN_ID
        assert httpx.post(f"{base}/predict", json=payload(raw_frame.iloc[0])).status_code == 401
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_uvicorn_factory_refuses_to_start_without_api_key(model_dir):
    port = _free_port()
    proc = _run_uvicorn({"API_KEY": "", "MODEL_SOURCE": "local",
                         "MODEL_DIR": str(model_dir), "MODEL_RUN_ID": RUN_ID}, port)
    out, _ = proc.communicate(timeout=30)
    assert proc.returncode != 0 and "API_KEY is not set" in out
