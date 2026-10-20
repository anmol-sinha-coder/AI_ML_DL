#!/usr/bin/env python3
"""Check the whole monitoring chain: API /metrics -> Prometheus -> Grafana dashboard queries.

Runs every PromQL expression of monitoring/grafana_dashboard.json against Prometheus and reports
which panels will have data.  Standard library only.

  python3 scripts/verify_monitoring.py                      # defaults: localhost ports
  python3 scripts/verify_monitoring.py --prom http://localhost:9090 --grafana http://localhost:3000

Run scripts/generate_traffic.py first (a minute is enough), otherwise panels are legitimately empty.
Exit code 0 = all required panels have data.
"""
import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Panels that are legitimately empty until a specific event happens
OPTIONAL = ("heart_predict_errors_total", "ALERTS", "fastapi-ml-app-k8s", 'status=~"5xx"')


def get(url, auth=None, timeout=10):
    req = urllib.request.Request(url)
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def prom_query(base, expr):
    url = f"{base}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    return get(url)["data"]["result"]


def resolve(expr):
    """Substitute Grafana variables the way Grafana would for 'All'."""
    for var, val in (("$__rate_interval", "1m"), ("$__range", "10m"), ("$deployment", ".*"), ("$instance", ".*")):
        expr = expr.replace(var, val)
    return expr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prom", default="http://localhost:9090")
    ap.add_argument("--grafana", default="http://localhost:3000")
    ap.add_argument("--grafana-auth", default="admin:admin")
    ap.add_argument("--dashboard", default=str(ROOT / "monitoring" / "grafana_dashboard.json"))
    args = ap.parse_args()
    failures = 0

    print("== 1. Prometheus targets")
    try:
        targets = get(args.prom + "/api/v1/targets")["data"]["activeTargets"]
    except Exception as exc:
        sys.exit(f"[FAIL] Prometheus not reachable at {args.prom}: {exc}\n"
                 "       -> docker compose logs prometheus   (a config error makes it exit immediately)")
    for t in targets:
        ok = t["health"] == "up"
        failures += (not ok) and t["labels"].get("job", "").startswith("fastapi-ml-app") and "k8s" not in t["labels"]["job"]
        print(f"  [{'OK ' if ok else 'BAD'}] {t['labels'].get('job'):<22} {t['scrapeUrl']:<40} {t['health']} {t.get('lastError', '')}")

    print("\n== 2. Dashboard queries against Prometheus")
    dash = json.load(open(args.dashboard))
    empty_required = 0
    for panel in dash["panels"]:
        for tgt in panel.get("targets", []):
            expr = resolve(tgt["expr"])
            try:
                res = prom_query(args.prom, expr)
                status = f"{len(res)} series"
                ok = bool(res)
            except Exception as exc:
                status, ok = f"ERROR {exc}", False
            optional = any(o in tgt["expr"] for o in OPTIONAL)
            tag = "OK " if ok else ("opt" if optional else "BAD")
            if not ok and not optional:
                empty_required += 1
            print(f"  [{tag}] {panel['title'][:46]:<46} {status}")
    failures += empty_required

    print("\n== 3. Grafana (optional)")
    try:
        health = get(f"{args.grafana}/api/datasources/uid/prometheus/health", auth=args.grafana_auth)
        print(f"  datasource 'prometheus': {health.get('status')} - {health.get('message')}")
        found = get(f"{args.grafana}/api/search?query=Heart", auth=args.grafana_auth)
        print("  dashboards:", [d["title"] for d in found] or "NONE FOUND (check provisioning mounts)")
        failures += (health.get("status") != "OK") or (not found)
    except Exception as exc:
        print(f"  skipped / not reachable: {exc}")

    print("\nRESULT:", "PASS - every required panel has data" if not failures else f"FAIL ({failures} problem(s))")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
