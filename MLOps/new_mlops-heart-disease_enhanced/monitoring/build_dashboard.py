#!/usr/bin/env python3
"""Generate monitoring/grafana_dashboard.json (Grafana 10.x, Prometheus datasource uid "prometheus").

Usage:  python3 monitoring/build_dashboard.py
Edit the panel definitions below and re-run; the JSON is picked up by Grafana provisioning within ~10 s.
"""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}
SEL = 'job=~"fastapi-ml-app.*", deployment=~"$deployment", instance=~"$instance"'      # common label filter
RI = "$__rate_interval"

_id = 0
panels = []
_y = 0


def _next_id():
    global _id
    _id += 1
    return _id


def target(expr, legend="", **kw):
    t = {"refId": kw.pop("ref", "A"), "datasource": DS, "expr": expr, "legendFormat": legend}
    t.update(kw)
    return t


def row(title):
    global _y
    panels.append({"id": _next_id(), "type": "row", "title": title, "collapsed": False,
                   "gridPos": {"x": 0, "y": _y, "w": 24, "h": 1}, "panels": []})
    _y += 1


def place(x, w, h):
    return {"x": x, "y": _y, "w": w, "h": h}


def stat(title, expr, x, w=4, unit="short", thresholds=None, decimals=None, desc="", color_mode="value", instant=False):
    steps = thresholds or [{"color": "green", "value": None}]
    defaults = {"unit": unit, "thresholds": {"mode": "absolute", "steps": steps},
                "color": {"mode": "thresholds"}}
    if decimals is not None:
        defaults["decimals"] = decimals
    panels.append({
        "id": _next_id(), "type": "stat", "title": title, "description": desc, "datasource": DS,
        "gridPos": place(x, w, 4),
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": color_mode, "graphMode": "area", "textMode": "auto", "orientation": "auto"},
        "targets": [target(expr, instant=instant, range=not instant)],
    })


def ts(title, targets, x, w=12, h=8, unit="short", stack=False, desc="", fill=12, minimum=None, legend_calcs=None):
    custom = {"drawStyle": "line", "lineWidth": 2, "fillOpacity": fill, "showPoints": "never",
              "spanNulls": True, "stacking": {"mode": "normal" if stack else "none", "group": "A"}}
    defaults = {"unit": unit, "custom": custom}
    if minimum is not None:
        defaults["min"] = minimum
    panels.append({
        "id": _next_id(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
        "gridPos": place(x, w, h),
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "bottom", "showLegend": True,
                               "calcs": legend_calcs or ["mean", "max"]},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
        "targets": targets,
    })


def pie(title, expr, legend, x, w=6, h=8, desc=""):
    panels.append({
        "id": _next_id(), "type": "piechart", "title": title, "description": desc, "datasource": DS,
        "gridPos": place(x, w, h),
        "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "pieType": "donut", "legend": {"displayMode": "table", "placement": "right",
                                                   "showLegend": True, "values": ["value", "percent"]}},
        "targets": [target(expr, legend, instant=True, range=False)],
    })


def bars(title, expr, legend, x, w=6, h=8, desc="", unit="short"):
    panels.append({
        "id": _next_id(), "type": "bargauge", "title": title, "description": desc, "datasource": DS,
        "gridPos": place(x, w, h),
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "continuous-BlPu"}, "min": 0},
                        "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True},
        "targets": [target(expr, legend, instant=True, range=False)],
    })


def table(title, targets, x, w=12, h=8, desc="", transformations=None):
    panels.append({
        "id": _next_id(), "type": "table", "title": title, "description": desc, "datasource": DS,
        "gridPos": place(x, w, h),
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {"showHeader": True, "cellHeight": "sm"},
        "transformations": transformations or [],
        "targets": targets,
    })


def heatmap(title, expr, x, w=12, h=8, desc=""):
    panels.append({
        "id": _next_id(), "type": "heatmap", "title": title, "description": desc, "datasource": DS,
        "gridPos": place(x, w, h),
        "fieldConfig": {"defaults": {"custom": {"scaleDistribution": {"type": "linear"}}}, "overrides": []},
        "options": {"calculate": False, "yAxis": {"unit": "s", "axisPlacement": "left"},
                    "color": {"scheme": "Oranges", "mode": "scheme", "fill": "dark-orange", "steps": 64},
                    "cellGap": 1, "legend": {"show": True}, "tooltip": {"show": True}},
        "targets": [target(expr, "{{le}}", format="heatmap")],
    })


