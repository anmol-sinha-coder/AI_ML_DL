#!/usr/bin/env bash
# End-to-end initial deployment for the MLOps Heart Disease stack.
# Run this script from the repository root (or keep it in the repository root).
# Usage: ./deploy_mlops.sh [--with-k8s | --helm] [--no-traffic]

set -Eeuo pipefail

# ------------------------------- Configuration -------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Prefer the caller's working directory when it is the repository root, so the
# script can also be invoked by absolute path from inside the project checkout.
if [[ -f "$PWD/requirements.txt" && -f "$PWD/src/train.py" ]]; then
  PROJECT_ROOT="$(pwd -P)"
else
  PROJECT_ROOT="$SCRIPT_DIR"
fi
cd "$PROJECT_ROOT"

K8S_MODE="none"              # none | manifests | helm
START_TRAFFIC="true"
HEALTH_TIMEOUT_SECONDS="180"
MLFLOW_URL="http://localhost:5000"
API_URL="http://localhost:8000"
GRAFANA_URL="http://localhost:3000"
PROMETHEUS_URL="http://localhost:9090"
IMAGE_NAME="heart-disease-api:v1"
HELM_RELEASE="heart-disease-release"
HELM_CHART="helm/heart-disease-app"
K8S_DEPLOYMENT="heart-disease-api"
K8S_SERVICE="heart-disease-service"

usage() {
  cat <<'USAGE'
MLOps Heart Disease stack deployment

Usage:
  ./deploy_mlops.sh [options]

Options:
  --with-k8s       Also deploy using k8s/deployment.yml (and k8s/service.yml if present)
  --helm           Also deploy using helm/heart-disease-app
  --no-traffic     Do not start tests/traffic_generator.py after deployment
  -h, --help       Show this help

The Docker Compose stack (MLflow, FastAPI, Prometheus, Grafana, and any other
services in the Compose file) is deployed by default. Kubernetes is optional.
This script intentionally does not run `docker compose down -v`; that command
can delete persistent MLflow/other service data.
USAGE
}

while (($#)); do
  case "$1" in
    --with-k8s)
      [[ "$K8S_MODE" == "none" ]] || { echo "ERROR: --with-k8s and --helm are mutually exclusive." >&2; exit 2; }
      K8S_MODE="manifests"
      ;;
    --helm)
      [[ "$K8S_MODE" == "none" ]] || { echo "ERROR: --with-k8s and --helm are mutually exclusive." >&2; exit 2; }
      K8S_MODE="helm"
      ;;
    --no-traffic) START_TRAFFIC="false" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [[ "$K8S_MODE" != "none" && "$EUID" -eq 0 ]]; then
  echo "ERROR: Run this script as your normal user, not via SuperUser Admin. The script uses SuperUser Admin only for system-level installation; Minikube should not be run as root." >&2
  exit 1
fi

trap 'rc=$?; echo "ERROR: Deployment failed near line ${BASH_LINENO[0]:-unknown} (exit ${rc})." >&2; exit "$rc"' ERR

log() { printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

run_root() {
  if [[ "$EUID" -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

docker_cli() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  else
    run_root docker "$@"
  fi
}

compose() { docker_cli compose "$@"; }

wait_for_http() {
  local url="$1" label="$2" timeout="${3:-$HEALTH_TIMEOUT_SECONDS}"
  local start="$SECONDS" status=""
  log "Waiting for ${label} at ${url} (timeout: ${timeout}s)..."
  while (( SECONDS - start < timeout )); do
    status="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
    if [[ "$status" =~ ^[23][0-9][0-9]$ ]]; then
      log "${label} responded with HTTP ${status}."
      return 0
    fi
    sleep 2
  done
  echo "ERROR: ${label} did not become available at ${url} within ${timeout}s." >&2
  return 1
}

wait_for_api_health() {
  local start="$SECONDS"
  local body=""
  log "Waiting for FastAPI health endpoint at ${API_URL}/health..."
  while (( SECONDS - start < HEALTH_TIMEOUT_SECONDS )); do
    body="$(curl -fsS --max-time 3 "${API_URL}/health" 2>/dev/null || true)"
    if [[ -n "$body" ]] && printf '%s' "$body" | jq -e '.status == "healthy"' >/dev/null 2>&1; then
      log "FastAPI health check passed: ${body}"
      return 0
    fi
    sleep 2
  done
  echo "ERROR: FastAPI did not report {\"status\":\"healthy\"} within ${HEALTH_TIMEOUT_SECONDS}s." >&2
  compose logs --tail=100 api 2>/dev/null || true
  compose ps || true
  return 1
}

check_project_files() {
  local f
  for f in requirements.txt src/download_data.py src/train.py Dockerfile; do
    [[ -f "$f" ]] || fail "Required project file is missing: $f (run this script from the project root)."
  done
  if [[ ! -f compose.yml && ! -f compose.yaml && ! -f docker-compose.yml && ! -f docker-compose.yaml ]]; then
    fail "No Compose file found (expected compose.yml, compose.yaml, docker-compose.yml, or docker-compose.yaml)."
  fi
  [[ -d src ]] || fail "Required source directory is missing: src/"
}

# ---------------------------- Step 1: Base system ----------------------------
log "[1/8] Updating Ubuntu packages and installing base utilities..."
command -v apt-get >/dev/null 2>&1 || fail "This script currently targets Ubuntu/Debian systems with apt-get."
run_root apt-get update -y
run_root apt-get install -y \
  ca-certificates curl gnupg lsb-release git python3 python3-pip python3-venv \
  build-essential jq tar gzip

# ------------------------------ Step 2: Docker -------------------------------
log "[2/8] Checking Docker Engine and Compose plugin..."
DOCKER_ENGINE_MISSING="false"
DOCKER_COMPOSE_MISSING="false"
if ! command -v docker >/dev/null 2>&1; then
  DOCKER_ENGINE_MISSING="true"
fi
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE_MISSING="true"
fi

if [[ "$DOCKER_ENGINE_MISSING" == "true" || "$DOCKER_COMPOSE_MISSING" == "true" ]]; then
  . /etc/os-release
  [[ "${ID:-}" == "ubuntu" ]] || fail "Automatic Docker installation is configured for Ubuntu; install Docker Engine and the Compose plugin manually on this distribution."
  run_root install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | run_root gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  run_root chmod a+r /etc/apt/keyrings/docker.gpg
  UBUNTU_CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-$(lsb_release -cs)}}"
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu %s stable\n' \
    "$(dpkg --print-architecture)" "$UBUNTU_CODENAME" \
    | run_root tee /etc/apt/sources.list.d/docker.list >/dev/null
  run_root apt-get update -y
  if [[ "$DOCKER_ENGINE_MISSING" == "true" ]]; then
    run_root apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  else
    # Install only the missing plugin instead of replacing an existing Docker Engine.
    run_root apt-get install -y docker-compose-plugin
  fi
else
  log "Docker Engine and Compose plugin are already installed."
fi

if command -v systemctl >/dev/null 2>&1; then
  run_root systemctl enable --now docker
fi

docker_cli version >/dev/null
docker_cli compose version >/dev/null

# Add the invoking non-root account to the docker group where possible. Current
# script commands fall back to SuperUser Admin if the new group membership is not active.
TARGET_USER="${SUDO_USER:-${USER:-}}"
if [[ -n "$TARGET_USER" && "$TARGET_USER" != "root" ]] && getent group docker >/dev/null 2>&1; then
  if ! id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx docker; then
    run_root usermod -aG docker "$TARGET_USER" || true
    log "Added ${TARGET_USER} to the docker group. A new login session may be required for passwordless Docker access."
  fi
fi

# ----------------------------- Step 3: Python -------------------------------
log "[3/8] Creating and populating the project Python virtual environment..."
mkdir -p data models screenshots scripts logs monitoring/provisioning/datasources monitoring/provisioning/dashboards
check_project_files
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

# Validate Compose configuration early, before downloading/training.
docker compose config --quiet

# ---------------------------- Step 4: Ingest data ----------------------------
log "[4/8] Downloading/preparing the Cleveland Heart Disease dataset..."
"$PYTHON_BIN" src/download_data.py

# ---------------------------- Step 5: MLflow + training ----------------------
log "[5/8] Starting MLflow tracking server without deleting existing volumes..."

docker compose down -v --remove-orphans || true
for c in mlflow_server ml_api prometheus grafana; do 
    docker rm -f "$c" >/dev/null 2>&1 || true
done
docker compose up -d mlflow

if ! wait_for_http "$MLFLOW_URL" "MLflow tracking server" "$HEALTH_TIMEOUT_SECONDS"; then
  docker compose logs --tail=100 mlflow || true
  fail "MLflow failed to start. Inspect the logs above and the Compose MLflow configuration."
fi

export MLFLOW_TRACKING_URI="$MLFLOW_URL"
log "Training model and logging experiments to MLflow..."
"$PYTHON_BIN" src/train.py

[[ -s models/best_model.pkl ]] || fail "models/best_model.pkl was not created or is empty. Check src/train.py and its output path."
log "Champion model verified: models/best_model.pkl"

# ---------------------- Step 6: Compose app + monitoring ---------------------
log "[6/8] Building and starting the complete Docker Compose stack..."
compose up -d --build
compose ps
wait_for_api_health

# ------------------------ Step 7: Optional Kubernetes ------------------------
install_kubernetes_tools() {
  local machine_arch k8s_arch tmpdir kubectl_version helm_version
  machine_arch="$(uname -m)"
  case "$machine_arch" in
    x86_64) k8s_arch="amd64" ;;
    aarch64|arm64) k8s_arch="arm64" ;;
    *) fail "Unsupported CPU architecture for automatic Kubernetes tool installation: $machine_arch" ;;
  esac

  if ! command -v kubectl >/dev/null 2>&1; then
    log "Installing kubectl for Linux/${k8s_arch}..."
    kubectl_version="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
    tmpdir="$(mktemp -d)"
    curl -fsSLo "$tmpdir/kubectl" "https://dl.k8s.io/release/${kubectl_version}/bin/linux/${k8s_arch}/kubectl"
    run_root install -o root -g root -m 0755 "$tmpdir/kubectl" /usr/local/bin/kubectl
    rm -rf "$tmpdir"
  fi

  if ! command -v minikube >/dev/null 2>&1; then
    log "Installing Minikube for Linux/${k8s_arch}..."
    tmpdir="$(mktemp -d)"
    curl -fsSLo "$tmpdir/minikube" "https://storage.googleapis.com/minikube/releases/latest/minikube-linux-${k8s_arch}"
    run_root install -m 0755 "$tmpdir/minikube" /usr/local/bin/minikube
    rm -rf "$tmpdir"
  fi

  if [[ "$K8S_MODE" == "helm" ]] && ! command -v helm >/dev/null 2>&1; then
    log "Installing Helm 3 using the upstream installer..."
    tmpdir="$(mktemp -d)"
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 -o "$tmpdir/get-helm-3"
    run_root bash "$tmpdir/get-helm-3"
    rm -rf "$tmpdir"
  fi
}

