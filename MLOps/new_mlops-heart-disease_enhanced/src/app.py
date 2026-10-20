"""Heart-disease prediction API (FastAPI).

Endpoints
  POST /predict     -> {"prediction", "disease_risk", "probability_disease", "confidence", ...}
  GET  /health      -> liveness/readiness (503 if the model is not loaded)
  GET  /model-info  -> metadata of the served model
  GET  /metrics     -> Prometheus metrics (HTTP + custom prediction metrics)

Every request is logged (JSON line: id, method, path, status, latency) to stdout
and, when writable, to logs/api.log. Prediction inputs/outputs are logged too.
"""
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

from src.config import FEATURES, MODEL_PATH, ROOT

# ----------------------------------------------------------------- logging
logger = logging.getLogger("heart_api")


def setup_logging() -> None:
    """Idempotent logger setup: stdout always, rotating file if possible."""
    if logger.handlers:
        return
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    fmt = logging.Formatter("%(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    log_file = Path(os.getenv("LOG_FILE", ROOT / "logs" / "api.log"))
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        logger.warning(json.dumps({"event": "log_file_unavailable", "path": str(log_file)}))


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **fields}))


# ----------------------------------------------------------------- metrics
PREDICTIONS = Counter("heart_predictions_total", "Predictions served, by predicted class", ["outcome"])
PROBABILITY = Histogram("heart_prediction_probability", "Distribution of P(disease)",
                        buckets=[.1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0])
INFERENCE_SECONDS = Histogram("heart_inference_seconds", "Model inference latency",
                              buckets=[.001, .005, .01, .025, .05, .1, .25, .5])
PREDICT_ERRORS = Counter("heart_predict_errors_total", "Failed prediction calls", ["reason"])
RISK_BANDS = Counter("heart_risk_band_total", "Predictions by risk band (P<0.33 low, <0.66 medium)", ["band"])
MODEL_LOADED = Gauge("heart_model_loaded", "1 if the model is loaded and serving")
MODEL_INFO = Gauge("heart_model_info", "Served model metadata (value is always 1)",
                   ["model_name", "sklearn_version", "mlflow_run_id"])
# Input-feature distributions: lets Grafana show data drift against the training data
INPUT_AGE = Histogram("heart_input_age", "Patient age in requests", buckets=[30, 40, 50, 60, 70, 80, 120])
INPUT_CHOL = Histogram("heart_input_chol", "Cholesterol in requests",
                       buckets=[150, 200, 250, 300, 350, 400, 700])
INPUT_TRESTBPS = Histogram("heart_input_trestbps", "Resting BP in requests",
                           buckets=[100, 120, 140, 160, 180, 200, 300])
INPUT_THALACH = Histogram("heart_input_thalach", "Max heart rate in requests",
                          buckets=[80, 100, 120, 140, 160, 180, 250])


# ----------------------------------------------------------------- schema
class PatientData(BaseModel):
    """Cleveland feature encoding; ranges reject obviously invalid input."""
    age: float = Field(..., ge=1, le=120, examples=[63.0], description="Age in years")
    sex: float = Field(..., ge=0, le=1, examples=[1.0], description="1 = male, 0 = female")
    cp: float = Field(..., ge=1, le=4, examples=[1.0], description="Chest pain type (1-4)")
    trestbps: float = Field(..., ge=50, le=300, examples=[145.0], description="Resting BP (mm Hg)")
    chol: float = Field(..., ge=50, le=700, examples=[233.0], description="Serum cholesterol (mg/dl)")
    fbs: float = Field(..., ge=0, le=1, examples=[1.0], description="Fasting blood sugar > 120 mg/dl")
    restecg: float = Field(..., ge=0, le=2, examples=[2.0], description="Resting ECG result (0-2)")
    thalach: float = Field(..., ge=30, le=250, examples=[150.0], description="Max heart rate achieved")
    exang: float = Field(..., ge=0, le=1, examples=[0.0], description="Exercise-induced angina")
    oldpeak: float = Field(..., ge=0, le=10, examples=[2.3], description="ST depression")
    slope: float = Field(..., ge=1, le=3, examples=[3.0], description="Slope of peak exercise ST (1-3)")
    ca: float = Field(..., ge=0, le=4, examples=[0.0], description="Major vessels coloured (0-4)")
    thal: float = Field(..., examples=[6.0], description="3 normal, 6 fixed defect, 7 reversible defect")

    @field_validator("thal")
    @classmethod
    def thal_valid(cls, v: float) -> float:
        if v not in (3.0, 6.0, 7.0):
            raise ValueError("thal must be one of 3, 6, 7")
        return v


class PredictionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    prediction: int
    disease_risk: str
    probability_disease: float
    confidence: float
    model_name: str


# ----------------------------------------------------------------- app
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    app.state.model = None
    app.state.metadata = {}
    path = Path(os.getenv("MODEL_PATH", MODEL_PATH))
    try:
        app.state.model = joblib.load(path)
        meta_path = path.with_name("model_metadata.json")
        if meta_path.exists():
            app.state.metadata = json.loads(meta_path.read_text())
        MODEL_LOADED.set(1)
        MODEL_INFO.clear()
        MODEL_INFO.labels(model_name=str(app.state.metadata.get("model_name", "unknown")),
                          sklearn_version=str(app.state.metadata.get("sklearn_version", "unknown")),
                          mlflow_run_id=str(app.state.metadata.get("mlflow_run_id", "unknown"))[:8]).set(1)
        log_event("model_loaded", path=str(path), model=app.state.metadata.get("model_name", "unknown"))
    except Exception as exc:  # keep the process alive so /health can report it
        MODEL_LOADED.set(0)
        log_event("model_load_failed", path=str(path), error=str(exc))
    yield


app = FastAPI(title="Heart Disease Prediction API", version="2.0", lifespan=lifespan)
Instrumentator(
    excluded_handlers=["/metrics"],
    should_instrument_requests_inprogress=True,
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
).instrument(app).expose(app, include_in_schema=False)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    finally:
        if request.url.path != "/metrics":
            log_event("request", request_id=request_id, method=request.method,
                      path=request.url.path, status=status,
                      latency_ms=round((time.perf_counter() - start) * 1000, 2),
                      client=request.client.host if request.client else None)


@app.get("/health")
def health_check(request: Request):
    if request.app.state.model is None:
        raise HTTPException(status_code=503, detail="Model unavailable")
    return {"status": "healthy", "model_loaded": True}


@app.get("/model-info")
def model_info(request: Request):
    if request.app.state.model is None:
        raise HTTPException(status_code=503, detail="Model unavailable")
    return request.app.state.metadata or {"model_name": "unknown"}


@app.post("/predict", response_model=PredictionResponse)
def predict(data: PatientData, request: Request):
    model = request.app.state.model
    if model is None:
        PREDICT_ERRORS.labels(reason="model_missing").inc()
        raise HTTPException(status_code=503, detail="Model unavailable")

    frame = pd.DataFrame([data.model_dump()], columns=FEATURES)
    start = time.perf_counter()
    try:
        proba = float(model.predict_proba(frame)[0][1])
    except Exception as exc:
        PREDICT_ERRORS.labels(reason="inference_error").inc()
        log_event("predict_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Inference failed")
    INFERENCE_SECONDS.observe(time.perf_counter() - start)

    prediction = int(proba >= 0.5)
    outcome = "disease" if prediction == 1 else "no_disease"
    PREDICTIONS.labels(outcome=outcome).inc()
    PROBABILITY.observe(proba)
    RISK_BANDS.labels(band="low" if proba < 0.33 else "medium" if proba < 0.66 else "high").inc()
    INPUT_AGE.observe(data.age)
    INPUT_CHOL.observe(data.chol)
    INPUT_TRESTBPS.observe(data.trestbps)
    INPUT_THALACH.observe(data.thalach)
    confidence = proba if prediction == 1 else 1 - proba
    log_event("prediction", input=data.model_dump(), prediction=prediction,
              probability_disease=round(proba, 4))
    return PredictionResponse(
        prediction=prediction,
        disease_risk="High Risk" if prediction == 1 else "Low Risk",
        probability_disease=round(proba, 4),
        confidence=round(confidence, 4),
        model_name=request.app.state.metadata.get("model_name", "unknown"),
    )
