# MLOps - Labs

```markdown
# CartVista MLOps Pipeline: End-to-End Execution Guide (Labs 1–4)

This repository contains the complete MLOps architecture for the **CartVista Churn Prediction Microservice**, covering experiment tracking, model registry, batch scoring containerization, FastAPI serving, Prometheus/Grafana observability, drift detection, and production A/B testing[cite: 1, 2, 3, 4, 5].

---

## Workspace Setup & Dependencies

1. **Activate Virtual Environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate

```

2. **Install Core Requirements:**
```bash
pip install -r requirements.txt

```



---

## Lab 1: Experiment Tracking & Model Registry

1. **Generate Synthetic Churn Dataset:**
Generate `churn_data.csv` (~5,000 records with customer features and target churn status):


```bash
python generate_data.py

```


2. **Run Baseline Training (Untracked):**
Train an un-monitored scikit-learn model to establish baseline performance metrics:


```bash
python train_no_tracking.py

```


3. **Execute Tracked Parameter Sweeps:**
Run hyperparameter experiments logged directly to SQLite backend database `mlflow.db`:


```bash
# Sweep Logistic Regression models
python train_tracked.py --model logreg --C 0.1
python train_tracked.py --model logreg --C 1.0

# Sweep Random Forest models
python train_tracked.py --model rf --n-estimators 200 --max-depth 8

# Automated training loop
python train_auto.py

```


4. **Launch MLflow Tracking UI:**
Inspect parameters, evaluation metrics (`accuracy`, `roc_auc`), artifacts, and data fingerprints:


```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000

```


*Access UI in browser at `http://localhost:5000*`.


5. **Register Champion Model:**
Select the top-performing run and assign the `@champion` alias in the MLflow Model Registry:


```bash
python register_model.py

```


6. **Verify Model Registry Consumption:**
Load and run predictions using `@champion` alias directly from registry without local training imports:


```bash
python consume_model.py

```



---

## Lab 2: Containerization & Batch Inference

1. **Export Champion Model Artifacts:**
Export serialized champion model and dependency metadata to `./model_export`:


```bash
python export_champion.py

```


2. **Build Unified Scorer Docker Image:**
Build the Docker container image using `Dockerfile`:


```bash
docker build -t cartvista-scorer:v1 .

```


3. **Execute Isolated Batch Scoring Container:**
Run batch inference in an isolated container to produce `scored.csv`:


```bash
docker run --rm -v "$(pwd):/data" cartvista-scorer:v1 /data/churn_data.csv /data/scored.csv

```


*(Or run batch inference locally: `python score_batch.py churn_data.csv scored.csv`)*.



---

## Lab 3: Online Microservice Serving (FastAPI)

1. **Start FastAPI Serving Microservice:**
Launch online inference REST API on host port 8000:


```bash
uvicorn serve_churn:app --host 0.0.0.0 --port 8000

```


*(For asynchronous implementation: `uvicorn serve_churn_async:app --host 0.0.0.0 --port 8000`)*.


2. **Access Interactive Swagger Docs:**
Open browser at `http://localhost:8000/docs` to view API contracts (`/health`, `/predict`, `/predict-batch`).


3. **Execute Test Single Prediction Request:**
Send sample JSON customer payload to `/predict` endpoint:


```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"tenure_months": 12, "monthly_spend": 450.0, "orders_per_month": 3, "support_tickets": 1, "uses_discounts": 1, "app_sessions": 10}'
```[cite: 3]


```


4. **Run Latency & Performance Benchmark:**
Evaluate single vs batch request throughput and $p_{50}/p_{95}/p_{99}$ latency distributions:


```bash
python load_test.py

```



---

## Lab 4: Observability, Drift Detection & A/B Testing

1. **Launch Prometheus & Grafana Monitoring Stack:**
Spin up containerized monitoring infrastructure using `docker-compose.yml` and `prometheus.yml`:


```bash
docker compose up -d

```


* **Prometheus:** `http://localhost:9090`

* **Grafana:** `http://localhost:3000` (Credentials: `admin` / `cartvista`)




2. **Start Instrumented FastAPI Microservice:**
Launch monitored service exporting Prometheus metrics (`/metrics`):


```bash
uvicorn serve_churn_monitored:app --host 0.0.0.0 --port 8000

```


3. **Replay Traffic Drift Incident:**
Run automated shell script `execute_drift.sh` (or `traffic_generator.py`) to stream normal traffic followed by simulated coupon-campaign drift:


```bash
# Automated execution
chmod +x execute_drift.sh
./execute_drift.sh

```


*(Manual traffic step 1: `python traffic_generator.py --minutes 3`)*

*(Manual traffic step 2: `python traffic_generator.py --minutes 3 --drift`)*

4. **Quantify Feature Drift (PSI Check):**
Calculate Population Stability Index (PSI) between baseline data and live traffic:


```bash
python psi_check.py

```


5. **Train & Register Challenger Model:**
Create a challenger model version and register the `@challenger` alias in MLflow:


```bash
python champion_challenger_create.py

```


6. **Launch A/B Router Service:**
Run the A/B router splitting live incoming production traffic (90% `@champion` / 10% `@challenger`):


```bash
uvicorn serve_ab:app --host 0.0.0.0 --port 8000

```



---

## Repository Artifacts Reference

* **`train_tracked.py` / `train_auto.py**`: Model training scripts integrated with MLflow tracking.


* **`register_model.py` / `champion_challenger_create.py**`: Model registry alias management scripts (`@champion`, `@challenger`).


* **`serve_churn.py` / `serve_churn_monitored.py` / `serve_ab.py**`: FastAPI REST microservice implementations.


* **`traffic_generator.py` / `execute_drift.sh**`: Synthetic load and drift injection automation.


* **`psi_check.py`**: Statistical drift calculation script.


* **`Dockerfile` / `docker-compose.yml**`: Containerization and monitoring stack infrastructure configuration files.



```

```
