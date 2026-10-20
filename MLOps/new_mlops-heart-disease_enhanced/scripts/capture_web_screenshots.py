#!/usr/bin/env python3
"""Take consistent, numbered screenshots of the web UIs (API docs, MLflow, Prometheus, Grafana).

Setup (once):   pip install playwright && playwright install chromium
Usage:
  python3 scripts/capture_web_screenshots.py                  # everything that is reachable
  python3 scripts/capture_web_screenshots.py --only grafana   # name filter (substring match)
  python3 scripts/capture_web_screenshots.py --headed         # watch the browser while it works
  python3 scripts/capture_web_screenshots.py --chrome-path /usr/bin/chromium   # use an installed browser

Output: screenshots/web/NN_<name>.png   (1600 px wide, light and readable for the report).
Run scripts/generate_traffic.py for a few minutes BEFORE the Prometheus/Grafana shots.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "web"
WIDTH = 1600


def http_json(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def reachable(url):
    try:
        urllib.request.urlopen(url, timeout=4)
        return True
    except Exception as exc:
        return getattr(exc, "code", None) is not None      # an HTTP error still means "server is there"


def dashboard_height(default=3600):
    try:
        d = json.load(open(ROOT / "monitoring" / "grafana_dashboard.json"))
        return int(max(p["gridPos"]["y"] + p["gridPos"]["h"] for p in d["panels"]) * 38 + 220)
    except Exception:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--mlflow", default="http://localhost:5000")
    ap.add_argument("--prom", default="http://localhost:9090")
    ap.add_argument("--grafana", default="http://localhost:3000")
    ap.add_argument("--grafana-user", default="admin")
    ap.add_argument("--grafana-password", default="admin")
    ap.add_argument("--only", help="substring of the shot name to capture")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--chrome-path", help="path of an existing chrome/chromium binary")
    ap.add_argument("--wait", type=int, default=4, help="seconds to let dashboards render")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright missing: pip install playwright && playwright install chromium")

    OUT.mkdir(parents=True, exist_ok=True)
    counter = [0]

    def path_for(name):
        counter[0] += 1
        return OUT / f"{counter[0]:02d}_{name}.png"

    def wanted(name):
        return not args.only or args.only in name

    with sync_playwright() as pw:
        launch = {"headless": not args.headed}
        if args.chrome_path:
            launch["executable_path"] = args.chrome_path
        browser = pw.chromium.launch(**launch)
        ctx = browser.new_context(viewport={"width": WIDTH, "height": 1000}, device_scale_factor=1)
        page = ctx.new_page()

        def shot(name, url, wait_ms=1500, full=True, height=None, before=None):
            if not wanted(name):
                return
            if height:
                page.set_viewport_size({"width": WIDTH, "height": height})
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
            except Exception:
                page.goto(url, timeout=45000)
            if before:
                try:
                    before(page)
                except Exception as exc:
                    print(f"   (interaction skipped: {exc})")
            page.wait_for_timeout(wait_ms)
            target = path_for(name)
            page.screenshot(path=str(target), full_page=full)
            page.set_viewport_size({"width": WIDTH, "height": 1000})
            print(f"  saved {target.relative_to(ROOT)}")

        # ---- API -------------------------------------------------------------------------------
        if reachable(args.api + "/health"):
            print("API")

            def try_predict(p):
                p.click(".opblock-post .opblock-summary")
                p.click("button.try-out__btn")
                p.click("button.execute")
                p.wait_for_selector(".responses-table.live-responses-table", timeout=10000)

            shot("api_swagger_docs", args.api + "/docs", 1500, height=1100)
            shot("api_predict_try_it_out", args.api + "/docs", 1500, height=1800, before=try_predict)
            shot("api_health", args.api + "/health", 500, full=False)
            shot("api_model_info", args.api + "/model-info", 500, full=False)
            shot("api_metrics_raw", args.api + "/metrics", 800, full=False)
        else:
            print("API not reachable - skipped")

        # ---- MLflow ----------------------------------------------------------------------------
        if reachable(args.mlflow + "/health"):
            print("MLflow")
            try:
                exp = http_json(args.mlflow + "/api/2.0/mlflow/experiments/get-by-name?experiment_name=Heart_Disease_Classification")
                eid = exp["experiment"]["experiment_id"]
                runs = http_json(args.mlflow + "/api/2.0/mlflow/runs/search", {"experiment_ids": [eid]})["runs"]
                champ = next((r for r in runs if {"key": "champion", "value": "true"} in r["data"]["tags"]), runs[0])
                rid = champ["info"]["run_id"]
                shot("mlflow_experiment_runs", f"{args.mlflow}/#/experiments/{eid}", 3000, height=1100)
                shot("mlflow_champion_run", f"{args.mlflow}/#/experiments/{eid}/runs/{rid}", 3000, height=1400)
                shot("mlflow_champion_artifacts", f"{args.mlflow}/#/experiments/{eid}/runs/{rid}/artifactPath/model", 3000, height=1100)
                shot("mlflow_compare_runs", f"{args.mlflow}/#/compare-runs?runs=" +
                     urllib.parse.quote(json.dumps([r["info"]["run_id"] for r in runs])) + f"&experiments={urllib.parse.quote(json.dumps([eid]))}",
                     3500, height=1400)
            except Exception as exc:
                print(f"  MLflow shots failed ({exc}) - run training first")
        else:
            print("MLflow not reachable - skipped")

        # ---- Prometheus ------------------------------------------------------------------------
        if reachable(args.prom + "/-/ready"):
            print("Prometheus")
            q = urllib.parse.quote
            shot("prometheus_targets", args.prom + "/targets", 1500, height=900)
            shot("prometheus_alerts", args.prom + "/alerts", 1500, height=900)
            shot("prometheus_rules", args.prom + "/rules", 1500, height=1000)
            shot("prometheus_query_request_rate",
                 f"{args.prom}/graph?g0.expr={q('sum by (handler) (rate(http_requests_total[1m]))')}&g0.tab=0&g0.range_input=15m",
                 3000, height=1000)
            shot("prometheus_query_predictions",
                 f"{args.prom}/graph?g0.expr={q('sum by (outcome) (heart_predictions_total)')}&g0.tab=1&g0.range_input=15m",
                 3000, height=900)
        else:
            print("Prometheus not reachable - skipped")

        # ---- Grafana ---------------------------------------------------------------------------
        if reachable(args.grafana + "/api/health"):
            print("Grafana")
            if wanted("grafana"):
                page.goto(args.grafana + "/login", timeout=45000)
                try:
                    page.fill('input[name="user"]', args.grafana_user)
                    page.fill('input[name="password"]', args.grafana_password)
                    page.click('button[type="submit"]')
                    page.wait_for_timeout(2500)
                    skip = page.get_by_text("Skip")
                    if skip.count():
                        skip.first.click()
                except Exception as exc:
                    print(f"  login step: {exc}")
            dash = f"{args.grafana}/d/heart-disease-api/heart-disease-mlops-monitoring?orgId=1&from=now-15m&to=now&refresh=10s"
            shot("grafana_datasource", f"{args.grafana}/connections/datasources", 1500, height=800)
            shot("grafana_dashboard_full", dash, args.wait * 1000 + 3000, height=dashboard_height())
            shot("grafana_dashboard_top", dash, args.wait * 1000, height=1000, full=False)
            shot("grafana_dashboard_kiosk", dash + "&kiosk", args.wait * 1000, height=dashboard_height())
            shot("grafana_alerts", f"{args.grafana}/alerting/list", 2000, height=900)
        else:
            print("Grafana not reachable - skipped")

        browser.close()
    print(f"\nDone: {counter[0]} screenshot(s) in {OUT.relative_to(ROOT)}  ({time.strftime('%H:%M:%S')})")


if __name__ == "__main__":
    main()
