# Report outline (10 pages) - Markdown/Word/PDF

| Page | Section | Content | Figures / screenshots |
|---|---|---|---|
| 1 | Title + summary | Problem, dataset, stack, repo URL, video URL, headline results | - |
| 2 | Setup / install | Prerequisites, `./initial_deploy.sh`, manual steps, ports | terminal 04 |
| 3 | Data + EDA | Source, cleaning, missing values (`ca` 4, `thal` 2), class balance 164/139 | EDA plots |
| 4 | Features + modelling | Pipeline, models, grids, CV and hold-out metrics, selection rule, model comparison table | ROC, confusion matrix |
| 5 | Experiment tracking | MLflow layout, what is logged, champion tagging, how to reproduce | MLflow 03 |
| 6 | Packaging + testing | requirements split, pickled pipeline, metadata, test matrix + coverage | pytest 04 |
| 7 | CI/CD | Workflow diagram, jobs, artifacts, failing-run demo | Actions 05-07 |
| 8 | Containerisation + API | Dockerfile decisions (slim, non-root, healthcheck), endpoints, sample request/response | docker 08-11 |
| 9 | Deployment | Minikube: manifests vs Helm, LoadBalancer/Ingress, rollout, scrape target for k8s | k8s 12-14 |
| 10 | Monitoring + conclusions | Logging format, Prometheus metrics, Grafana sections, alerts; limitations and future work | Prometheus/Grafana 16-17 |

Architecture diagram (`docs/architecture.png`) goes on page 1 or 2.

Honest limitations to mention: small dataset (303 rows), single-site Cleveland data, no clinical validation, pickled model
tied to library versions, local-only deployment, demo-grade Grafana credentials.

Convert Markdown to PDF/DOCX:
```bash
sudo apt install pandoc texlive-xetex
pandoc report.md -o report.pdf --pdf-engine=xelatex -V geometry:margin=2cm
pandoc report.md -o report.docx
```
