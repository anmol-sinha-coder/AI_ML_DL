import os
import pandas as pd
import requests

DATA_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data"
SAVE_PATH = "data/heart_disease.csv"

COLUMNS = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", 
    "restecg", "thalach", "exang", "oldpeak", "slope", 
    "ca", "thal", "target"
]

def download_dataset():
    os.makedirs("data", exist_ok=True)
    print(f"Downloading dataset from {DATA_URL}...")
    df = pd.read_csv(DATA_URL, names=COLUMNS, na_values="?")
    df.to_csv(SAVE_PATH, index=False)
    print(f"Dataset saved to {SAVE_PATH}. Shape: {df.shape}")

if __name__ == "__main__":
    download_dataset()