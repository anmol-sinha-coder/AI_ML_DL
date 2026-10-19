import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Heart Disease Prediction API", version="1.0")

# Instrument Prometheus Metrics
Instrumentator().instrument(app).expose(app)

MODEL_PATH = "models/best_model.pkl"

try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    model = None

class PatientData(BaseModel):
    age: float = Field(..., example=63.0)
    sex: float = Field(..., example=1.0)
    cp: float = Field(..., example=1.0)
    trestbps: float = Field(..., example=145.0)
    chol: float = Field(..., example=233.0)
    fbs: float = Field(..., example=1.0)
    restecg: float = Field(..., example=2.0)
    thalach: float = Field(..., example=150.0)
    exang: float = Field(..., example=0.0)
    oldpeak: float = Field(..., example=2.3)
    slope: float = Field(..., example=3.0)
    ca: float = Field(..., example=0.0)
    thal: float = Field(..., example=6.0)

@app.get("/health")
def health_check():
    if model is None:
        raise HTTPException(status_code=500, detail="Model unavailable")
    return {"status": "healthy", "model_loaded": True}

@app.post("/predict")
def predict(data: PatientData):
    if model is None:
        raise HTTPException(status_code=500, detail="Model missing")
    
    input_df = pd.DataFrame([data.dict()])
    prediction = int(model.predict(input_df)[0])
    confidence = float(model.predict_proba(input_df)[0][1])

    return {
        "prediction": prediction,
        "disease_risk": "High Risk" if prediction == 1 else "Low Risk",
        "confidence": round(confidence, 4)
    }