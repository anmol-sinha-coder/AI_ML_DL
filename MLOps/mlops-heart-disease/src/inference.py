import joblib
import pandas as pd

def run_inference():
    model = joblib.load("models/best_model.pkl")
    
    sample_patient = pd.DataFrame([{
        "age": 63.0,
        "sex": 1.0,
        "cp": 1.0,
        "trestbps": 145.0,
        "chol": 233.0,
        "fbs": 1.0,
        "restecg": 2.0,
        "thalach": 150.0,
        "exang": 0.0,
        "oldpeak": 2.3,
        "slope": 3.0,
        "ca": 0.0,
        "thal": 6.0
    }])
    
    prediction = model.predict(sample_patient)[0]
    probabilities = model.predict_proba(sample_patient)[0]
    
    print("--- Inference Output ---")
    print(f"Prediction: {'Heart Disease' if prediction == 1 else 'Normal'}")
    print(f"Confidence (Probability of Disease): {probabilities[1]:.4f}")

if __name__ == "__main__":
    run_inference()