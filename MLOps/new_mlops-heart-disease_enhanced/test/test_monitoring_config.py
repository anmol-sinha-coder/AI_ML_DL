"""Guards against the 'Grafana shows No data' class of bugs (bad Prometheus YAML, stale metric names)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.app import app

ROOT = Path(__file__).resolve().parent.parent
MON = ROOT / "monitoring"
PROM_TOP_LEVEL = {"global", "rule_files", "scrape_configs", "alerting", "remote_write", "remote_read", "storage"}
OPTIONAL_METRICS = {"heart_predict_errors_total"}      # only exists after the first failure


def test_prometheus_yaml_contains_only_prometheus_keys():
    cfg = yaml.safe_load((MON / "prometheus.yml").read_text())
    unknown = set(cfg) - PROM_TOP_LEVEL
    assert not unknown, f"unknown top-level keys (Grafana syntax pasted in?): {unknown}"
    assert cfg["scrape_configs"][0]["static_configs"][0]["targets"] == ["api:8000"]


def test_alert_rules_parse():
    rules = yaml.safe_load((MON / "alert_rules.yml").read_text())
    assert all("expr" in r for g in rules["groups"] for r in g["rules"])


def test_grafana_provisioning_files():
    ds = yaml.safe_load((MON / "provisioning" / "datasources" / "prometheus.yml").read_text())
    assert ds["datasources"][0]["uid"] == "prometheus"
    assert ds["datasources"][0]["url"] == "http://prometheus:9090"      # service name, not localhost
    prov = yaml.safe_load((MON / "provisioning" / "dashboards" / "prometheus.yml").read_text())
    assert prov["providers"][0]["options"]["path"] == "/var/lib/grafana/dashboards"


def test_dashboard_json_is_in_sync_with_generator(tmp_path):
    committed = json.loads((MON / "grafana_dashboard.json").read_text())
    out = subprocess.run([sys.executable, str(MON / "build_dashboard.py")], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    assert json.loads((MON / "grafana_dashboard.json").read_text()) == committed


def test_dashboard_structure():
    d = json.loads((MON / "grafana_dashboard.json").read_text())
    panels = [p for p in d["panels"] if p["type"] != "row"]
    assert len(panels) >= 35 and d["uid"] == "heart-disease-api"
    for p in panels:
        assert p["datasource"]["uid"] == "prometheus"
        assert all(t["expr"].strip() for t in p["targets"])


@pytest.fixture()
def metrics_text(trained, monkeypatch, valid_payload):
    monkeypatch.setenv("MODEL_PATH", str(trained["model_path"]))
    with TestClient(app) as c:
        c.post("/predict", json=valid_payload)
        c.post("/predict", json={"age": 1})
        yield c.get("/metrics").text


def test_every_metric_used_by_the_dashboard_is_exposed(metrics_text):
    d = json.loads((MON / "grafana_dashboard.json").read_text())
    exposed = set(re.findall(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)[{ ]", metrics_text, flags=re.M))
    used = set()
    for p in d["panels"]:
        for t in p.get("targets", []):
            used |= set(re.findall(r"\b((?:http|heart|process|python)_[a-zA-Z0-9_]+)", t["expr"]))
    missing = {m for m in used if m not in exposed and m not in OPTIONAL_METRICS}
    assert not missing, f"dashboard queries metrics the API does not expose: {sorted(missing)}"
