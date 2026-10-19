import time
import random
import requests
import sys

API_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

high_risk_patient = {
    "age": 67.0, "sex": 1.0, "cp": 4.0, "trestbps": 160.0,
    "chol": 286.0, "fbs": 0.0, "restecg": 2.0, "thalach": 108.0,
    "exang": 1.0, "oldpeak": 1.5, "slope": 2.0, "ca": 3.0, "thal": 3.0
}

low_risk_patient = {
    "age": 37.0, "sex": 1.0, "cp": 3.0, "trestbps": 130.0,
    "chol": 250.0, "fbs": 0.0, "restecg": 0.0, "thalach": 187.0,
    "exang": 0.0, "oldpeak": 0.0, "slope": 1.0, "ca": 0.0, "thal": 3.0
}

invalid_payload = {"age": "invalid_type", "sex": 1.0}

def generate_traffic(duration_seconds=120):
    print(f"--> Generating automated API traffic against {API_URL} for {duration_seconds} seconds...")
    start_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        choice = random.choices(
            ["high_risk", "low_risk", "health", "invalid"], 
            weights=[40, 40, 15, 5]
        )[0]
        
        try:
            if choice == "high_risk":
                res = requests.post(f"{API_URL}/predict", json=high_risk_patient)
            elif choice == "low_risk":
                res = requests.post(f"{API_URL}/predict", json=low_risk_patient)
            elif choice == "health":
                res = requests.get(f"{API_URL}/health")
            elif choice == "invalid":
                res = requests.post(f"{API_URL}/predict", json=invalid_payload)

            print(f"[{choice.upper()}] HTTP {res.status_code}")
        except Exception as e:
            print(f"Request failed: {e}")

        time.sleep(random.uniform(0.1, 0.4))

if __name__ == "__main__":
    generate_traffic(180)