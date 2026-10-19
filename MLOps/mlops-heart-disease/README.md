# MLOps :  Heart Disease Monitor - UCI Dataset

## Ports :

- FastAPI uvicorn host : 8000
- MlFlow : 5000
- Prometheus : 9090
- Grafana : 3000

# Heart Disease Prediction MLOps Pipeline

An end-to-end production-ready MLOps pipeline for predicting heart disease risk using the Cleveland Heart Disease dataset. This project covers automated data ingestion, exploratory data analysis, experiment tracking with MLflow, containerized serving with FastAPI, metrics scraping with Prometheus, visual monitoring with Grafana, and container orchestration via Docker Compose and Kubernetes (Minikube).

---

## 📁 Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI/CD workflow
├── Dockerfile                      # FastAPI production build image
├── docker-compose.yml              # Multi-container stack (MLflow, API, Prometheus, Grafana)
├── deploy.sh                       # One-click deployment script
├── requirements.txt                # Python dependencies
├── data/                           # Dataset storage & EDA outputs
│   └── heart_disease.csv
├── k8s/                            # Kubernetes deployment & service manifests
│   └── deployment.yaml
├── models/                         # Trained model artifacts directory
│   └── best_model.pkl
├── monitoring/                     # Monitoring configuration & dashboards
│   ├── grafana_dashboard.json
│   └── prometheus.yml
├── src/                            # Pipeline source code
│   ├── app.py                      # FastAPI inference app with Prometheus instrumentation
│   ├── download_data.py            # Data ingestion script
│   ├── eda.py                      # Exploratory Data Analysis & visual outputs
│   ├── inference.py                # Standalone inference validation script
│   └── train.py                    # Training script with MLflow logging
└── tests/
    └── test_pipeline.py            # Pytest suite for automated testing

```

---

## 🌐 Services & Port Reference

| Service | Technology | URL / Endpoint | Function |
| --- | --- | --- | --- |
| **MLflow UI** | MLflow Server | `http://localhost:5000` | Experiment tracking & model registry |
| **Prediction API** | FastAPI / Uvicorn | `http://localhost:8000` | REST API for model predictions |
| **API Health Check** | FastAPI | `http://localhost:8000/health` | Container readiness/liveness probe |
| **Prometheus** | Prometheus | `http://localhost:9090` | Metrics collection and storage |
| **Grafana** | Grafana | `http://localhost:3000` | Operational and performance dashboards |

---

## ⚡ Quickstart (Automated Deployment)

To deploy the entire stack automatically on a clean Linux instance:

```bash
# 1. Clone the repository and navigate into the project directory
git clone <repository-url>
cd mlops-heart-disease

# 2. Make the script executable
chmod +x initial_deploy.sh

# 3. Run automated setup (Docker Compose stack)
./initial_deploy.sh

# (Optional) Run automated setup including Kubernetes (Minikube) deployment
./initial_deploy.sh --with-k8s

```

---

## 🛠️ Manual Step-by-Step Deployment

Follow these steps to build, train, and deploy the stack manually.

### Step 1: Environment Setup

```bash
# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

```

### Step 2: Data Ingestion & EDA

```bash
# Download dataset from UCI Repository
python3 src/download_data.py

# (Optional) Run exploratory data analysis
python3 src/eda.py

```

### Step 3: Launch MLflow Tracking Server

Start only the MLflow container first so it can record training runs and save artifacts over HTTP:

```bash
# Start MLflow service
docker compose up -d mlflow

# Verify MLflow server health
curl -I http://localhost:5000

```

### Step 4: Model Training & Tracking

Train the machine learning model pipeline and log metrics, parameters, ROC curves, and saved models to MLflow:

```bash
# Point training script to active MLflow server
export MLFLOW_TRACKING_URI=http://localhost:5000

# Execute model training
python3 src/train.py

```

*This step saves the champion model locally to `models/best_model.pkl`.*

### Step 5: Verify Local Inference (Optional)

Test local model loading before containerization:

```bash
python3 src/inference.py

```

### Step 6: Launch Full Docker Stack

Build and deploy the API server, Prometheus, and Grafana containers:

```bash
# Build API image and launch all containers
docker compose up -d --build

# Verify container status
docker compose ps

# Test the FastAPI health check endpoint
curl http://localhost:8000/health

```

### Step 7: Sample Prediction Request

Send a sample payload to the API to confirm inference functionality:

```bash
curl -X POST "http://localhost:8000/predict" \
     -H "Content-Type: application/json" \
     -d '{
       "age": 63.0, "sex": 1.0, "cp": 1.0, "trestbps": 145.0,
       "chol": 233.0, "fbs": 1.0, "restecg": 2.0, "thalach": 150.0,
       "exang": 0.0, "oldpeak": 2.3, "slope": 3.0, "ca": 0.0, "thal": 6.0
     }'

```

---

## ☸️ Kubernetes (Minikube) Deployment

To deploy the FastAPI serving application to a local Kubernetes cluster:

```bash
# 1. Start Minikube cluster
minikube start

# 2. Build local API image
docker build -t heart-disease-api:v1 .

# 3. Load image into Minikube registry
minikube image load heart-disease-api:v1

# 4. Deploy resources to Kubernetes
kubectl apply -f k8s/deployment.yaml

# 5. Verify deployment rollout
kubectl rollout restart deployment heart-disease-api
kubectl get pods

# 6. Get public service URL
minikube service heart-disease-service --url

```

---

## 🧪 Testing & Code Quality

Run automated unit tests and code linting across the project:

```bash
# Run code linting
flake8 src/

# Run unit tests
pytest tests/

```

And hence, we have deployed an available ML model with available API backend endpoint for any business use case.
 
