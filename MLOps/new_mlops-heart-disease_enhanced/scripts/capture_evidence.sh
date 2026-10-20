#!/usr/bin/env bash
# Collect TEXT evidence (command + output + timestamp) into screenshots/evidence/.
# Run it after each phase; the files back up your PNG screenshots and are handy for the report.
#
#   scripts/capture_evidence.sh tests      # lint + pytest + coverage
#   scripts/capture_evidence.sh train      # MLflow runs summary
#   scripts/capture_evidence.sh docker     # images, containers, health, logs, predict
#   scripts/capture_evidence.sh monitoring # Prometheus targets + PromQL checks, Grafana health
#   scripts/capture_evidence.sh k8s        # pods, svc, helm releases, predict via port-forward
#   scripts/capture_evidence.sh all
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT=screenshots/evidence; mkdir -p "$OUT"
API="${API_URL:-http://localhost:8000}"; PROM="${PROM_URL:-http://localhost:9090}"
GRAF="${GRAFANA_URL:-http://localhost:3000}"; MLF="${MLFLOW_URL:-http://localhost:5000}"
PAYLOAD='{"age":63,"sex":1,"cp":1,"trestbps":145,"chol":233,"fbs":1,"restecg":2,"thalach":150,"exang":0,"oldpeak":2.3,"slope":3,"ca":0,"thal":6}'
if docker info >/dev/null 2>&1; then DOCKER=docker; else DOCKER="sudo docker"; fi
[ -f .venv/bin/activate ] && source .venv/bin/activate

# run <file-name> <command...> : tee "$ command" + output into $OUT/<file-name>.txt
run() {
  local name="$1"; shift
  { echo "# $(date -Is)"; echo "# host: $(hostname)"; echo "\$ $*"; echo; eval "$*"; echo; echo "# exit code: $?"; } 2>&1 | tee "$OUT/$name.txt"
  echo "--- saved $OUT/$name.txt"; echo
}

phase_tests()  { run 04_flake8 "flake8 . && echo 'flake8: no issues'"
                 run 04_pytest "pytest -q --cov=src --cov-report=term"; }
phase_train()  { run 02_mlflow_runs "python3 - <<'PY'
import json, urllib.request
req = urllib.request.Request('$MLF/api/2.0/mlflow/runs/search', data=json.dumps({'experiment_ids': ['1']}).encode(), headers={'Content-Type': 'application/json'})
for r in json.load(urllib.request.urlopen(req))['runs']:
    m = {x['key']: round(x['value'], 4) for x in r['data']['metrics']}
    t = {x['key']: x['value'] for x in r['data']['tags']}
    print(r['info']['run_name'], 'champion=' + t.get('champion', 'false'))
    print('   params :', {x['key']: x['value'] for x in r['data']['params']})
    print('   metrics:', {k: m[k] for k in sorted(m)})
PY
cat models/model_metadata.json"; }
phase_docker() { run 07_docker_images "$DOCKER images | grep -E 'REPOSITORY|heart-disease'"
                 run 07_docker_compose_ps "$DOCKER compose ps"
                 run 07_container_health "$DOCKER inspect --format '{{.Name}} {{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' ml_api mlflow_server"
                 run 08_predict_curl "curl -s -i -X POST $API/predict -H 'Content-Type: application/json' -d '$PAYLOAD'"
                 run 08_smoke_test "scripts/smoke_test.sh $API"
                 run 11_api_logs "$DOCKER compose logs --tail 25 api"; }
phase_monitoring() {
  run 12_prometheus_targets "curl -s $PROM/api/v1/targets | python3 -c \"import sys,json; [print(t['labels']['job'], t['scrapeUrl'], t['health']) for t in json.load(sys.stdin)['data']['activeTargets']]\""
  for q in 'sum(rate(http_requests_total[1m]))' 'sum by (outcome) (heart_predictions_total)' 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[1m])))'; do
    run "12_promql_$(echo "$q" | tr -c 'a-zA-Z0-9' '_' | cut -c1-40)" "curl -s --get $PROM/api/v1/query --data-urlencode 'query=$q'"
  done
  run 13_grafana_health "curl -s $GRAF/api/health; echo; curl -s -u admin:admin '$GRAF/api/search?query=Heart'"; }
phase_k8s()    { run 09_kubectl_pods_svc "kubectl get nodes,pods,svc,deploy -o wide"
                 run 09_helm_list "helm list 2>/dev/null || echo 'helm release not used'"
                 run 09_rollout "kubectl rollout status deployment --timeout=60s"
                 run 10_k8s_url "minikube service heart-disease-service --url 2>/dev/null || minikube service heart-disease-api --url"; }

case "${1:-all}" in
  tests) phase_tests ;; train) phase_train ;; docker) phase_docker ;;
  monitoring) phase_monitoring ;; k8s) phase_k8s ;;
  all) phase_tests; phase_train; phase_docker; phase_monitoring; phase_k8s ;;
  *) echo "usage: $0 {tests|train|docker|monitoring|k8s|all}"; exit 2 ;;
esac
