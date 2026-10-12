import asyncio, os, pathlib, time, traceback, json, csv
import pandas as pd, mlflow, mlflow.sklearn, sqlalchemy.orm
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from mlflow import MlflowClient
import mlflow.tracking._model_registry.utils as reg_utils, mlflow.tracking._tracking_service.utils as track_utils

PROJECT_DIR = pathlib.Path(__file__).parent.resolve()
TRACKING_URI = f"sqlite:///{PROJECT_DIR}/mlflow.db"
MODEL_NAME, ALIAS = "cartvista-churn", "champion"

app = FastAPI(title="CartVista Churn Service", version="1.0")

class Customer(BaseModel):
    tenure_months: int = Field(ge=0, le=120)
    monthly_spend: float = Field(ge=0)
    orders_per_month: int = Field(ge=0)
    support_tickets: int = Field(ge=0)
    uses_discounts: int = Field(ge=0, le=1)
    app_sessions: int = Field(ge=0)

class BatchRequest(BaseModel):
    customers: list[Customer]

state = {
    "model": None,
    "version": "unknown",
    "run_id": "none",
    "model_loaded": False
}

def load_model_from_registry():
    db_path = TRACKING_URI.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        print(f"[WAITING] Database missing at {db_path}. Pausing check...")
        state["model_loaded"] = False
        return

    print("[TRACE] 1. DB found. Configuring SQLAlchemy connection...")
    # timeout=2 tells SQLite to instantly throw an error if the file is locked, rather than hanging.
    cache_buster = int(time.time() * 1000)
    fresh_uri = f"sqlite:///{db_path}?timeout=2&cache_buster={cache_buster}"
    
    mlflow.set_tracking_uri(fresh_uri)
    client = MlflowClient(tracking_uri=fresh_uri)
    
    try:
        print(f"[TRACE] 2. Fetching alias '{ALIAS}'...")
        mv = client.get_model_version_by_alias(MODEL_NAME, ALIAS)
        current_version = str(mv.version)
        print(f"[TRACE] 3. Alias found (v{current_version}). Checking if update is needed...")
        
        if state["version"] != current_version or state["model"] is None:
            print(f"[LOADING] 4. Fetching artifacts for v{current_version}...")
            model_uri = f"models:/{MODEL_NAME}@{ALIAS}"
            new_model = mlflow.sklearn.load_model(model_uri)
            
            state["model"] = new_model
            state["version"] = current_version
            state["run_id"] = str(mv.run_id)
            state["model_loaded"] = True
            print(f"[HOT-SWAP SUCCESS] 5. Active model is now v{current_version}")
        else:
            ## BUG FIX: If the DB is restored and the model is already in memory,
            # we must explicitly re-enable the API!
            if not state["model_loaded"]:
                print(f"[RECOVERY SUCCESS] Database reconnected. Resuming API traffic for v{current_version}.")
                state["model_loaded"] = True
            else:
                print("[TRACE] Model is already up to date.")
            
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Registry check failed: {type(e).__name__} - {e}")
        state["model_loaded"] = False


async def poll_model_updates():
    """Background worker checking mlflow.db every 5 seconds with a strict timeout."""
    while True:
        await asyncio.sleep(5)
        try:
            # Enforce a strict 4-second timeout. If SQLite deadlocks, this forcibly kills the check.
            await asyncio.wait_for(asyncio.to_thread(load_model_from_registry), timeout=4.0)
        except asyncio.TimeoutError:
            print("[TIMEOUT ERROR] MLflow thread deadlocked while reading the DB. Forcing a retry on the next tick...")
            state["model_loaded"] = False
        except Exception as e:
            print(f"[POLL FATAL ERROR] {e}")
            state["model_loaded"] = False

@app.on_event("startup")
async def startup_event():
    load_model_from_registry()
    asyncio.create_task(poll_model_updates())

@app.get("/health")
def health():
    return {
        "status": "ok" if state["model_loaded"] else "degraded", 
        "model_loaded": state["model_loaded"]
    }

@app.post("/predict")
def predict(customer: Customer):
    if not state["model_loaded"] or state["model"] is None:
        raise HTTPException(status_code=503, detail="Service degraded: Model not loaded")
    
    t0 = time.perf_counter()
    df = pd.DataFrame([customer.model_dump()])
    
    pred = int(state["model"].predict(df)[0])
    
    prob = None
    if hasattr(state["model"], "predict_proba"):
        prob = round(float(state["model"].predict_proba(df)[0][1]), 4)
        
    ms = (time.perf_counter() - t0) * 1000
    
    res = {
        "churn_prediction": pred,
        "model_version": state["version"],
        "inference_ms": round(ms, 2)
    }
    if prob is not None:
        res["churn_probability"] = prob
    return res

@app.post("/predict-batch")
def predict_batch(batch: BatchRequest):
    if not state["model_loaded"] or state["model"] is None:
        raise HTTPException(status_code=503, detail="Service degraded: Model not loaded")
    if not batch.customers:
        raise HTTPException(status_code=422, detail="Empty batch")
        
    t0 = time.perf_counter()
    df = pd.DataFrame([c.model_dump() for c in batch.customers])
    preds = state["model"].predict(df)
    
    ms = (time.perf_counter() - t0) * 1000
    return {
        "predictions": [int(p) for p in preds],
        "count": len(preds),
        "model_version": state["version"],
        "inference_ms": round(ms, 2)
    }
