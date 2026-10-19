# Screenshot evidence (capture these after deploying)

Save PNGs in this folder using these names, then embed them in the report.

| File | What to capture | Assignment task |
|---|---|---|
| `01_eda_plots.png` | `data/eda_plots/*` (class balance, histograms, heatmap) | 1 |
| `02_mlflow_runs.png` | MLflow UI experiment table (both runs, metrics columns) | 3 |
| `03_mlflow_run_detail.png` | One run: params, metrics, plots, model artifacts | 3 |
| `04_pytest_pass.png` | Terminal: `pytest` green + coverage | 5 |
| `05_github_actions_run.png` | Actions run with all steps green (+ artifacts list) | 5 |
| `06_github_actions_failure_demo.png` | (optional) run failing on a deliberate lint/test error | 5 |
| `07_docker_build_run.png` | `docker build`, `docker compose ps`, healthy containers | 6 |
| `08_predict_curl.png` | `curl /predict` with sample JSON and the response | 6 |
| `09_k8s_pods_svc.png` | `kubectl get pods,svc` + rollout status | 7 |
| `10_k8s_predict.png` | `scripts/smoke_test.sh <minikube url>` output | 7 |
| `11_api_logs.png` | `docker compose logs api` showing JSON request logs | 8 |
| `12_prometheus_targets.png` | Prometheus Status > Targets (api UP) | 8 |
| `13_grafana_dashboard.png` | Grafana "Heart Disease Model Monitoring" with traffic | 8 |

Generate traffic for the dashboard first:
`for i in $(seq 1 50); do scripts/smoke_test.sh >/dev/null; done`
