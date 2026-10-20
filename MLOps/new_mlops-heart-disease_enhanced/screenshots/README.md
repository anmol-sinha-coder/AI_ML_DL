# Screenshot evidence

Two kinds of screenshots, both saved under `screenshots/`:

* **Web UIs - automatic** (`python3 scripts/capture_web_screenshots.py`) -> `screenshots/web/NN_name.png`
  API docs + Try-it-out, MLflow experiment/run/artifacts/compare, Prometheus targets/alerts/rules/queries,
  Grafana datasource/dashboard (one tall image with every panel) / alerts.
* **Terminal and GitHub - manual** with `scripts/shot.sh NAME` (area select) -> `screenshots/NAME.png`.
  Names below. Each has a matching text log from `scripts/capture_evidence.sh` in `screenshots/evidence/`.

| # | Screenshot | How | Task |
|---|---|---|---|
| 01 | `01_repo_tree` - `tree -L 2` (or file explorer) | manual | 9 |
| 02 | `02_eda_*` - EDA plots | already in `data/eda_plots/` | 1 |
| 03 | `03_mlflow_*` | automatic (`web/`) | 3 |
| 04 | `04_flake8_pytest` - green lint + tests + coverage | manual after `capture_evidence.sh tests` | 5 |
| 05 | `05_github_actions_green` - workflow run, all jobs green | manual (GitHub) | 5 |
| 06 | `06_github_actions_artifacts` - Artifacts section of the run | manual (GitHub) | 5 |
| 07 | `07_github_actions_failing` - run that fails on a deliberate error (see FINAL_STEPS step 9) | manual (GitHub) | 5 |
| 08 | `08_docker_build` - `docker build -t heart-disease-api:v1 .` finishing | manual | 6 |
| 09 | `09_docker_ps_health` - `docker compose ps` (healthy) | manual after `capture_evidence.sh docker` | 6 |
| 10 | `10_predict_curl` - sample JSON in, prediction + confidence out | manual | 6 |
| 11 | `11_api_swagger` | automatic (`web/`) | 6 |
| 12 | `12_k8s_pods_svc` - `kubectl get deploy,pods,svc -o wide` | manual | 7 |
| 13 | `13_helm_list_status` - `helm list`, `helm status heart-disease-api` | manual | 7 |
| 14 | `14_k8s_predict` - smoke test through the Minikube URL | manual | 7 |
| 15 | `15_api_logs` - JSON request log lines (`docker compose logs api`) | manual | 8 |
| 16 | `16_prometheus_*` | automatic (`web/`) | 8 |
| 17 | `17_grafana_*` - dashboard with traffic | automatic (`web/`) | 8 |
| 18 | `18_traffic_generator` - generator summary output | manual | 8 |

Order matters: capture 16-17 only **after** traffic has run for 3+ minutes
(`python3 scripts/generate_traffic.py`), otherwise the graphs are empty.
