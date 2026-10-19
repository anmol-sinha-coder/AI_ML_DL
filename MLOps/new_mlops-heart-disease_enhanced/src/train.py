"""Train, tune, evaluate and track the heart-disease classifiers.

Usage:  python -m src.train            # full hyper-parameter grids
        python -m src.train --fast     # tiny grids (smoke tests / CI speed)

Model selection: every candidate is tuned with stratified 5-fold GridSearchCV
(refit on ROC-AUC).  The champion is the candidate with the best *cross-
validated* ROC-AUC; the untouched hold-out test set is only used to report
final metrics, so it never influences selection.
"""
import argparse
import json
import logging
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import joblib  # noqa: E402
import mlflow  # noqa: E402
import mlflow.sklearn  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
import sklearn  # noqa: E402
from mlflow.models import infer_signature  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score,  # noqa: E402
                             classification_report, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402

from src.config import (CLEAN_DATA_PATH, CV_FOLDS, EXPERIMENT_NAME, MODEL_PATH,  # noqa: E402
                        RANDOM_STATE, REPORTS_DIR, TEST_SIZE, default_tracking_uri)
from src.data_processing import build_preprocessor, feature_names, load_clean, split_xy  # noqa: E402

log = logging.getLogger("train")
SCORING = ["accuracy", "precision", "recall", "roc_auc"]


def candidate_models(fast: bool = False) -> dict:
    """name -> (estimator, param grid). Grid keys are pipeline-prefixed."""
    if fast:
        lr_grid = {"classifier__C": [0.1, 1.0]}
        rf_grid = {"classifier__n_estimators": [50], "classifier__max_depth": [3, 5]}
    else:
        lr_grid = {"classifier__C": [0.01, 0.1, 1.0, 10.0]}
        rf_grid = {
            "classifier__n_estimators": [100, 200],
            "classifier__max_depth": [3, 5, 8, None],
            "classifier__min_samples_leaf": [1, 3],
        }
    return {
        "Logistic_Regression": (LogisticRegression(max_iter=2000, random_state=RANDOM_STATE), lr_grid),
        "Random_Forest": (RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=1), rf_grid),
    }


def check_tracking_server(uri: str, timeout: int = 5) -> None:
    """Fail fast with a clear message if an HTTP MLflow server is not reachable."""
    if not uri.startswith("http"):
        return
    try:
        requests.get(uri.rstrip("/") + "/health", timeout=timeout).raise_for_status()
    except Exception as exc:
        raise SystemExit(
            f"MLflow server at {uri} is not reachable ({exc}).\n"
            "Start it with `docker compose up -d mlflow`, or unset MLFLOW_TRACKING_URI "
            "to use the local ./mlruns file store.")


