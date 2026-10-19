"""Exploratory data analysis: summary tables and publication-style plots.

Usage:  python -m src.eda
Outputs go to data/eda_plots/ (PNG + summary_statistics.csv).
"""
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from src.config import (CATEGORICAL_FEATURES, CLEAN_DATA_PATH, EDA_DIR,  # noqa: E402
                        NUMERIC_FEATURES, RAW_DATA_PATH, TARGET)
from src.data_processing import load_clean, load_raw  # noqa: E402

log = logging.getLogger("eda")
sns.set_theme(style="whitegrid", context="notebook")
LABELS = {0: "No disease", 1: "Disease"}
PALETTE = {"No disease": "#4C78A8", "Disease": "#E45756"}


def _save(fig, out_dir: Path, name: str) -> Path:
    path = out_dir / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_class_balance(raw: pd.DataFrame, clean: pd.DataFrame, out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    sns.countplot(x=raw[TARGET], hue=raw[TARGET], palette="viridis", legend=False, ax=axes[0])
    axes[0].set_title("Original severity label (0-4)")
    axes[0].set_xlabel("num")
    labelled = clean[TARGET].map(LABELS)
    sns.countplot(x=labelled, hue=labelled, palette=PALETTE, order=list(LABELS.values()),
                  legend=False, ax=axes[1])
    axes[1].set_title("Binary target used for modelling")
    axes[1].set_xlabel("")
    for ax in axes:
        ax.margins(y=0.12)
        for p in ax.patches:
            ax.annotate(int(p.get_height()), (p.get_x() + p.get_width() / 2, p.get_height()),
                        ha="center", va="bottom")
    return _save(fig, out_dir, "class_balance.png")


def plot_histograms(clean: pd.DataFrame, out_dir: Path) -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    data = clean.assign(label=clean[TARGET].map(LABELS))
    for ax, col in zip(axes.ravel(), NUMERIC_FEATURES):
        sns.histplot(data=data, x=col, hue="label", palette=PALETTE, bins=20,
                     kde=True, element="step", ax=ax)
        ax.set_title(f"Distribution of {col}")
    axes.ravel()[-1].axis("off")
    fig.suptitle("Numeric feature distributions by class", fontsize=14)
    return _save(fig, out_dir, "feature_histograms.png")


def plot_boxplots(clean: pd.DataFrame, out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, len(NUMERIC_FEATURES), figsize=(16, 4))
    data = clean.assign(label=clean[TARGET].map(LABELS))
    for ax, col in zip(axes, NUMERIC_FEATURES):
        sns.boxplot(data=data, x="label", y=col, hue="label", palette=PALETTE,
                    legend=False, ax=ax, order=list(LABELS.values()))
        ax.set_xlabel("")
    fig.suptitle("Outlier check: numeric features by class", fontsize=14)
    return _save(fig, out_dir, "boxplots_by_class.png")


def plot_categorical(clean: pd.DataFrame, out_dir: Path) -> Path:
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    data = clean.assign(label=clean[TARGET].map(LABELS))
    for ax, col in zip(axes.ravel(), CATEGORICAL_FEATURES):
        sns.countplot(data=data, x=col, hue="label", palette=PALETTE, ax=ax)
        ax.set_title(col)
        ax.legend(title="", fontsize=8)
    fig.suptitle("Categorical features by class", fontsize=14)
    return _save(fig, out_dir, "categorical_by_class.png")


def plot_correlation(clean: pd.DataFrame, out_dir: Path) -> Path:
    corr = clean.corr(numeric_only=True)
    mask = np.triu(np.ones_like(corr, dtype=bool))
    with sns.axes_style("white"):
        fig, ax = plt.subplots(figsize=(11, 8))
        sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="coolwarm", center=0,
                    linewidths=0.5, cbar_kws={"shrink": 0.8}, ax=ax)
    ax.set_title("Feature correlation heatmap (incl. binary target)")
    return _save(fig, out_dir, "correlation_heatmap.png")


def plot_missing(raw: pd.DataFrame, out_dir: Path) -> Path:
    miss = raw.isna().sum()
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(x=miss.index, y=miss.values, hue=miss.index, legend=False,
                palette="mako", ax=ax)
    ax.set_title("Missing values per column (handled by median / mode imputation)")
    ax.set_ylabel("count")
    ax.tick_params(axis="x", rotation=45)
    return _save(fig, out_dir, "missing_values.png")


def perform_eda(raw_path: Path = RAW_DATA_PATH, clean_path: Path = CLEAN_DATA_PATH,
                out_dir: Path = EDA_DIR) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = load_raw(raw_path)
    clean = load_clean(clean_path, raw_path)

    print("--- Shape ---", raw.shape)
    print("--- Missing values ---")
    print(raw.isna().sum()[raw.isna().sum() > 0])
    print("--- Class balance (binary) ---")
    print(clean[TARGET].value_counts(normalize=True).round(3))

    summary = clean.describe().T
    summary.to_csv(out_dir / "summary_statistics.csv")

    files = [
        plot_class_balance(raw, clean, out_dir),
        plot_histograms(clean, out_dir),
        plot_boxplots(clean, out_dir),
        plot_categorical(clean, out_dir),
        plot_correlation(clean, out_dir),
        plot_missing(raw, out_dir),
    ]
    log.info("EDA plots saved in %s", out_dir)
    return {"rows": len(clean), "plots": [str(f) for f in files]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    perform_eda()
