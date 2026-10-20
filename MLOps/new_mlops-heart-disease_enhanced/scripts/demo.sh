#!/usr/bin/env bash
# Narrated walk-through for the screen recording. Press ENTER to advance each scene.
#   scripts/demo.sh            # interactive (recommended for the video)
#   scripts/demo.sh --auto     # no pauses (dry run / CI)
#   scripts/demo.sh --open     # also open the browser tabs (xdg-open) at the right moments
# Preconditions: ./initial_deploy.sh finished (stack up). Add --k8s/--helm scenes if you deployed Minikube.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
AUTO=0; OPEN=0
for a in "$@"; do case "$a" in --auto) AUTO=1 ;; --open) OPEN=1 ;; esac; done
[ -f .venv/bin/activate ] && source .venv/bin/activate
if docker info >/dev/null 2>&1; then DOCKER=docker; else DOCKER="sudo docker"; fi
PAYLOAD='{"age":67,"sex":1,"cp":4,"trestbps":160,"chol":286,"fbs":0,"restecg":2,"thalach":108,"exang":1,"oldpeak":1.5,"slope":2,"ca":3,"thal":3}'

scene() { clear; printf '\n\033[1;36m=== SCENE %s: %s ===\033[0m\n' "$1" "$2"; printf '\033[0;33m(say: %s)\033[0m\n\n' "$3"; }
pause() { [ "$AUTO" -eq 1 ] || read -r -p $'\n[ENTER for next]' _; }
open_url() { [ "$OPEN" -eq 1 ] && command -v xdg-open >/dev/null && xdg-open "$1" >/dev/null 2>&1 || true; }
run() { printf '\033[1;32m$ %s\033[0m\n' "$*"; eval "$*"; }

scene 1 "Repository and requirements" "Project layout: src, tests, Docker, Helm, k8s, monitoring, CI"
run "ls; echo; ls src test k8s helm/heart-disease-app monitoring .github/workflows"; pause

scene 2 "Quality gate" "flake8 and pytest must pass, otherwise the pipeline fails"
run "flake8 . && echo 'flake8 clean' && pytest -q --cov=src 2>&1 | tail -18"; pause

scene 3 "Data + EDA" "Cleaned dataset and EDA plots (class balance, histograms, heatmap)"
run "head -3 data/heart_disease_clean.csv; ls data/eda_plots"; open_url "file://$PWD/data/eda_plots/correlation_heatmap.png"; pause

scene 4 "Experiment tracking" "Two tuned models tracked in MLflow; champion saved with metadata"
run "cat models/model_metadata.json | head -30"; open_url "http://localhost:5000"; pause

scene 5 "Docker image and stack" "Container is healthy; API, MLflow, Prometheus, Grafana are running"
run "$DOCKER compose ps; $DOCKER images | grep -E 'REPOSITORY|heart-disease'"; pause

scene 6 "Prediction API" "POST /predict returns prediction and confidence; bad input gets HTTP 422"
run "curl -s -X POST localhost:8000/predict -H 'Content-Type: application/json' -d '$PAYLOAD'; echo"
run "curl -s -o /dev/null -w 'invalid input -> HTTP %{http_code}\n' -X POST localhost:8000/predict -H 'Content-Type: application/json' -d '{\"age\":1}'"
open_url "http://localhost:8000/docs"; pause

scene 7 "Traffic + logging" "Traffic generator hits the API; every request is logged as JSON"
( python3 scripts/generate_traffic.py --profile steady --rps 8 --duration 45 > logs/demo_traffic.log 2>&1 & )
run "sleep 6; $DOCKER compose logs --tail 8 api | cut -c1-200"; pause

scene 8 "Prometheus" "Prometheus scrapes /metrics every 15 s; targets are UP, alert rules loaded"
open_url "http://localhost:9090/targets"
run "curl -s localhost:9090/api/v1/targets | python3 -c \"import sys,json;[print(t['labels']['job'],t['health']) for t in json.load(sys.stdin)['data']['activeTargets']]\""; pause

scene 9 "Grafana" "Provisioned dashboard: traffic, latency, errors, model behaviour, drift, resources"
open_url "http://localhost:3000/d/heart-disease-api/heart-disease-mlops-monitoring?orgId=1&refresh=10s"
echo "Switch to the browser (admin / admin). Scroll through each section while traffic is running."; pause

scene 10 "Monitoring self-check" "Every dashboard query returns data"
run "python3 scripts/verify_monitoring.py | tail -15"; pause

if command -v kubectl >/dev/null && kubectl get deploy >/dev/null 2>&1; then
  scene 11 "Kubernetes / Helm" "Same image deployed to Minikube: 2 replicas behind a LoadBalancer service"
  run "kubectl get deploy,pods,svc -o wide; helm list 2>/dev/null"; pause
fi

scene 12 "CI/CD" "GitHub Actions: lint, tests, training, docker build, smoke test; artifacts attached"
echo "Show the Actions tab: last green run, steps, uploaded artifacts, and the failing-run demo."; pause
printf '\n\033[1;36mDone - stop the recording.\033[0m\n'
