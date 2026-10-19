"""Download the UCI Heart Disease (Cleveland) dataset and build the cleaned CSV.

Usage:  python -m src.download_data

If the UCI site is unreachable and a raw CSV already exists locally, the
existing file is reused so the pipeline still runs offline.
"""
import io
import logging
import sys
import zipfile

import pandas as pd
import requests

from src.config import (COLUMNS, DATA_URLS, EXPECTED_ROWS, RAW_DATA_PATH)
from src.data_processing import save_clean

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("download_data")


def _read_payload(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            with zf.open("processed.cleveland.data") as fh:
                return pd.read_csv(fh, names=COLUMNS, na_values="?")
    return pd.read_csv(io.StringIO(resp.text), names=COLUMNS, na_values="?")


def download_dataset() -> pd.DataFrame:
    RAW_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    for url in DATA_URLS:
        try:
            log.info("Downloading %s", url)
            df = _read_payload(url)
            if df.shape != (EXPECTED_ROWS, len(COLUMNS)):
                raise ValueError(f"Unexpected shape {df.shape}")
            df.to_csv(RAW_DATA_PATH, index=False)
            log.info("Raw dataset saved to %s %s", RAW_DATA_PATH, df.shape)
            return df
        except Exception as exc:  # network, parse or shape problems
            log.warning("Source failed (%s): %s", url, exc)

    if RAW_DATA_PATH.exists():
        log.warning("All sources failed; reusing existing %s", RAW_DATA_PATH)
        return pd.read_csv(RAW_DATA_PATH)
    raise SystemExit("Could not download the dataset and no local copy exists. "
                     "Download processed.cleveland.data manually from "
                     "https://archive.ics.uci.edu/dataset/45/heart+disease "
                     f"and save it with a header row as {RAW_DATA_PATH}")


def main() -> int:
    download_dataset()
    clean = save_clean()
    log.info("Cleaned dataset written (%d rows, target balance: %s)",
             len(clean), clean["target"].value_counts().to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
