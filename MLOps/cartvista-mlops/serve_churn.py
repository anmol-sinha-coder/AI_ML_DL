"""CartVista churn scoring microservice (FastAPI + MLflow registry)."""
import time, asyncio
import mlflow, mlflow.pyfunc, mlflow.sklearn, pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from mlflow import MlflowClient
import numpy as np
import pandas as pd
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
 

TRACKING_URI = "sqlite:///mlflow.db"
MODEL_NAME, ALIAS = "cartvista-churn", "champion"
PSI_GAUGE = Gauge("churn_feature_psi_tenure", "Rolling 200-request PSI for tenure_months")

app = FastAPI(title="CartVista Churn Service", version="1.0")


# Pre-compute training baseline quantiles
train_df = pd.read_csv("churn_data.csv")
expected_tenure = train_df["tenure_months"].values
bins = np.quantile(expected_tenure, np.linspace(0, 1, 11))
bins[0], bins[-1] = -np.inf, np.inf

e_counts, _ = np.histogram(expected_tenure, bins)
E_DIST = np.clip(e_counts / len(expected_tenure), 1e-4, None)

tenure_window = deque(maxlen=200)

def compute_tenure_psi(data):
    a_counts, _ = np.histogram(data, bins)
    a_dist = np.clip(a_counts / len(data), 1e-4, None)
    return float(np.sum((a_dist - E_DIST) * np.log(a_dist / E_DIST)))


# ---- typed request contract: the API *is* this class ----
class Customer(BaseModel):
    tenure_months:    int   = Field(ge=0, le=120)
    monthly_spend:    float = Field(ge=0)
    orders_per_month: int   = Field(ge=0)
    support_tickets:  int   = Field(ge=0)
    uses_discounts:   int   = Field(ge=0, le=1)
    app_sessions:     int   = Field(ge=0)
 
class BatchRequest(BaseModel):
    customers: list[Customer]
 
state = {}
@app.on_event("startup")
def load_model():
    mlflow.set_tracking_uri(TRACKING_URI)
    try:
        # state["model"] = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{ALIAS}")
        state["model"] = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@{ALIAS}")
        mv = MlflowClient().get_model_version_by_alias(MODEL_NAME, ALIAS)
        state["version"], state["run_id"] = mv.version, mv.run_id
        state["model_loaded"] = True
        print(f"Loaded {MODEL_NAME} v{mv.version} (run {mv.run_id[:8]})")
    except Exception as e:
        print(f"WARNING: Failed to load model on startup: {e}")
        state["model"] = None
        state["version"], state["run_id"] = "unknown", "none"
        state["model_loaded"] = False
 
@app.get("/health")
def health():
    return {"status": "ok" if state.get("model_loaded") else "degraded", "model_loaded": state.get("model_loaded", False)}
 
@app.get("/model-info")
def model_info():
    return {"model": MODEL_NAME, "alias": ALIAS,
            "version": state["version"], "run_id": state["run_id"]}

# --- Keep metric definitions as they are ---
PREDICTIONS = Counter("churn_predictions_total", "How many predictions, split by outcome", ["outcome"])
LATENCY = Histogram("churn_inference_seconds", "Inference latency distribution", buckets=[.005, .01, .025, .05, .1, .25])
TICKETS_IN = Gauge("churn_input_support_tickets", "support_tickets value of the last request")

 
@app.post("/predict")
def predict(customer: Customer):
    if not state.get("model_loaded"):
        raise HTTPException(status_code=503, detail="Service degraded: Model not available")
    t0 = time.perf_counter()
    df = pd.DataFrame([customer.model_dump()])
    pred = int(state["model"].predict(df)[0])
    prob = float(state["model"].predict_proba(df)[0][1])
    ms = (time.perf_counter() - t0) * 1000

    tenure_window.append(customer.tenure_months)
    if len(tenure_window) >= 50:
        PSI_GAUGE.set(compute_tenure_psi(list(tenure_window)))
        
    with LATENCY.time():
        pred = int(state["model"].predict(df)[0])
    PREDICTIONS.labels(outcome=str(pred)).inc()
    TICKETS_IN.set(customer.support_tickets)
    return {"churn_prediction": pred,
            "churn_probability": round(prob, 4),
            "model_version": state["version"],
            "inference_ms": round(ms, 2)}
 
@app.post("/predict-batch")
def predict_batch(batch: BatchRequest):
    if not batch.customers:
        raise HTTPException(422, "empty batch")
    df = pd.DataFrame([c.model_dump() for c in batch.customers])
    preds = state["model"].predict(df)
    return {"predictions": [int(p) for p in preds],
            "count": len(preds), "model_version": state["version"]}

# --- REPLACE app.mount("/metrics", make_asgi_app()) WITH THIS ROUTE ---
@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

###################################################################################

