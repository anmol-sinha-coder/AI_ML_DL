# Video guide - "short video recording of the overall pipeline"

Target length **6-8 minutes** (max 10), 1080p, voice-over, one continuous screen recording (cuts allowed).

## Before recording (15 min)
1. `./initial_deploy.sh --helm` once, so everything is already built and warm (skip image pulls on camera).
2. `python3 scripts/generate_traffic.py &` 5 min before recording so Grafana already has history.
3. Browser tabs in this order: GitHub Actions run, MLflow :5000, API docs :8000/docs, Prometheus :9090/targets,
   Grafana dashboard. Zoom 100-110 %, bookmarks bar hidden, notifications off (Do Not Disturb).
4. Terminal: font 16-18 pt, dark-on-light or high contrast, window ~140 columns, `clear` between scenes.
5. Run `scripts/demo.sh --auto` once (dry run), then `scripts/demo.sh --open` for the take.

## Tools
* **OBS Studio** (`sudo apt install obs-studio`): Scene = "Screen Capture (PipeWire)" + mic; 1920x1080, 30 fps, MP4 (Settings -> Output -> Recording format mp4).
* Simpler: **SimpleScreenRecorder** or GNOME's built-in recorder (Ctrl+Alt+Shift+R, no audio on some versions).
* Command line fallback: `ffmpeg -f x11grab -framerate 30 -video_size 1920x1080 -i :0.0 -f pulse -i default -c:v libx264 -preset veryfast -crf 23 demo.mp4`.
* Trim/compress: `ffmpeg -i demo.mp4 -vcodec libx264 -crf 26 -preset slow demo_small.mp4` (keep under the portal limit).

## Shot list (matches `scripts/demo.sh` scenes)

| Time | Scene | Show | Say (one sentence each) |
|---|---|---|---|
| 0:00 | Intro | Title slide or README + `docs/architecture.png` | Problem, dataset, stack, what the pipeline does |
| 0:40 | 1-2 Repo + quality gate | tree; `flake8`, `pytest` green | Tests cover data, model, API; pipeline fails on errors |
| 1:30 | 3-4 Data, tracking | EDA plots; MLflow runs table, champion run | Two tuned models, CV metrics, plots and model logged |
| 2:30 | 5-6 Docker + API | `docker compose ps`; curl `/predict`; invalid -> 422; Swagger | Containerised FastAPI returns prediction + confidence |
| 3:30 | 7 Traffic + logs | traffic generator; JSON logs | Every request is logged |
| 4:15 | 8-9 Prometheus + Grafana | Targets UP; Alerts; dashboard sections | Latency, errors, model behaviour, drift, resources |
| 5:45 | 11 Kubernetes + Helm | `kubectl get`, `helm list`, smoke test via Minikube URL | Same image deployed with manifests/Helm, LoadBalancer |
| 6:45 | 12 CI/CD | Actions run, artifacts, red failing run | Automated lint -> test -> train -> docker build |
| 7:30 | Wrap-up | Repo link, README | What I would improve (registry, auto-retraining, alerting) |

## Tips
* Rehearse once; speak slowly; mention file names as you open them.
* Do not wait for long commands on camera: pre-run and show output, or cut the pause in editing.
* Show real terminal output, not a slide, for anything the PDF calls "proof" (docker build/run, K8s, CI).
* Upload (e.g. Google Drive / YouTube unlisted) and paste the link in the report and README; keep the MP4 as a backup.
