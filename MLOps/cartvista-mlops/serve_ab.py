import random
import pandas as pd
import time
import mlflow
import mlflow.pyfunc
from fastapi import FastAPI, Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST, Histogram

TRACKING_URI = "sqlite:///mlflow.db"
MODEL_NAME = "cartvista-churn"
SPLIT = 0.10  # 10% traffic to challenger
LATENCY = Histogram(
    "ab_inference_seconds",
    "Inference latency by model variant",
    ["variant"],
    buckets=[.001, .005, .01, .025, .05, .1]
)

# 1. Input Validation Schema (Reused from Lab 3)
class Customer(BaseModel):
    tenure_months: int = Field(ge=0, le=120)
    monthly_spend: float = Field(ge=0)
    orders_per_month: int = Field(ge=0)
    support_tickets: int = Field(ge=0)
    uses_discounts: int = Field(ge=0, le=1)
    app_sessions: int = Field(ge=0)

# 2. Prometheus Metric
AB_PRED = Counter(
    "ab_predictions_total",
    "predictions by variant and outcome",
    ["variant", "outcome"]
)

app = FastAPI(title="CartVista A/B Router")
state = {}

@app.on_event("startup")
def load():
    mlflow.set_tracking_uri(TRACKING_URI)
    state["champion"] = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
    state["challenger"] = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@challenger")

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/predict")
def predict(customer: Customer):
    variant = "challenger" if random.random() < SPLIT else "champion"
    df = pd.DataFrame([customer.model_dump()])

    start_time = time.perf_counter()
    pred = int(state[variant].predict(df)[0])
    duration = time.perf_counter() - start_time
    
    LATENCY.labels(variant=variant).observe(duration)
    AB_PRED.labels(variant=variant, outcome=str(pred)).inc()
    
    try:
        if variant=="challenger":
            chall_pred = int(state[variant].predict(df)[0])
            AB_PRED.labels(variant="challenger_shadow", outcome=str(chall_pred)).inc()
    except Exception:
        pass  # Prevent shadow failures from affecting production responses
    return {"churn_prediction": pred, "variant": variant}
