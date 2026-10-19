"""Shared fixtures: a synthetic, network-free dataset and a tiny trained model."""
import numpy as np
import pandas as pd
import pytest

from src.config import COLUMNS


def make_synthetic_heart(n: int = 200, seed: int = 0, with_missing: bool = True) -> pd.DataFrame:
    """Random data with Cleveland-style encodings and a learnable target (0-4)."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "age": rng.integers(30, 78, n).astype(float),
        "sex": rng.integers(0, 2, n).astype(float),
        "cp": rng.integers(1, 5, n).astype(float),
        "trestbps": rng.normal(130, 15, n).round(),
        "chol": rng.normal(245, 45, n).round(),
        "fbs": rng.integers(0, 2, n).astype(float),
        "restecg": rng.integers(0, 3, n).astype(float),
        "thalach": rng.normal(150, 20, n).round(),
        "exang": rng.integers(0, 2, n).astype(float),
        "oldpeak": rng.gamma(1.2, 0.9, n).round(1),
        "slope": rng.integers(1, 4, n).astype(float),
        "ca": rng.integers(0, 4, n).astype(float),
        "thal": rng.choice([3.0, 6.0, 7.0], n),
    })
    risk = 0.8 * (df["cp"] == 4) + 0.6 * df["exang"] + 0.5 * df["oldpeak"] + 0.5 * df["ca"] \
        - 0.02 * (df["thalach"] - 150) + rng.normal(0, 0.6, n)
    df["target"] = np.where(risk > np.median(risk), rng.integers(1, 5, n), 0)
    if with_missing:
        df.loc[df.sample(5, random_state=seed).index, "ca"] = np.nan
        df.loc[df.sample(3, random_state=seed + 1).index, "thal"] = np.nan
    return df[COLUMNS]


@pytest.fixture(scope="session")
def synthetic_raw():
    return make_synthetic_heart()


@pytest.fixture(scope="session")
def trained(tmp_path_factory, synthetic_raw):
    """Run the real training code on synthetic data (tiny grids, file MLflow store)."""
    from src.train import train_and_evaluate
    root = tmp_path_factory.mktemp("train")
    raw = root / "raw.csv"
    synthetic_raw.to_csv(raw, index=False)
    from src.data_processing import save_clean
    clean_path = root / "clean.csv"
    save_clean(raw, clean_path)
    model_path = root / "models" / "best_model.pkl"
    result = train_and_evaluate(clean_path=clean_path, model_path=model_path,
                                tracking_uri=(root / "mlruns").as_uri(), fast=True,
                                reports_dir=root / "reports")
    return {"result": result, "model_path": model_path, "root": root, "clean_path": clean_path}


@pytest.fixture()
def valid_payload():
    return {"age": 63, "sex": 1, "cp": 1, "trestbps": 145, "chol": 233, "fbs": 1,
            "restecg": 2, "thalach": 150, "exang": 0, "oldpeak": 2.3, "slope": 3,
            "ca": 0, "thal": 6}
