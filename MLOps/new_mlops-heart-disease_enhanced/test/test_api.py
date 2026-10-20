import json
import logging

import pytest
from fastapi.testclient import TestClient

from src.app import app


@pytest.fixture()
def client(trained, monkeypatch):
    monkeypatch.setenv("MODEL_PATH", str(trained["model_path"]))
    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "healthy"


def test_predict_returns_prediction_and_confidence(client, valid_payload):
    r = client.post("/predict", json=valid_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["prediction"] in (0, 1)
    assert 0.5 <= body["confidence"] <= 1
    assert 0 <= body["probability_disease"] <= 1
    assert body["disease_risk"] in ("High Risk", "Low Risk")
    assert r.headers["x-request-id"]


@pytest.mark.parametrize("field,value", [("age", -5), ("sex", 2), ("cp", 9), ("thal", 5),
                                         ("chol", 5000), ("age", "abc")])
def test_predict_rejects_invalid_values(client, valid_payload, field, value):
    valid_payload[field] = value
    assert client.post("/predict", json=valid_payload).status_code == 422


def test_predict_rejects_missing_field(client, valid_payload):
    del valid_payload["age"]
    assert client.post("/predict", json=valid_payload).status_code == 422


def test_model_info(client):
    assert client.get("/model-info").json()["model_name"] in ("Logistic_Regression", "Random_Forest")


def test_metrics_endpoint_exposes_custom_and_http_metrics(client, valid_payload):
    client.post("/predict", json=valid_payload)
    text = client.get("/metrics").text
    assert "heart_predictions_total" in text
    assert "heart_inference_seconds_bucket" in text
    assert "http_requests_total" in text


def test_requests_are_logged(client, valid_payload, caplog):
    logger = logging.getLogger("heart_api")
    logger.propagate = True
    with caplog.at_level(logging.INFO, logger="heart_api"):
        client.post("/predict", json=valid_payload)
    events = [json.loads(r.getMessage()) for r in caplog.records if r.name == "heart_api"]
    kinds = {e["event"] for e in events}
    assert {"request", "prediction"} <= kinds
    req = next(e for e in events if e["event"] == "request")
    assert req["path"] == "/predict" and req["status"] == 200 and "latency_ms" in req


def test_service_unavailable_without_model(tmp_path, monkeypatch, valid_payload):
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "missing.pkl"))
    with TestClient(app) as c:
        assert c.get("/health").status_code == 503
        assert c.post("/predict", json=valid_payload).status_code == 503


def test_model_and_input_metrics(client, valid_payload):
    client.post("/predict", json=valid_payload)
    text = client.get("/metrics").text
    for name in ("heart_model_loaded 1.0", "heart_model_info{", "heart_risk_band_total{", "heart_input_age_bucket",
                 "heart_input_chol_count", "http_requests_inprogress", "http_request_duration_highr_seconds_bucket"):
        assert name in text, name
    assert 'handler="/metrics"' not in text   # scraping must not pollute the traffic panels