def advance(h):
    global _y
    _y += h


# ----------------------------------------------------------------------------- Overview
row("Overview")
thr_ok_bad = [{"color": "red", "value": None}, {"color": "green", "value": 1}]
stat("Targets up", f'sum(up{{job=~"fastapi-ml-app.*", deployment=~"$deployment"}})', 0, unit="none",
     thresholds=thr_ok_bad, desc="Scrape targets Prometheus can reach (1 per running API deployment)")
stat("Request rate", f'sum(rate(http_requests_total{{{SEL}}}[{RI}]))', 4, unit="reqps", decimals=2)
stat("Total requests (range)", f'sum(increase(http_requests_total{{{SEL}}}[$__range]))', 8, unit="short", decimals=0)
stat("Error ratio (4xx+5xx)",
     f'sum(rate(http_requests_total{{{SEL}, status=~"4xx|5xx"}}[{RI}])) / clamp_min(sum(rate(http_requests_total{{{SEL}}}[{RI}])), 0.0001)',
     12, unit="percentunit", decimals=1,
     thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 0.05}, {"color": "red", "value": 0.2}])
stat("Latency p95", f'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_highr_seconds_bucket{{{SEL}}}[{RI}])))',
     16, unit="s", decimals=3,
     thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 0.25}, {"color": "red", "value": 0.5}])
stat("Predictions (range)", f'sum(increase(heart_predictions_total{{{SEL}}}[$__range]))', 20, unit="short", decimals=0)
advance(4)
stat("High-risk share",
     f'sum(increase(heart_predictions_total{{{SEL}, outcome="disease"}}[$__range])) / clamp_min(sum(increase(heart_predictions_total{{{SEL}}}[$__range])), 1)',
     0, unit="percentunit", decimals=1, desc="Share of predictions classified as heart disease")
stat("Mean P(disease)",
     f'sum(increase(heart_prediction_probability_sum{{{SEL}}}[$__range])) / clamp_min(sum(increase(heart_prediction_probability_count{{{SEL}}}[$__range])), 1)',
     4, unit="percentunit", decimals=1)
stat("Model loaded", f'min(heart_model_loaded{{{SEL}}})', 8, unit="none",
     thresholds=thr_ok_bad, desc="1 = model loaded on every selected instance")
stat("In-flight requests", f'sum(http_requests_inprogress{{{SEL}}})', 12, unit="none", decimals=0)
stat("Uptime (oldest instance)", f'max(time() - process_start_time_seconds{{{SEL}}})', 16, unit="s", decimals=0)
stat("Active alerts", 'count(ALERTS{alertstate="firing"}) or vector(0)', 20, unit="none", decimals=0,
     thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}])
advance(4)

# ----------------------------------------------------------------------------- Traffic
row("Traffic")
ts("Request rate by endpoint", [target(f'sum by (handler) (rate(http_requests_total{{{SEL}}}[{RI}]))', "{{handler}}")],
   0, unit="reqps", stack=True)
ts("Request rate by status class", [target(f'sum by (status) (rate(http_requests_total{{{SEL}}}[{RI}]))', "{{status}}")],
   12, unit="reqps", stack=True)
advance(8)
ts("Request rate by instance", [target(f'sum by (deployment, instance) (rate(http_requests_total{{{SEL}}}[{RI}]))',
                                       "{{deployment}} / {{instance}}")], 0, w=8, unit="reqps")
ts("Avg request size", [target(f'sum(rate(http_request_size_bytes_sum{{{SEL}}}[{RI}])) / clamp_min(sum(rate(http_request_size_bytes_count{{{SEL}}}[{RI}])), 0.0001)', "request")],
   8, w=8, unit="bytes")
ts("Avg response size", [target(f'sum(rate(http_response_size_bytes_sum{{{SEL}}}[{RI}])) / clamp_min(sum(rate(http_response_size_bytes_count{{{SEL}}}[{RI}])), 0.0001)', "response")],
   16, w=8, unit="bytes")
advance(8)

# ----------------------------------------------------------------------------- Latency
row("Latency")
q = lambda p: f'histogram_quantile({p}, sum by (le) (rate(http_request_duration_highr_seconds_bucket{{{SEL}}}[{RI}])))'  # noqa: E731
ts("HTTP latency percentiles (all endpoints)",
   [target(q(0.5), "p50", ref="A"), target(q(0.95), "p95", ref="B"), target(q(0.99), "p99", ref="C")],
   0, unit="s", fill=5)
