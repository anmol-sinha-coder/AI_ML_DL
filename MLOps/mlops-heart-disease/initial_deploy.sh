#!/usr/bin/env bash
set -eo pipefail

echo "=================================================="
echo " Starting MLOps Heart Disease Stack Deployment "
echo "=================================================="

# 1. Update system and install base packages
echo "--> [1/8] Updating system packages & installing utilities..."
sudo apt-get update -y
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    jq

# 2. Install Docker & Docker Compose Plugin (if not installed)
if ! command -v docker &> /dev/null; then
    echo "--> [2/8] Installing Docker Engine..."
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    sudo usermod -aG docker "$USER"
    echo "Added $USER to docker group. Note: A new login shell may be required for non-sudo docker execution."
else
    echo "--> [2/8] Docker is already installed."
fi

# 3. Create Virtual Environment & Install Python Dependencies
echo "--> [3/8] Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Download Cleveland Heart Disease Dataset
echo "--> [4/8] Downloading raw dataset..."
python3 src/download_data.py

# 5. Start MLflow Tracking Server
echo "--> [5/8] Starting MLflow Tracking Server via Docker Compose..."
# Remove any broken volumes from previous attempts to ensure clean DB initialization
sudo docker compose down -v || true
sudo docker compose up -d mlflow

echo "--> Waiting for MLflow Tracking Server (port 5000) to become healthy..."
until curl -s http://localhost:5000 > /dev/null; do
    sleep 2
done
echo "MLflow is live!"

# 6. Execute Model Training & Track Experiments
echo "--> [6/8] Running model training script..."
export MLFLOW_TRACKING_URI=http://localhost:5000
python3 src/train.py

# Verify champion model artifact was generated
if [ ! -f "models/best_model.pkl" ]; then
    echo "ERROR: models/best_model.pkl was not created! Aborting deployment."
    exit 1
fi
echo "Champion model verified at models/best_model.pkl."

# 7. Build and Launch the Full Docker Stack
echo "--> [7/8] Building & starting API, Prometheus, and Grafana containers..."
sudo docker compose up -d --build

echo "--> Waiting for FastAPI Prediction API (port 8000) to respond..."
until curl -s http://localhost:8000/health | grep -q '"status":"healthy"'; do
    sleep 2
done

# 8. Optional: Install & Deploy on Minikube Cluster
if [ "$1" == "--with-k8s" ]; then
    echo "--> [8/8] Setting up Minikube & Kubernetes deployment..."
    
    if ! command -v kubectl &> /dev/null; then
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
        rm kubectl
    fi

    if ! command -v minikube &> /dev/null; then
        curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
        sudo install minikube-linux-amd64 /usr/local/bin/minikube
        rm minikube-linux-amd64
    fi

    minikube status || minikube start --driver=docker
    sudo docker build -t heart-disease-api:v1 .
    minikube image load heart-disease-api:v1
    
    kubectl apply -f k8s/deployment.yaml
    kubectl rollout restart deployment heart-disease-api
    
    echo "Kubernetes deployment complete!"
fi

echo "=================================================="
echo "       Stack Deployed Successfully!               "
echo "=================================================="
echo " - MLflow Tracking UI : http://localhost:5000"
echo " - FastAPI Prediction : http://localhost:8000"
echo " - API Healthcheck    : http://localhost:8000/health"
echo " - Prometheus Metrics : http://localhost:9090"
echo " - Grafana Dashboard  : http://localhost:3000"
echo "=================================================="