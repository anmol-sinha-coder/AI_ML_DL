# Assignment-1 requirements checklist (50 marks)

Legend: **Done** = implemented and verified in code/tests; **You** = needs your own evidence or action.

## Tasks

| # | Requirement from the PDF | Marks | Status | Where | Your action / evidence |
|---|---|---|---|---|---|
| 1a | Obtain the dataset (download script or instructions) | 5 | Done | `src/download_data.py`, README | - |
| 1b | Clean and preprocess: missing values, encoding | | Done | `src/data_processing.py` -> `data/heart_disease_clean.csv` | - |
| 1c | EDA with professional visuals: histograms, correlation heatmap, class balance | | Done | `src/eda.py` -> `data/eda_plots/` (6 plots + summary CSV) | screenshots 02 |
| 2a | Final features: scaling, encoding | 8 | Done | `build_preprocessor()` (median/StandardScaler, mode/one-hot) | - |
| 2b | >= 2 classifiers (LogReg, Random Forest) | | Done | `src/train.py` | - |
| 2c | Document model selection and tuning | | Done | GridSearchCV grids, README "Modelling summary", MLflow CV CSV | write in report |
| 2d | Cross-validation + accuracy, precision, recall, ROC-AUC | | Done | 5-fold CV + hold-out, all four metrics logged | table in report |
| 3 | MLflow: params, metrics, artifacts, plots for all runs | 5 | Done | `src/train.py`, MLflow UI :5000 | screenshots 03 (auto) |
| 4a | Save final model in a reusable format | 7 | Done | `models/best_model.pkl` (+ MLflow model with signature) | - |
| 4b | Clean `requirements.txt` | | Done | `requirements.txt`, `requirements-serve.txt` | - |
| 4c | Preprocessing pipeline for full reproducibility | | Done | one sklearn Pipeline, seeds, `model_metadata.json` | - |
| 5a | Unit tests for data processing and model code | 8 | Done | `test/` - 40+ tests, ~93 % coverage | screenshot 04 |
| 5b | GitHub Actions: lint, tests, training | | Done | `.github/workflows/ci.yml` | push to GitHub: screenshots 05-06 |
| 5c | Artifacts/logging for each run | | Done | upload-artifact (models, mlruns, reports, logs, helm output) | screenshot 06 |
| 5d | Pipeline fails on code/test errors with clear logs | | Done | flake8 hard-fail, pytest, smoke test | failing run: screenshot 07 (Step 8) |
| 6a | Docker container for the API (FastAPI) | 5 | Done | `Dockerfile` | screenshot 08 |
| 6b | `/predict` accepts JSON, returns prediction + confidence | | Done | `src/app.py` | screenshots 10, 11 |
| 6c | Builds and runs locally with sample input | | Done | `initial_deploy.sh`, `scripts/smoke_test.sh` | screenshot 09-10 |
| 7a | Deploy to cloud or local Kubernetes (Minikube/Docker Desktop) | 7 | Done | `scripts/deploy_k8s.sh` | screenshots 12, 14 |
| 7b | Deployment manifest **or Helm chart** | | Done | `k8s/*.yml` **and** `helm/heart-disease-app/` | screenshot 13 |
| 7c | Expose via LoadBalancer or Ingress | | Done | `service.yml` (LoadBalancer), `ingress.yml`, Helm `ingress.enabled` | `minikube service ... --url` |
| 7d | Verify endpoints + deployment screenshots | | You | smoke test through the K8s URL | screenshots 12-14 |
| 8a | Logging of API requests | 3 | Done | JSON logs (stdout + `logs/api.log`) | screenshot 15 |
| 8b | Monitoring: Prometheus + Grafana (or logs dashboard) | | Done | `monitoring/`, 42-panel dashboard, alert rules | screenshots 16-17 (auto) |
| 9 | Report: setup, EDA/modelling, tracking, architecture, CI/CD + deploy screenshots, repo link | 2 | You | `docs/REPORT_OUTLINE.md`, `docs/architecture.png` | write the 10-page report |

## Deliverables

| Deliverable | Status | Notes |
|---|---|---|
| GitHub repo: code, Dockerfile(s), requirements | You | push (Step 7); repo link into README/report |
| Cleaned dataset + download script | Done | `data/heart_disease_clean.csv`, `src/download_data.py` |
| Notebooks/scripts for EDA, training, inference | Done | `src/eda.py`, `src/train.py`, `src/inference.py` (scripts are allowed by the PDF) |
| `test/` folder with unit tests | Done | note: folder is `test/` as named in the PDF |
| GitHub Actions YAML | Done | |
| Deployment manifests / Helm charts | Done | `k8s/`, `helm/` |
| Screenshot folder | You | `screenshots/` + automation |
| Final written report (10 pages, doc/docx/pdf) | You | outline provided |
| Deployed API URL or access instructions | Done | README + `docs/FINAL_STEPS.md` (local Minikube; cite `http://localhost:8000`, `minikube service ... --url`) |
| Short video of the whole pipeline | You | `docs/VIDEO_GUIDE.md`, `scripts/demo.sh` |

## Production-readiness requirements

| Requirement | Status | Proof |
|---|---|---|
| All scripts run from a clean setup using the requirements file | Done | clean-room venv test; `initial_deploy.sh` step 3 |
| Model serves correctly in an isolated environment (Docker build/test proof) | Done / You | `docker build` + `scripts/smoke_test.sh`; screenshots 08-10 + `capture_evidence.sh docker` log |
| Pipeline fails on code or test errors and gives clear logs | Done | Step 8 demo |
