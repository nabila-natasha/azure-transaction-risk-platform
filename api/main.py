"""Online scoring API for the transaction risk model.

Run:  API_KEY=... MODEL_RUN_ID=... uvicorn --factory api.main:create_app
"""

import json
import logging
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.model_store import Settings, load_bundle
from src.scoring import MODEL_THRESHOLD, MODEL_VERSION, score_frame

logger = logging.getLogger("risk_api")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_event(**fields):
    logger.info(json.dumps(fields, default=str))


class Transaction(BaseModel):
    """Raw transaction fields. Features are derived server-side."""

    model_config = ConfigDict(extra="forbid")

    event_time: datetime
    dob: datetime
    amt: float = Field(ge=0, le=1_000_000, allow_inf_nan=False)
    city_pop: float = Field(ge=0, le=100_000_000, allow_inf_nan=False)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    long: float = Field(ge=-180, le=180, allow_inf_nan=False)
    merch_lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    merch_long: float = Field(ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_dates(self):
        # Use wall-clock time, as the batch pipeline does (no tz conversion).
        event = self.event_time.replace(tzinfo=None)
        dob = self.dob.replace(tzinfo=None)
        if dob >= event:
            raise ValueError("dob must be earlier than event_time")
        if event - dob > timedelta(days=365.25 * 120):
            raise ValueError("customer age must be 120 years or less")
        return self


class Prediction(BaseModel):
    request_id: str
    fraud_probability: float
    predicted_fraud: int
    risk_band: str
    model_version: str
    model_run_id: str
    threshold: float


def create_app(settings=None, bundle=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        if not settings.api_key:
            raise RuntimeError("API_KEY is not set; refusing to start.")
        app.state.bundle = bundle or load_bundle(settings)
        app.state.lock = threading.Lock()
        log_event(
            event="startup",
            model_run_id=app.state.bundle.manifest.get("run_id"),
            source=app.state.bundle.source,
        )
        yield

    app = FastAPI(title="Transaction Risk Scoring API", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            bundle_ = getattr(request.app.state, "bundle", None)
            log_event(
                event="request",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=status,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
                model_run_id=bundle_.manifest.get("run_id") if bundle_ else None,
            )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # Drop "input"/"ctx" so submitted values are never echoed back.
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "request_id": getattr(request.state, "request_id", None),
                "detail": errors,
            },
        )

    def require_key(x_api_key: str = Header(default="")):
        if not secrets.compare_digest(x_api_key.encode(), settings.api_key.encode()):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/model-info", dependencies=[Depends(require_key)])
    def model_info(request: Request):
        m = request.app.state.bundle.manifest
        return {
            "model_version": MODEL_VERSION,
            "model_run_id": m.get("run_id"),
            "features": m.get("features"),
            "threshold": MODEL_THRESHOLD,
        }

    @app.post("/predict", response_model=Prediction, dependencies=[Depends(require_key)])
    def predict(txn: Transaction, request: Request):
        b = request.app.state.bundle
        frame = pd.DataFrame([{
            **txn.model_dump(),
            "event_time": txn.event_time.replace(tzinfo=None),
            "dob": txn.dob.replace(tzinfo=None),
        }])
        try:
            with request.app.state.lock:
                scored = score_frame(b.model, frame, MODEL_THRESHOLD)
        except ValueError:
            raise HTTPException(status_code=422, detail="Transaction could not be scored")
        row = scored.iloc[0]
        return Prediction(
            request_id=request.state.request_id,
            fraud_probability=float(row["fraud_probability"]),
            predicted_fraud=int(row["predicted_fraud"]),
            risk_band=str(row["risk_band"]),
            model_version=MODEL_VERSION,
            model_run_id=str(b.manifest.get("run_id")),
            threshold=MODEL_THRESHOLD,
        )

    return app
