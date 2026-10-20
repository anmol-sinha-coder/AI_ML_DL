#!/usr/bin/env bash
# One-shot (re)deployment of the Heart Disease MLOps stack on a local Ubuntu/Debian box.
#
#   ./initial_deploy.sh                  # venv, tests, data, training, Compose stack, traffic, monitoring check
#   ./initial_deploy.sh --k8s            # ... plus Minikube deployment with plain manifests (alias --with-k8s)
#   ./initial_deploy.sh --helm           # ... plus Minikube deployment with the Helm chart (alias --with-helm)
#   ./initial_deploy.sh --no-traffic     # do not start scripts/generate_traffic.py in the background
#   ./initial_deploy.sh --reset          # wipe MLflow/Prometheus/Grafana volumes first (clean slate)
#   ./initial_deploy.sh --skip-install   # do not apt-install anything (tools already present)
#
# Safe to re-run. Run as a normal user (sudo is used only where needed).
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

K8S_MODE=""; RESET=0; SKIP_INSTALL=0; TRAFFIC=1
for arg in "$@"; do
  case "$arg" in
    --k8s|--with-k8s) K8S_MODE="manifests" ;;
    --helm|--with-helm) K8S_MODE="helm" ;;
    --no-traffic) TRAFFIC=0 ;;
    --reset) RESET=1 ;;
    --skip-install) SKIP_INSTALL=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { echo; echo "--> $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }
trap 'echo "ERROR: deployment failed near line ${LINENO} (exit $?)" >&2' ERR

[ "$EUID" -ne 0 ] || [ -z "$K8S_MODE" ] || die "run as a normal user for Kubernetes (minikube refuses root)"

wait_for() {  # wait_for <description> <timeout-seconds> <command...>
  local what="$1" limit="$2" waited=0; shift 2
  until "$@" >/dev/null 2>&1; do
    sleep 2; waited=$((waited + 2))
    if [ "$waited" -ge "$limit" ]; then
      $DOCKER compose ps || true; $DOCKER compose logs --tail 40 || true
      die "timed out after ${limit}s waiting for ${what}"
    fi
  done
}

echo "=================================================="
echo " Heart Disease MLOps stack deployment"
echo "=================================================="

# 1-2. System packages + Docker ----------------------------------------------
if [ "$SKIP_INSTALL" -eq 0 ]; then
  step "[1/9] Installing base packages"
  command -v apt-get >/dev/null || die "apt-get not found (Ubuntu/Debian expected); use --skip-install"
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg lsb-release git python3 python3-pip python3-venv build-essential
  if ! command -v docker >/dev/null 2>&1; then
    step "[2/9] Installing Docker Engine + Compose plugin"
    . /etc/os-release
    case "$ID" in ubuntu|debian) DOCKER_DISTRO="$ID" ;; *) DOCKER_DISTRO="ubuntu" ;; esac
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/${DOCKER_DISTRO}/gpg" | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${DOCKER_DISTRO} $(lsb_release -cs) stable" \
      | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER" || true
    sudo systemctl enable --now docker || true
  else
    step "[2/9] Docker already installed"
  fi
else
  step "[1-2/9] Skipping package installation (--skip-install)"
fi
command -v jq >/dev/null 2>&1 || true
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi
$DOCKER info >/dev/null 2>&1 || die "Docker daemon is not running (try: sudo systemctl start docker)"
$DOCKER compose version >/dev/null 2>&1 || die "'docker compose' plugin missing"
$DOCKER compose config -q || die "docker-compose.yml is invalid"

# 3. Python environment -------------------------------------------------------
step "[3/9] Python virtual environment + dependencies"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || die "Python >= 3.10 required (3.12 recommended)"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# 4. Quality gate ---------------------------------------------------------------
step "[4/9] Lint + unit tests (deployment aborts on failure)"
flake8 .
pytest -q

# 5. Data + EDA -----------------------------------------------------------------
step "[5/9] Dataset download/cleaning and EDA plots"
python -m src.download_data
python -m src.eda

# 6. MLflow + training ----------------------------------------------------------
step "[6/9] Starting MLflow tracking server and training models"
if [ "$RESET" -eq 1 ]; then $DOCKER compose down -v --remove-orphans || true; fi
$DOCKER compose down --remove-orphans >/dev/null 2>&1 || true          # keeps volumes
for c in mlflow_server ml_api prometheus grafana; do $DOCKER rm -f "$c" >/dev/null 2>&1 || true; done  # stale name clashes
$DOCKER compose up -d mlflow
wait_for "MLflow (port 5000)" 120 curl -fsS http://localhost:5000/health
export MLFLOW_TRACKING_URI=http://localhost:5000
python -m src.train
[ -s models/best_model.pkl ] || die "models/best_model.pkl was not created"
python -m src.inference

# 7. API + monitoring stack -----------------------------------------------------
step "[7/9] Building image and starting API, Prometheus, Grafana"
$DOCKER compose up -d --build
wait_for "API (port 8000)" 120 curl -fsS http://localhost:8000/health
wait_for "Prometheus (port 9090)" 90 curl -fsS http://localhost:9090/-/ready
wait_for "Grafana (port 3000)" 120 curl -fsS http://localhost:3000/api/health
scripts/smoke_test.sh http://localhost:8000

# 8. Traffic + monitoring verification -----------------------------------------
if [ "$TRAFFIC" -eq 1 ]; then
  step "[8/9] Starting background traffic (3 min demo profile) and verifying the monitoring chain"
  mkdir -p logs
  if [ -f logs/traffic_generator.pid ] && kill -0 "$(cat logs/traffic_generator.pid)" 2>/dev/null; then
    echo "traffic generator already running (PID $(cat logs/traffic_generator.pid))"
  else
    nohup python3 scripts/generate_traffic.py --url http://localhost:8000 --profile demo \
      >> logs/traffic_generator.log 2>&1 &
    echo $! > logs/traffic_generator.pid
    echo "traffic generator PID $(cat logs/traffic_generator.pid), log: logs/traffic_generator.log"
  fi
  echo "waiting 50 s for Prometheus to scrape ..."; sleep 50
  python3 scripts/verify_monitoring.py || echo "WARNING: some dashboard queries are empty - see output above"

  scripts/capture_evidence.sh all ; python3 scripts/capture_web_screenshots.py
else
  step "[8/9] Traffic skipped (--no-traffic)"
fi


# 9. Optional Kubernetes --------------------------------------------------------
if [ -n "$K8S_MODE" ]; then
  step "[9/9] Minikube / Kubernetes deployment (${K8S_MODE})"
  scripts/deploy_k8s.sh "--${K8S_MODE}"
else
  step "[9/9] Kubernetes skipped (use --k8s or --helm)"
fi

cat <<SUMMARY

==================================================
 Stack deployed
==================================================
 MLflow UI   : http://localhost:5000
 API docs    : http://localhost:8000/docs
 Prometheus  : http://localhost:9090   (Status > Targets, Alerts)
 Grafana     : http://localhost:3000   (admin / admin) -> dashboard "Heart Disease MLOps - Monitoring"
 Traffic     : python3 scripts/generate_traffic.py --profile demo
 Evidence    : scripts/capture_evidence.sh all ; python3 scripts/capture_web_screenshots.py
 Stop        : docker compose down        (add -v to wipe volumes)
==================================================
SUMMARY
