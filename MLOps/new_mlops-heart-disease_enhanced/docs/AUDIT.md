# Assignment-1 audit: findings, fixes and verification status

Source of truth: *MLOps Assignment 01* (AIMLCZG523, 50 marks). Baseline = the `mlops-heart-disease` folder as supplied.

## 1. Requirement-by-requirement status

| # | Requirement (marks) | Baseline gap | Now |
|---|---|---|---|
| 1 | Data + EDA (5) | Only the raw file saved - **no cleaned dataset** (listed deliverable); EDA covered 5 numeric histograms, a countplot and a raw heatmap; seaborn `palette` deprecation warnings | `download_data.py` (2 mirrors, shape check, offline fallback) + `data_processing.py` -> `data/heart_disease_clean.csv`; EDA adds class balance (5-class + binary), histograms by class, boxplots, categorical-by-class, masked heatmap, missing-value chart, summary CSV |
| 2 | Features + models (8) | Two models but **no tuning**, only CV ROC-AUC logged (no CV accuracy/precision/recall), champion chosen on the **test set**, one preprocessor object shared by both pipelines | Per-model pipelines, stratified 5-fold GridSearchCV, all four CV metrics + hold-out metrics, selection on CV ROC-AUC, tuning grid documented in README/MLflow |
| 3 | Experiment tracking (5) | Params/metrics/ROC only; defaulted to `http://localhost:5000` so training **crashed whenever the server was down (incl. CI)** | Params, CV+test metrics, ROC, confusion matrix, feature importance, classification report, CV grid CSV, model+signature+input example, tags, champion tag; defaults to local `./mlruns`; fast, clear error if an HTTP server is unreachable |
| 4 | Packaging + reproducibility (7) | Training deps (MLflow, matplotlib) shipped in the API image; Python 3.10 in CI vs 3.12 in Docker; SQLAlchemy unpinned so a fresh install **breaks the MLflow server**; no model metadata | `requirements.txt` (full) + `requirements-serve.txt` (image); Python 3.12 everywhere; `sqlalchemy==2.0.29`, `setuptools==75.8.0` pinned; `model_metadata.json` (versions, metrics, params, run id); preprocessing lives inside the pickled pipeline |
| 5 | CI/CD + tests (8) | Tests only checked that files exist (no data/model logic); second flake8 call used `--exit-zero` (never fails); training step needed an MLflow server; **no artifacts uploaded**; `pytest` bare would not import `src` | 36 network-free tests (cleaning, preprocessing, training, MLflow logging, API contract, logging, metrics, download fallbacks), 93 % coverage; strict flake8; pytest -> train -> docker build + smoke test; JUnit/coverage/model/mlruns/logs uploaded on every run; `pythonpath` fixed |
| 6 | Containerisation (5) | `confidence` was P(disease) even when predicting "no disease"; `.dict()` deprecated; root user; no healthcheck/.dockerignore; no input validation | `/predict` returns prediction, `probability_disease`, `confidence` (of predicted class); range/enum validation (422); non-root image, HEALTHCHECK, `.dockerignore`; 503 when model missing |
| 7 | Deployment (7) | README/script applied `k8s/deployment.yaml` but the file was `deployment.yml` (**kubectl apply would fail**); unused MLflow pod in the API manifest; no rollout wait/verification | `k8s/deployment.yml` + `service.yml` (2 replicas, probes, resources, rolling update, non-root, LoadBalancer), optional `ingress.yml`, `hpa.yml`, `mlflow.yml`, plus a Helm chart; script waits for rollout and smoke-tests the URL |
| 8 | Monitoring + logging (3) | **No request logging at all**; Grafana had no datasource and the dashboard JSON was never mounted | JSON request/prediction logging (stdout + rotating file); custom Prometheus metrics; Grafana datasource + dashboard auto-provisioned (8 panels) |
| 9 | Documentation (2) | README mentioned a non-existent `deploy.sh`, no architecture diagram | README rewritten, `docs/architecture.png`, screenshot checklist, this audit |

Deliverable folder names: the PDF asks for a `test/` folder - `tests/` was renamed to `test/`.

## 2. Other fixes in the deploy script

`down -v` ran on **every** run (wiped MLflow history) -> now only with `--reset`; endless `until curl` loops -> timeouts with clear errors;
Ubuntu-only Docker repo URL -> Debian/Ubuntu aware; hard `sudo docker` -> auto-detects; lint+tests gate added before training;
smoke test + rollout status added; wrong K8s file name fixed.

## 3. What was verified here (Python 3.12, clean virtualenv built only from `requirements.txt`)

* `flake8 .` clean; `pytest` 36 passed; 93 % coverage of `src/`.
* `download_data` -> `eda` -> `train` -> `inference` run end-to-end; training against a **real MLflow 2.11.1 HTTP server started with the same flags as docker-compose** (2 runs, champion tag set).
* API run with **only `requirements-serve.txt`** under uvicorn: `scripts/smoke_test.sh` all PASS; JSON logs written to file; Prometheus metric names match every Grafana query.
* `docker compose config` valid; all YAML/JSON parse.

## 4. NOT verifiable in my sandbox (please run on your Linux box)

* `docker build` / `docker compose up`: the sandbox cannot pull from Docker Hub (HTTP 403). The Dockerfile uses only steps equivalent to those validated above.
* Minikube/kubectl, Grafana UI rendering, GitHub Actions execution, and the live UCI download (blocked here; the fallback path is tested).
* Screenshots, the 10-page report and the video are yours to produce (see `screenshots/README.md`).

## 5. Monitoring fix (second review round)

Reported symptom: Grafana panels "No data" with red error icons. Root cause reproduced with `promtool` on the shipped
`prometheus.yml`: a stray Grafana key (`apiVersion: 1`) made Prometheus exit at start-up. Fixes: clean config,
fixed datasource uid + `deleteDatasources`, 42-panel dashboard, additional API metrics, alert rules, a regression test
(`test/test_monitoring_config.py`), a CI `promtool` check and `scripts/verify_monitoring.py`.
Verified here against a real Prometheus 2.50.1 scraping the live API under generated traffic: every required dashboard
query returns data. Not verifiable here: Grafana rendering itself (binary not downloadable), Helm (`helm lint`
not available), Minikube.
