"""Load and validate a pinned model artifact (local files or ADLS)."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from xgboost import XGBClassifier

from src.features import FEATURES

# The run this service is pinned to unless MODEL_RUN_ID overrides it.
PINNED_RUN_ID = "20261012T024013Z"


@dataclass
class ModelBundle:
    model: object
    manifest: dict
    source: str


def build_bundle(manifest, model_bytes, source, expected_run_id=None):
    if expected_run_id and manifest.get("run_id") != expected_run_id:
        raise ValueError(
            f"Model run ID mismatch: expected {expected_run_id}, "
            f"got {manifest.get('run_id')}"
        )

    if manifest.get("features") != FEATURES:
        raise ValueError(
            "Feature contract mismatch. "
            f"Manifest: {manifest.get('features')}; service: {FEATURES}"
        )

    model = XGBClassifier()
    model.load_model(bytearray(model_bytes))

    saved = model.get_booster().feature_names
    if saved is not None and saved != FEATURES:
        raise ValueError(f"Saved model feature names differ: {saved}")

    return ModelBundle(model=model, manifest=manifest, source=source)


def load_local(model_dir, expected_run_id=None):
    model_dir = Path(model_dir)
    manifest_path = model_dir / "manifest.json"
    model_path = model_dir / "model.json"

    for path in (manifest_path, model_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing model artifact: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return build_bundle(
        manifest,
        model_path.read_bytes(),
        source=f"local:{model_dir}",
        expected_run_id=expected_run_id,
    )


def load_adls(filesystem, artifact_root, run_id):
    """filesystem is an azure-storage-file-datalake FileSystemClient."""
    base = f"{artifact_root}/{run_id}"
    manifest = json.loads(
        filesystem.get_file_client(f"{base}/manifest.json").download_file().readall()
    )
    model_bytes = (
        filesystem.get_file_client(f"{base}/model.json").download_file().readall()
    )
    return build_bundle(
        manifest, model_bytes, source=f"adls:{base}", expected_run_id=run_id
    )


def get_adls_filesystem(account, filesystem):
    # Imported lazily so the API runs without Azure packages or access.
    from azure.identity import DefaultAzureCredential
    from azure.storage.filedatalake import DataLakeServiceClient

    credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
    service = DataLakeServiceClient(
        account_url=f"https://{account}.dfs.core.windows.net",
        credential=credential,
    )
    return service.get_file_system_client(filesystem)


@dataclass
class Settings:
    api_key: str
    model_source: str = "local"  # "local" or "adls"
    model_dir: str = "artifacts/ml/xgboost"
    model_run_id: str = ""
    adls_account: str = "sttransactionbello"
    adls_filesystem: str = "synapse"
    adls_artifact_root: str = "gold/ml/artifacts/xgboost"

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.environ.get("API_KEY", ""),
            model_source=os.environ.get("MODEL_SOURCE", "local"),
            model_dir=os.environ.get("MODEL_DIR", "artifacts/ml/xgboost"),
            model_run_id=os.environ.get("MODEL_RUN_ID", PINNED_RUN_ID),
            adls_account=os.environ.get("ADLS_ACCOUNT", "sttransactionbello"),
            adls_filesystem=os.environ.get("ADLS_FILESYSTEM", "synapse"),
            adls_artifact_root=os.environ.get(
                "ADLS_ARTIFACT_ROOT", "gold/ml/artifacts/xgboost"
            ),
        )


def load_bundle(settings):
    if settings.model_source == "local":
        return load_local(settings.model_dir, settings.model_run_id or None)
    if settings.model_source == "adls":
        if not settings.model_run_id:
            raise ValueError("MODEL_RUN_ID is required when MODEL_SOURCE=adls")
        fs = get_adls_filesystem(settings.adls_account, settings.adls_filesystem)
        return load_adls(fs, settings.adls_artifact_root, settings.model_run_id)
    raise ValueError(f"Unknown MODEL_SOURCE: {settings.model_source}")