def _plot_roc(y_true, y_proba, name, auc, path: Path) -> None:
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, label=f"{name} (AUC = {auc:.3f})", lw=2)
    ax.plot([0, 1], [0, 1], "k--", label="Chance")
    ax.set(xlabel="False positive rate", ylabel="True positive rate", title=f"ROC curve - {name}")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_confusion(y_true, y_pred, name, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay.from_predictions(
        y_true, y_pred, display_labels=["No disease", "Disease"], cmap="Blues", ax=ax)
    ax.set_title(f"Confusion matrix - {name}")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_importance(pipe: Pipeline, name, path: Path, top: int = 15) -> None:
    clf = pipe.named_steps["classifier"]
    names = feature_names(pipe.named_steps["preprocessor"])
    values = clf.feature_importances_ if hasattr(clf, "feature_importances_") else clf.coef_.ravel()
    order = np.argsort(np.abs(values))[::-1][:top][::-1]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh([names[i] for i in order], values[order], color="#4C78A8")
    ax.set_title(f"Top {top} features - {name}")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def train_and_evaluate(clean_path: Path = CLEAN_DATA_PATH, model_path: Path = MODEL_PATH,
                       tracking_uri: str = None, fast: bool = False,
                       reports_dir: Path = REPORTS_DIR) -> dict:
    model_path = Path(model_path)
    reports_dir = Path(reports_dir)
    plots_dir = reports_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    tracking_uri = tracking_uri or default_tracking_uri()
    check_tracking_server(tracking_uri)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)

    data = load_clean(clean_path)
    X, y = split_xy(data)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y)
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    results = {}
    for name, (estimator, grid) in candidate_models(fast).items():
        pipe = Pipeline([("preprocessor", build_preprocessor()), ("classifier", estimator)])
        search = GridSearchCV(pipe, grid, scoring=SCORING, refit="roc_auc", cv=cv, n_jobs=1)

        with mlflow.start_run(run_name=name) as run:
            search.fit(X_train, y_train)
            best = search.best_estimator_
            idx = search.best_index_

            y_pred = best.predict(X_test)
            y_proba = best.predict_proba(X_test)[:, 1]
            test = {
                "test_accuracy": accuracy_score(y_test, y_pred),
                "test_precision": precision_score(y_test, y_pred),
                "test_recall": recall_score(y_test, y_pred),
                "test_roc_auc": roc_auc_score(y_test, y_proba),
            }
            cv_metrics = {}
            for m in SCORING:
                cv_metrics[f"cv_{m}"] = float(search.cv_results_[f"mean_test_{m}"][idx])
                cv_metrics[f"cv_{m}_std"] = float(search.cv_results_[f"std_test_{m}"][idx])

            best_params = {k.replace("classifier__", ""): v for k, v in search.best_params_.items()}
            mlflow.set_tags({"model_type": name, "dataset": "UCI Heart Disease (Cleveland)",
                             "selection_metric": "cv_roc_auc"})
            mlflow.log_params({**best_params, "cv_folds": CV_FOLDS, "test_size": TEST_SIZE,
                               "random_state": RANDOM_STATE, "n_rows": len(data),
                               "grid_size": len(search.cv_results_["params"])})
            mlflow.log_metrics({**cv_metrics, **test})

            roc_p = plots_dir / f"{name}_roc.png"
            cm_p = plots_dir / f"{name}_confusion_matrix.png"
            fi_p = plots_dir / f"{name}_feature_importance.png"
            _plot_roc(y_test, y_proba, name, test["test_roc_auc"], roc_p)
            _plot_confusion(y_test, y_pred, name, cm_p)
            _plot_importance(best, name, fi_p)
            for p in (roc_p, cm_p, fi_p):
                mlflow.log_artifact(str(p), "plots")
            mlflow.log_text(classification_report(y_test, y_pred, target_names=["No disease", "Disease"]),
                            "classification_report.txt")
            with tempfile.TemporaryDirectory() as tmp:
                cvp = Path(tmp) / "cv_results.csv"
                pd.DataFrame(search.cv_results_).to_csv(cvp, index=False)
                mlflow.log_artifact(str(cvp), "tuning")
            mlflow.sklearn.log_model(
                best, "model",
                signature=infer_signature(X_test, best.predict_proba(X_test)),
                input_example=X_train.head(3))

            results[name] = {"pipeline": best, "run_id": run.info.run_id, "best_params": best_params,
                             **cv_metrics, **test}
            log.info("[%s] cv_auc=%.4f test_auc=%.4f test_acc=%.4f params=%s", name,
                     cv_metrics["cv_roc_auc"], test["test_roc_auc"], test["test_accuracy"], best_params)

    champion = max(results, key=lambda n: results[n]["cv_roc_auc"])
    champ = results[champion]

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(champ["pipeline"], model_path)
    metadata = {
        "model_name": champion,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mlflow_run_id": champ["run_id"],
        "best_params": champ["best_params"],
        "metrics": {k: round(float(v), 4) for k, v in champ.items()
                    if k.startswith(("cv_", "test_"))},
        "features": list(X.columns),
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "n_training_rows": int(len(X_train)),
    }
    model_path.with_name("model_metadata.json").write_text(json.dumps(metadata, indent=2))

    with mlflow.start_run(run_id=champ["run_id"]):
        mlflow.set_tag("champion", "true")
        mlflow.log_artifact(str(model_path), "champion")
        mlflow.log_artifact(str(model_path.with_name("model_metadata.json")), "champion")

    summary = {n: {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v)
                   for k, v in r.items() if k != "pipeline"} for n, r in results.items()}
    summary["champion"] = champion
    (reports_dir / "metrics.json").write_text(json.dumps(summary, indent=2, default=str))
    log.info("Champion: %s -> %s", champion, model_path)
    return {"champion": champion, "metadata": metadata, "results": summary}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="use tiny hyper-parameter grids")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = train_and_evaluate(fast=args.fast)
    print(json.dumps(out["metadata"]["metrics"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