heatmap("HTTP latency heatmap", f'sum by (le) (increase(http_request_duration_highr_seconds_bucket{{{SEL}}}[{RI}]))',
        12, desc="Colour = number of requests in each latency bucket")
advance(8)
ts("Average latency by endpoint",
   [target(f'sum by (handler) (rate(http_request_duration_seconds_sum{{{SEL}}}[{RI}])) / sum by (handler) (rate(http_request_duration_seconds_count{{{SEL}}}[{RI}]))', "{{handler}}")],
   0, unit="s")
iq = lambda p: f'histogram_quantile({p}, sum by (le) (rate(heart_inference_seconds_bucket{{{SEL}}}[{RI}])))'  # noqa: E731
ts("Model inference latency", [target(iq(0.5), "p50", ref="A"), target(iq(0.95), "p95", ref="B"),
                               target(iq(0.99), "p99", ref="C")], 12, unit="s", fill=5,
   desc="Time spent inside model.predict_proba only")
advance(8)

# ----------------------------------------------------------------------------- Errors
row("Errors")
ts("4xx / 5xx rate by endpoint",
   [target(f'sum by (handler, status) (rate(http_requests_total{{{SEL}, status=~"4xx|5xx"}}[{RI}]))', "{{handler}} {{status}}")],
   0, w=8, unit="reqps", stack=True)
ts("Prediction errors by reason", [target(f'sum by (reason) (rate(heart_predict_errors_total{{{SEL}}}[{RI}]))', "{{reason}}")],
   8, w=8, unit="reqps", desc="Counter appears only after the first failure")
table("Requests by endpoint and status (range)",
      [target(f'sum by (handler, method, status) (increase(http_requests_total{{{SEL}}}[$__range]))',
              instant=True, range=False, format="table")],
      16, w=8, desc="Totals for the selected time range",
      transformations=[{"id": "organize", "options": {"excludeByName": {"Time": True},
                                                      "renameByName": {"Value": "requests"}}}])
advance(8)

# ----------------------------------------------------------------------------- Model behaviour
row("Model behaviour")
ts("Predictions per minute by outcome",
   [target(f'sum by (outcome) (rate(heart_predictions_total{{{SEL}}}[{RI}])) * 60', "{{outcome}}")],
   0, w=9, stack=True, unit="short")
pie("Risk bands (range)", f'sum by (band) (increase(heart_risk_band_total{{{SEL}}}[$__range]))', "{{band}}", 9, w=5,
    desc="low < 0.33 <= medium < 0.66 <= high")
ts("P(disease): mean over time",
   [target(f'sum(rate(heart_prediction_probability_sum{{{SEL}}}[{RI}])) / clamp_min(sum(rate(heart_prediction_probability_count{{{SEL}}}[{RI}])), 0.0001)', "mean P(disease)")],
   14, w=10, unit="percentunit", minimum=0)
advance(8)
bars("P(disease) distribution (cumulative, range)",
     f'sum by (le) (increase(heart_prediction_probability_bucket{{{SEL}}}[$__range]))', "<= {{le}}", 0, w=8,
     desc="Number of predictions with P(disease) up to each bound")
table("Served model", [target(f'heart_model_info{{{SEL}}}', instant=True, range=False, format="table")], 8, w=8,
      desc="Which model/version each instance is serving",
      transformations=[{"id": "organize", "options": {
          "excludeByName": {"Time": True, "Value": True, "__name__": True, "job": True},
          "renameByName": {}}}])
ts("Predicted-positive ratio",
   [target(f'sum(rate(heart_predictions_total{{{SEL}, outcome="disease"}}[{RI}])) / clamp_min(sum(rate(heart_predictions_total{{{SEL}}}[{RI}])), 0.0001)', "disease share")],
   16, w=8, unit="percentunit", minimum=0, desc="A sudden shift can indicate data drift")
advance(8)

