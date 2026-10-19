"""Data loading, cleaning, validation and the reusable preprocessing pipeline."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import (CATEGORICAL_FEATURES, CLEAN_DATA_PATH, COLUMNS,
                        FEATURES, NUMERIC_FEATURES, RAW_DATA_PATH, TARGET)

log = logging.getLogger(__name__)


def load_raw(path: Path = RAW_DATA_PATH) -> pd.DataFrame:
    """Read the raw CSV, treating '?' as missing."""
    return pd.read_csv(path, na_values="?")


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned copy of the raw frame.

    * checks all expected columns exist
    * coerces every column to numeric ('?' and junk become NaN)
    * drops exact duplicate rows
    * binarises the target (0 = no disease, 1..4 -> 1 = disease present)

    Remaining NaNs (``ca``/``thal``) are deliberately kept: they are imputed
    inside the sklearn pipeline so imputation statistics never leak from the
    test fold.
    """
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")

    out = df[COLUMNS].copy()
    for col in COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    before = len(out)
    out = out.drop_duplicates().reset_index(drop=True)
    if len(out) != before:
        log.info("Dropped %d duplicate rows", before - len(out))

    if out[TARGET].isna().any():
        raise ValueError("Target column contains missing values")
    out[TARGET] = (out[TARGET] > 0).astype(int)
    return out


def save_clean(raw_path: Path = RAW_DATA_PATH, clean_path: Path = CLEAN_DATA_PATH) -> pd.DataFrame:
    clean = clean_dataframe(load_raw(raw_path))
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(clean_path, index=False)
    return clean


def load_clean(path: Path = CLEAN_DATA_PATH, raw_path: Path = RAW_DATA_PATH) -> pd.DataFrame:
    """Load the cleaned data, creating it from the raw file if necessary."""
    path = Path(path)
    if not path.exists():
        return save_clean(raw_path, path)
    return pd.read_csv(path)


def split_xy(df: pd.DataFrame):
    return df[FEATURES], df[TARGET]


def build_preprocessor() -> ColumnTransformer:
    """Imputation + scaling for numeric, imputation + one-hot for categorical."""
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric, NUMERIC_FEATURES),
        ("cat", categorical, CATEGORICAL_FEATURES),
    ])


def feature_names(fitted_preprocessor: ColumnTransformer) -> list:
    """Names of the transformed columns (for importance / coefficient plots)."""
    return [str(n) for n in np.asarray(fitted_preprocessor.get_feature_names_out())]
