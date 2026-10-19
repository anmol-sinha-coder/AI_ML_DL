"""Central configuration shared by data, training, inference and API code."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
RAW_DATA_PATH = DATA_DIR / "heart_disease.csv"          # as downloaded (target 0-4)
CLEAN_DATA_PATH = DATA_DIR / "heart_disease_clean.csv"  # cleaned (binary target)
EDA_DIR = DATA_DIR / "eda_plots"

MODEL_DIR = ROOT / "models"
MODEL_PATH = Path(os.getenv("MODEL_PATH", MODEL_DIR / "best_model.pkl"))
METADATA_PATH = MODEL_PATH.with_name("model_metadata.json")

REPORTS_DIR = ROOT / "reports"

EXPERIMENT_NAME = "Heart_Disease_Classification"
RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

COLUMNS = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal", "target",
]
NUMERIC_FEATURES = ["age", "trestbps", "chol", "thalach", "oldpeak"]
CATEGORICAL_FEATURES = ["sex", "cp", "fbs", "restecg", "exang", "slope", "ca", "thal"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "target"

# UCI Heart Disease (Cleveland subset). Several mirrors are tried in order.
DATA_URLS = [
    "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data",
    "https://archive.ics.uci.edu/static/public/45/heart+disease.zip",
]
EXPECTED_ROWS = 303


def default_tracking_uri() -> str:
    """MLflow tracking URI: env var wins, else a local file store in ./mlruns.

    A file store means training and CI work without any server running.
    """
    return os.getenv("MLFLOW_TRACKING_URI", (ROOT / "mlruns").as_uri())
