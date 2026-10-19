import os
import joblib
import pandas as pd
import pytest

def test_data_file_exists():
    assert os.path.exists("data/heart_disease.csv"), "Data file missing!"

def test_model_training_output():
    assert os.path.exists("models/best_model.pkl"), "Model file missing!"

def test_model_prediction_shape():
    model = joblib.load("models/best_model.pkl")
    dummy_input = pd.DataFrame([{
        "age": 55, "sex": 1, "cp": 0, "trestbps": 130, "chol": 250,
        "fbs": 0, "restecg": 1, "thalach": 160, "exang": 0,
        "oldpeak": 1.2, "slope": 2, "ca": 0, "thal": 3
    }])
    
    pred = model.predict(dummy_input)
    proba = model.predict_proba(dummy_input)
    
    assert len(pred) == 1
    assert pred[0] in [0, 1]
    assert 0.0 <= proba[0][1] <= 1.0