start_minikube() {
  if docker info >/dev/null 2>&1; then
    minikube start --driver=docker
  elif command -v sg >/dev/null 2>&1 && getent group docker >/dev/null 2>&1; then
    # Use the freshly-added docker group for this one command, without requiring
    # the user to log out and back in before the first deployment.
    sg docker -c 'minikube start --driver=docker'
  else
    fail "Minikube requires the current user to access the Docker daemon. Re-login after docker-group membership is added, then rerun with $([[ "$K8S_MODE" == "helm" ]] && echo --helm || echo --with-k8s)."
  fi
}

test_kubernetes_service() {
  local service_name="$1" service_url=""
  [[ -n "$service_name" ]] || { echo "WARNING: Could not identify a Kubernetes Service exposing port 8000; skipping endpoint tests." >&2; return 0; }
  service_url="$(minikube service "$service_name" --url 2>/dev/null | head -n 1 || true)"
  if [[ -z "$service_url" ]]; then
    echo "WARNING: Minikube did not return a URL for service ${service_name}. Check service type/ports with kubectl get svc." >&2
    return 0
  fi
  log "Testing Kubernetes API at ${service_url}..."
  curl -fsS --max-time 15 "${service_url%/}/health" || fail "Kubernetes API health request failed at ${service_url}/health."
  printf '\n'
  curl -fsS --max-time 30 -X POST "${service_url%/}/predict" \
    -H 'Content-Type: application/json' \
    -d '{"age":63.0,"sex":1.0,"cp":1.0,"trestbps":145.0,"chol":233.0,"fbs":1.0,"restecg":2.0,"thalach":150.0,"exang":0.0,"oldpeak":2.3,"slope":3.0,"ca":0.0,"thal":6.0}'
  printf '\n'
}

