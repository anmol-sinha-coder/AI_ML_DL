#!/usr/bin/env bash
# Deploy the API to a local Minikube cluster with plain manifests or Helm.
#
#   scripts/deploy_k8s.sh --manifests                 # kubectl apply k8s/deployment.yml + service.yml
#   scripts/deploy_k8s.sh --helm                      # helm upgrade --install helm/heart-disease-app
#   scripts/deploy_k8s.sh --helm --ingress --hpa      # + Ingress (heart.local) and autoscaling
#   scripts/deploy_k8s.sh --teardown                  # remove both kinds of deployment
#
# Needs models/best_model.pkl (python -m src.train). Run as a normal user (minikube refuses root).
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

MODE=""; INGRESS=0; HPA=0; TEARDOWN=0
IMAGE="heart-disease-api:v1"; RELEASE="${HELM_RELEASE:-heart-disease-api}"; CHART="helm/heart-disease-app"
LOCAL_PORT="${LOCAL_PORT:-18080}"
for a in "$@"; do
  case "$a" in
    --manifests|--k8s) MODE=manifests ;;
    --helm) MODE=helm ;;
    --ingress) INGRESS=1 ;;
    --hpa) HPA=1 ;;
    --teardown) TEARDOWN=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a" >&2; exit 2 ;;
  esac
done
die() { echo "ERROR: $*" >&2; exit 1; }
log() { printf '\n--> %s\n' "$*"; }
[ "$EUID" -ne 0 ] || die "run as a normal user, not root (minikube's docker driver refuses root)"
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi

install_tools() {
  local arch; case "$(uname -m)" in x86_64) arch=amd64 ;; aarch64|arm64) arch=arm64 ;; *) die "unsupported CPU $(uname -m)" ;; esac
  local tmp; tmp="$(mktemp -d)"
  if ! command -v kubectl >/dev/null; then
    log "Installing kubectl"
    curl -fsSLo "$tmp/kubectl" "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/${arch}/kubectl"
    sudo install -o root -g root -m 0755 "$tmp/kubectl" /usr/local/bin/kubectl
  fi
  if ! command -v minikube >/dev/null; then
    log "Installing minikube"
    curl -fsSLo "$tmp/minikube" "https://storage.googleapis.com/minikube/releases/latest/minikube-linux-${arch}"
    sudo install -m 0755 "$tmp/minikube" /usr/local/bin/minikube
  fi
  if [ "$MODE" = "helm" ] && ! command -v helm >/dev/null; then
    log "Installing helm"
    curl -fsSLo "$tmp/get-helm-3" https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    bash "$tmp/get-helm-3"
  fi
  rm -rf "$tmp"
}

start_minikube() {
  if docker info >/dev/null 2>&1; then
    minikube start --driver=docker
  elif command -v sg >/dev/null && getent group docker >/dev/null; then
    sg docker -c 'minikube start --driver=docker'      # docker group not active in this shell yet
  else
    die "current user cannot reach the Docker daemon; log out/in after joining the docker group"
  fi
}

if [ "$TEARDOWN" -eq 1 ]; then
  helm uninstall "$RELEASE" 2>/dev/null || true
  kubectl delete -f k8s/ingress.yml -f k8s/hpa.yml -f k8s/service.yml -f k8s/deployment.yml --ignore-not-found
  rm -f monitoring/targets/k8s.json
  echo "Kubernetes resources removed."; exit 0
fi

[ -n "$MODE" ] || die "choose --manifests or --helm"
[ -f models/best_model.pkl ] || die "models/best_model.pkl missing - run: python -m src.train"
install_tools

log "Minikube"
minikube status >/dev/null 2>&1 || start_minikube
[ "$INGRESS" -eq 0 ] || minikube addons enable ingress
[ "$HPA" -eq 0 ] || minikube addons enable metrics-server

log "Build and load image ${IMAGE}"
$DOCKER build -t "$IMAGE" .
minikube image load "$IMAGE"

if [ "$MODE" = "manifests" ]; then
  helm uninstall "$RELEASE" >/dev/null 2>&1 || true          # never run both at once
  kubectl apply -f k8s/deployment.yml -f k8s/service.yml
  [ "$INGRESS" -eq 0 ] || kubectl apply -f k8s/ingress.yml
  [ "$HPA" -eq 0 ] || kubectl apply -f k8s/hpa.yml
  kubectl rollout restart deployment/heart-disease-api
  DEPLOY="heart-disease-api"; SVC="heart-disease-service"
else
  kubectl delete -f k8s/service.yml -f k8s/deployment.yml --ignore-not-found >/dev/null
  helm lint "$CHART"
  helm upgrade --install "$RELEASE" "$CHART" \
    --set ingress.enabled="$([ "$INGRESS" -eq 1 ] && echo true || echo false)" \
    --set autoscaling.enabled="$([ "$HPA" -eq 1 ] && echo true || echo false)" \
    --wait --timeout 180s
  helm list
  DEPLOY="$RELEASE"; SVC="$RELEASE"
fi

kubectl rollout status "deployment/${DEPLOY}" --timeout=180s
kubectl get deploy,pods,svc -o wide
[ "$INGRESS" -eq 0 ] || kubectl get ingress

log "Smoke test through kubectl port-forward"
kubectl port-forward "svc/${SVC}" "${LOCAL_PORT}:80" >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null || true' EXIT
sleep 3
scripts/smoke_test.sh "http://localhost:${LOCAL_PORT}"

# Let the Compose Prometheus scrape the Kubernetes pods too (shows up as deployment="k8s" in Grafana)
if $DOCKER ps --format '{{.Names}}' | grep -qx prometheus; then
  SVC_NAME="$SVC" scripts/add_k8s_scrape_target.sh || echo "WARNING: could not register the k8s scrape target (non-fatal)"
fi

helm list -A

echo
echo "Minikube URL : $(minikube service "$SVC" --url | head -n1)"
echo "Port-forward : kubectl port-forward svc/${SVC} ${LOCAL_PORT}:80   then scripts/generate_traffic.py --url http://localhost:${LOCAL_PORT}"