# ----------------------------------------------------------------------------- Input monitoring
row("Input data monitoring (drift watch)")
for i, (name, label, unit) in enumerate([("age", "Mean age (years)", "none"), ("chol", "Mean cholesterol (mg/dl)", "none"),
                                         ("trestbps", "Mean resting BP (mm Hg)", "none"),
                                         ("thalach", "Mean max heart rate (bpm)", "none")]):
    ts(label, [target(f'sum(rate(heart_input_{name}_sum{{{SEL}}}[{RI}])) / clamp_min(sum(rate(heart_input_{name}_count{{{SEL}}}[{RI}])), 0.0001)', f"mean {name}")],
       i * 6, w=6, unit=unit, legend_calcs=["mean"])
advance(8)
bars("Age distribution (cumulative, range)", f'sum by (le) (increase(heart_input_age_bucket{{{SEL}}}[$__range]))',
     "<= {{le}}", 0, w=12, h=7)
bars("Cholesterol distribution (cumulative, range)",
     f'sum by (le) (increase(heart_input_chol_bucket{{{SEL}}}[$__range]))', "<= {{le}}", 12, w=12, h=7)
advance(7)

# ----------------------------------------------------------------------------- Resources
row("Process resources")
ts("CPU usage (cores)", [target(f'sum by (deployment, instance) (rate(process_cpu_seconds_total{{{SEL}}}[{RI}]))',
                                "{{deployment}} / {{instance}}")], 0, w=6, unit="none", minimum=0)
ts("Memory (RSS)", [target(f'sum by (deployment, instance) (process_resident_memory_bytes{{{SEL}}})',
                           "{{deployment}} / {{instance}}")], 6, w=6, unit="bytes", minimum=0)
ts("Open file descriptors", [target(f'sum by (deployment, instance) (process_open_fds{{{SEL}}})',
                                    "{{deployment}} / {{instance}}")], 12, w=6, minimum=0)
ts("Python GC collections / s", [target(f'sum by (generation) (rate(python_gc_collections_total{{{SEL}}}[{RI}]))',
                                        "gen {{generation}}")], 18, w=6)
advance(8)

# ----------------------------------------------------------------------------- Deployments
row("Deployments and scrape health")
table("Scrape targets",
      [target('up{job=~"fastapi-ml-app.*"}', instant=True, range=False, format="table")], 0, w=12,
      desc="1 = Prometheus can scrape the API of this deployment",
      transformations=[{"id": "organize", "options": {
          "excludeByName": {"Time": True, "__name__": True}, "renameByName": {"Value": "up"}}}])
ts("Scrape duration", [target(f'scrape_duration_seconds{{job=~"fastapi-ml-app.*", deployment=~"$deployment"}}',
                              "{{deployment}} / {{instance}}")], 12, w=12, unit="s")
advance(8)

dashboard = {
    "uid": "heart-disease-api",
    "title": "Heart Disease MLOps - Monitoring",
    "description": "Traffic, latency, errors, model behaviour, input drift and resources for the heart-disease API "
                   "(Docker Compose and Kubernetes deployments).",
    "tags": ["mlops", "heart-disease", "fastapi"],
    "timezone": "browser", "editable": True, "graphTooltip": 1, "schemaVersion": 39, "version": 3,
    "refresh": "10s", "time": {"from": "now-15m", "to": "now"},
    "annotations": {"list": []}, "links": [],
    "templating": {"list": [
        {"name": "deployment", "label": "Deployment", "type": "query", "datasource": DS,
         "query": {"query": 'label_values(http_requests_total{job=~"fastapi-ml-app.*"}, deployment)', "refId": "v1"},
         "definition": 'label_values(http_requests_total{job=~"fastapi-ml-app.*"}, deployment)',
         "refresh": 2, "includeAll": True, "multi": True, "allValue": ".*", "sort": 1,
         "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
        {"name": "instance", "label": "Instance", "type": "query", "datasource": DS,
         "query": {"query": 'label_values(http_requests_total{job=~"fastapi-ml-app.*", deployment=~"$deployment"}, instance)', "refId": "v2"},
         "definition": 'label_values(http_requests_total{job=~"fastapi-ml-app.*", deployment=~"$deployment"}, instance)',
         "refresh": 2, "includeAll": True, "multi": True, "allValue": ".*", "sort": 1,
         "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
    ]},
    "panels": panels,
}

if __name__ == "__main__":
    out = Path(__file__).with_name("grafana_dashboard.json")
    out.write_text(json.dumps(dashboard, indent=2) + "\n")
    print(f"wrote {out} ({len(panels)} panels/rows)")