if [[ "$K8S_MODE" != "none" ]]; then
  log "[7/8] Preparing optional Kubernetes deployment (${K8S_MODE})..."
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    log "The current shell does not yet have direct Docker access; Minikube startup will try the docker group."
  fi
  install_kubernetes_tools
  MINIKUBE_HOST_STATUS="$(minikube status --format='{{.Host}}' 2>/dev/null || true)"
  if [[ "$MINIKUBE_HOST_STATUS" != "Running" ]]; then
    start_minikube
  fi
  minikube status

  log "Building ${IMAGE_NAME} and loading it into Minikube..."
  docker_cli build -t "$IMAGE_NAME" .
  minikube image load "$IMAGE_NAME"

  if [[ "$K8S_MODE" == "manifests" ]]; then
    [[ -f k8s/deployment.yml ]] || fail "--with-k8s requested but k8s/deployment.yml was not found."
    kubectl apply -f k8s/deployment.yml
    if [[ -f k8s/service.yml ]]; then kubectl apply -f k8s/service.yml; fi
    kubectl rollout status "deployment/${K8S_DEPLOYMENT}" --timeout=180s
    kubectl get pods -o wide
    kubectl get svc
    if ! kubectl get svc "$K8S_SERVICE" >/dev/null 2>&1; then
      fail "Kubernetes Service '${K8S_SERVICE}' was not found. Ensure it is defined in k8s/deployment.yml or k8s/service.yml (if used)."
    fi
    test_kubernetes_service "$K8S_SERVICE"
  else
    [[ -d "$HELM_CHART" ]] || fail "--helm requested but chart directory '${HELM_CHART}' was not found."
    helm upgrade --install "$HELM_RELEASE" "$HELM_CHART" \
      --set image.repository=heart-disease-api \
      --set image.tag=v1 \
      --set image.pullPolicy=IfNotPresent \
      --wait --timeout=180s
    #  helm install heart-disease-release helm/heart-disease-app
    kubectl get deployments,pods,svc -l "app.kubernetes.io/instance=${HELM_RELEASE}" -o wide || true
    K8S_HELM_SERVICE="$(kubectl get svc -o json | jq -r '.items[] | select(any(.spec.ports[]?; .port == 8000 or .targetPort == 8000)) | .metadata.name' | head -n 1)"
    test_kubernetes_service "$K8S_HELM_SERVICE"
  fi
else
  log "[7/8] Kubernetes deployment skipped. Use --with-k8s or --helm to enable it."
fi

# ------------------------- Step 8: Traffic + summary -------------------------
log "[8/8] Setting up synthetic API traffic for monitoring dashboards..."
if [[ "$START_TRAFFIC" == "true" && -f tests/traffic_generator.py ]]; then
  mkdir -p logs
  if [[ -f logs/traffic_generator.pid ]]; then
    old_pid="$(cat logs/traffic_generator.pid 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      log "Traffic generator is already running (PID ${old_pid}); not starting a duplicate."
    else
      rm -f logs/traffic_generator.pid
    fi
  fi
  if [[ ! -f logs/traffic_generator.pid ]]; then
    nohup "$PYTHON_BIN" tests/traffic_generator.py "$API_URL" \
      >> logs/traffic_generator.log 2>&1 &
    echo "$!" > logs/traffic_generator.pid
    log "Traffic generator started (PID $(cat logs/traffic_generator.pid)); log: logs/traffic_generator.log"
  fi
elif [[ "$START_TRAFFIC" == "true" ]]; then
  log "tests/traffic_generator.py was not found; skipping synthetic traffic generation."
else
  log "Synthetic traffic generation disabled by --no-traffic."
fi

log "Deployment completed. Current Compose services:"
compose ps
cat <<SUMMARY

============================================================
MLOps Heart Disease Stack Deployment Complete
============================================================
MLflow Tracking UI : ${MLFLOW_URL}
FastAPI Prediction : ${API_URL}
Swagger API Docs   : ${API_URL}/docs
API Healthcheck    : ${API_URL}/health
Prometheus UI      : ${PROMETHEUS_URL}
Grafana Dashboard  : ${GRAFANA_URL}

Python environment: ${PROJECT_ROOT}/.venv
Champion model    : ${PROJECT_ROOT}/models/best_model.pkl
Traffic log       : ${PROJECT_ROOT}/logs/traffic_generator.log

Note: If Grafana still uses its default admin/admin credentials, change them
before exposing the dashboard beyond a local development environment.
============================================================
SUMMARY
