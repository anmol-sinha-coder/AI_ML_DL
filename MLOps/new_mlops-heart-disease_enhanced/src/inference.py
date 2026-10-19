"""Standalone inference check against the saved model (no API needed).

Usage:  python -m src.inference
        python -m src.inference --json '{"age": 55, ...}'
"""
import argparse
import json
import sys

import joblib
import pandas as pd

from src.config import FEATURES, MODEL_PATH

SAMPLE_PATIENT = {
    "age": 63.0, "sex": 1.0, "cp": 1.0, "trestbps": 145.0, "chol": 233.0,
    "fbs": 1.0, "restecg": 2.0, "thalach": 150.0, "exang": 0.0,
    "oldpeak": 2.3, "slope": 3.0, "ca": 0.0, "thal": 6.0,
}


def predict_one(record: dict, model=None) -> dict:
    """Score a single patient dict; returns label, probabilities and confidence."""
    model = model or joblib.load(MODEL_PATH)
    frame = pd.DataFrame([record], columns=FEATURES)
    proba = float(model.predict_proba(frame)[0][1])
    pred = int(proba >= 0.5)
    return {
        "prediction": pred,
        "probability_disease": round(proba, 4),
        "confidence": round(proba if pred == 1 else 1 - proba, 4),
    }


def run_inference(record: dict = None) -> dict:
    result = predict_one(record or SAMPLE_PATIENT)
    print("--- Inference Output ---")
    print(f"Prediction: {'Heart Disease' if result['prediction'] == 1 else 'Normal'}")
    print(f"P(disease): {result['probability_disease']:.4f} | confidence: {result['confidence']:.4f}")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="patient record as a JSON string")
    a = ap.parse_args()
    run_inference(json.loads(a.json) if a.json else None)
    sys.exit(0)
