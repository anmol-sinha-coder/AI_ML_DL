#!/usr/bin/env bash
# Register the Minikube service as a Prometheus scrape target (label deployment="k8s").
# Prometheus (Docker Compose) re-reads monitoring/targets/*.json every 30 s - no restart needed.
#   SVC_NAME=heart-disease-service scripts/add_k8s_scrape_target.sh     # manifests (default)
#   SVC_NAME=heart-disease-api     scripts/add_k8s_scrape_target.sh     # helm release
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
SVC_NAME="${SVC_NAME:-heart-disease-service}"
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi

IP="$(minikube ip)"
NODEPORT="$(kubectl get svc "$SVC_NAME" -o jsonpath='{.spec.ports[0].nodePort}')"
[ -n "$NODEPORT" ] || { echo "Service $SVC_NAME has no nodePort (type must be LoadBalancer or NodePort)" >&2; exit 1; }

mkdir -p monitoring/targets
cat > monitoring/targets/k8s.json <<JSON
[{"targets": ["${IP}:${NODEPORT}"], "labels": {"deployment": "k8s"}}]
JSON
echo "Wrote monitoring/targets/k8s.json -> ${IP}:${NODEPORT}"

# Prometheus (compose network) must be able to reach the minikube network
if $DOCKER network inspect minikube >/dev/null 2>&1; then
  $DOCKER network connect minikube prometheus 2>/dev/null && echo "Connected prometheus container to the 'minikube' docker network" || true
fi
echo "Check in ~30 s:  http://localhost:9090/targets   (job fastapi-ml-app-k8s should be UP)"
