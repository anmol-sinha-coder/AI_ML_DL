import json

import joblib
import mlflow
import pandas as pd
import pytest

from src.config import FEATURES
from src.inference import predict_one
from src.train import candidate_models, check_tracking_server


def test_two_models_with_tuning_grids():
    models = candidate_models()
    assert len(models) >= 2
    assert all(grid for _, grid in models.values())


def test_training_produces_model_and_metadata(trained):
    assert trained["model_path"].exists()
    meta = json.loads(trained["model_path"].with_name("model_metadata.json").read_text())
    assert meta["features"] == FEATURES
    assert {"cv_roc_auc", "test_accuracy", "test_precision", "test_recall", "test_roc_auc"} <= set(meta["metrics"])
    assert meta["metrics"]["test_roc_auc"] > 0.6     # learnable synthetic signal


def test_saved_model_predicts_valid_probabilities(trained):
    model = joblib.load(trained["model_path"])
    X = pd.read_csv(trained["clean_path"])[FEATURES].head(5)
    proba = model.predict_proba(X)
    assert proba.shape == (5, 2)
    assert ((proba >= 0) & (proba <= 1)).all()
    assert set(model.predict(X)) <= {0, 1}


def test_model_handles_missing_values_end_to_end(trained, valid_payload):
    model = joblib.load(trained["model_path"])
    valid_payload["ca"] = float("nan")
    out = predict_one(valid_payload, model=model)
    assert 0 <= out["probability_disease"] <= 1
    assert out["confidence"] >= 0.5


def test_mlflow_logged_params_metrics_artifacts(trained):
    client = mlflow.MlflowClient(tracking_uri=(trained["root"] / "mlruns").as_uri())
    exp = client.get_experiment_by_name("Heart_Disease_Classification")
    runs = client.search_runs([exp.experiment_id])
    assert len(runs) >= 2
    for run in runs:
        assert run.data.params and "cv_roc_auc" in run.data.metrics
        assert "test_recall" in run.data.metrics
        names = {a.path for a in client.list_artifacts(run.info.run_id)}
        assert {"model", "plots"} <= names
    assert sum(r.data.tags.get("champion") == "true" for r in runs) == 1


def test_champion_has_best_cv_auc(trained):
    res = trained["result"]["results"]
    best = max((k for k in res if k != "champion"), key=lambda k: res[k]["cv_roc_auc"])
    assert trained["result"]["champion"] == best


def test_unreachable_mlflow_server_fails_fast():
    with pytest.raises(SystemExit, match="not reachable"):
        check_tracking_server("http://127.0.0.1:9", timeout=1)


def test_file_store_needs_no_server_check():
    check_tracking_server("file:///tmp/whatever")    # must not raise
