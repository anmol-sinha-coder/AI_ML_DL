#!/usr/bin/env bash
# One-shot (re)deployment of the Heart Disease MLOps stack on a local Ubuntu/Debian box.
#
#   ./initial_deploy.sh                 # venv + data + training + Docker Compose stack
#   ./initial_deploy.sh --with-k8s      # ... plus Minikube deployment
#   ./initial_deploy.sh --reset         # also wipe MLflow/Grafana volumes first (clean slate)
#   ./initial_deploy.sh --skip-install  # do not apt-install anything (tools already present)
#
# Safe to re-run: existing venv, Docker install and volumes are reused unless --reset.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

WITH_K8S=0; RESET=0; SKIP_INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --with-k8s) WITH_K8S=1 ;;
    --reset) RESET=1 ;;
    --skip-install) SKIP_INSTALL=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { echo; echo "--> $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

wait_for() {  # wait_for <description> <timeout-seconds> <command...>
  local what="$1" limit="$2"; shift 2
  local waited=0
  until "$@" >/dev/null 2>&1; do
    sleep 2; waited=$((waited + 2))
    [ "$waited" -lt "$limit" ] || die "Timed out after ${limit}s waiting for ${what}. Check: docker compose logs"
  done
}

echo "=================================================="
echo " Heart Disease MLOps stack deployment"
echo "=================================================="

# 1. System packages + Docker -------------------------------------------------
if [ "$SKIP_INSTALL" -eq 0 ]; then
  step "[1/8] Installing base packages"
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg lsb-release git python3 python3-pip python3-venv build-essential

  if ! command -v docker >/dev/null 2>&1; then
    step "[2/8] Installing Docker Engine + Compose plugin"
    . /etc/os-release
    case "$ID" in ubuntu|debian) DOCKER_DISTRO="$ID" ;; *) DOCKER_DISTRO="ubuntu" ;; esac
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/${DOCKER_DISTRO}/gpg" | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${DOCKER_DISTRO} $(lsb_release -cs) stable" \
      | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER" || true
  else
    step "[2/8] Docker already installed"
  fi
else
  step "[1-2/8] Skipping package installation (--skip-install)"
fi

# Use sudo for docker only if the current user cannot talk to the daemon yet
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi
$DOCKER info >/dev/null 2>&1 || die "Docker daemon is not running (try: sudo systemctl start docker)"
$DOCKER compose version >/dev/null 2>&1 || die "'docker compose' plugin missing"

# 3. Python environment --------------------------------------------------------
step "[3/8] Python virtual environment + dependencies"
command -v python3 >/dev/null || die "python3 not found"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || die "Python >= 3.10 required (3.12 recommended)"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# 4. Quality gate --------------------------------------------------------------
step "[4/8] Lint + unit tests (deployment aborts on failure)"
flake8 .
pytest -q

# 5. Data + EDA ----------------------------------------------------------------
step "[5/8] Dataset download/cleaning and EDA plots"
python -m src.download_data
python -m src.eda

# 6. MLflow server + training --------------------------------------------------
step "[6/8] Starting MLflow tracking server and training models"
if [ "$RESET" -eq 1 ]; then $DOCKER compose down -v --remove-orphans || true; for c in mlflow_server ml_api prometheus grafana; do $DOCKER rm -f "$c" >/dev/null 2>&1 || true; done fi
$DOCKER compose up -d mlflow
wait_for "MLflow (port 5000)" 120 curl -fsS http://localhost:5000/health
export MLFLOW_TRACKING_URI=http://localhost:5000
python -m src.train
[ -f models/best_model.pkl ] || die "models/best_model.pkl was not created"
python -m src.inference

# 7. API + monitoring stack ----------------------------------------------------
step "[7/8] Building image and starting API, Prometheus, Grafana"
$DOCKER compose up -d --build
wait_for "API (port 8000)" 120 curl -fsS http://localhost:8000/health
scripts/smoke_test.sh http://localhost:8000

# 8. Optional Kubernetes -------------------------------------------------------
if [ "$WITH_K8S" -eq 1 ]; then
  step "[8/8] Minikube / Kubernetes deployment"
  if ! command -v kubectl >/dev/null 2>&1; then
    curl -fsSLO "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm -f kubectl
  fi
  if ! command -v minikube >/dev/null 2>&1; then
    curl -fsSLO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm -f minikube-linux-amd64
  fi
  minikube status >/dev/null 2>&1 || minikube start --driver=docker
  $DOCKER build -t heart-disease-api:v1 .
  minikube image load heart-disease-api:v1
  kubectl apply -f k8s/deployment.yaml
  kubectl rollout restart deployment/heart-disease-api
  kubectl rollout status deployment/heart-disease-api --timeout=180s
  kubectl get pods,svc -l app=heart-disease-api
  K8S_URL="$(minikube service heart-disease-service --url | head -n1)"
  scripts/smoke_test.sh "$K8S_URL"
  echo "Kubernetes API URL: $K8S_URL"
else
  step "[8/8] Kubernetes skipped (use --with-k8s)"
fi

echo
echo "=================================================="
echo " Stack deployed successfully"
echo "=================================================="
echo " MLflow UI   : http://localhost:5000"
echo " API docs    : http://localhost:8000/docs"
echo " API health  : http://localhost:8000/health"
echo " Prometheus  : http://localhost:9090"
echo " Grafana     : http://localhost:3000  (admin / admin)"
echo " To stop     : docker compose down   (add -v to wipe volumes)"
echo "=================================================="
