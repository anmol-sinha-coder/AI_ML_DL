"""Render docs/architecture.png (used in README and the report).

Usage:  python scripts/make_architecture_diagram.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture.png"
fig, ax = plt.subplots(figsize=(14, 8))
ax.set_xlim(0, 14)
ax.set_ylim(0, 8)
ax.axis("off")

COLORS = {"data": "#DCEBFA", "ml": "#E3F4E1", "ci": "#FCEBD3", "serve": "#EADCF5", "mon": "#FADADD"}


def box(x, y, w, h, text, kind):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.12",
                                fc=COLORS[kind], ec="#444", lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9.5)


def arrow(x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color="#333", lw=1.3))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, ha="center", fontsize=8, color="#333")


ax.text(7, 7.65, "Heart Disease MLOps - Architecture", ha="center", fontsize=15, weight="bold")

# Row 1: data + ML
box(0.3, 5.6, 2.4, 1.2, "UCI Heart Disease\n(Cleveland CSV)", "data")
box(3.2, 5.6, 2.4, 1.2, "download_data.py\nclean + impute plan\nheart_disease_clean.csv", "data")
box(6.1, 5.6, 2.4, 1.2, "eda.py\nplots + summary stats", "data")
box(9.0, 5.6, 2.6, 1.2, "train.py\nGridSearchCV (LR, RF)\nCV + hold-out metrics", "ml")
box(12.0, 5.6, 1.7, 1.2, "MLflow\nparams, metrics,\nplots, models", "ml")
arrow(2.7, 6.2, 3.2, 6.2)
arrow(5.6, 6.2, 6.1, 6.2)
arrow(8.5, 6.2, 9.0, 6.2)
arrow(11.6, 6.2, 12.0, 6.2)

# Row 2: packaging + serving
box(9.0, 3.6, 2.6, 1.2, "models/best_model.pkl\n(preprocess + classifier)\n+ model_metadata.json", "ml")
box(6.1, 3.6, 2.4, 1.2, "Docker image\nFastAPI /predict\nnon-root, healthcheck", "serve")
arrow(10.3, 5.6, 10.3, 4.8, "champion")
arrow(9.0, 4.2, 8.5, 4.2)

box(0.3, 3.6, 5.5, 1.2, "Runtime targets\nDocker Compose: API + MLflow + Prometheus + Grafana\n"
    "Minikube / K8s: Deployment x2 + LoadBalancer Service", "serve")
arrow(6.1, 4.2, 5.8, 4.2)

# Row 3: monitoring + clients
box(0.3, 1.4, 2.4, 1.2, "Client\nPOST /predict (JSON)\n-> prediction + confidence", "serve")
box(3.2, 1.4, 2.6, 1.2, "Request logging\nJSON logs: stdout +\nlogs/api.log", "mon")
box(6.1, 1.4, 2.4, 1.2, "Prometheus\nscrapes /metrics", "mon")
box(9.0, 1.4, 2.6, 1.2, "Grafana dashboard\nrate, latency, errors,\npredictions by class", "mon")
arrow(1.5, 2.6, 1.5, 3.6, "HTTP")
arrow(4.5, 3.6, 4.5, 2.6, "logs")
arrow(7.3, 3.6, 7.3, 2.6, "metrics")
arrow(8.5, 2.0, 9.0, 2.0)

# CI/CD band
ax.add_patch(FancyBboxPatch((0.3, 0.1), 13.4, 0.85, boxstyle="round,pad=0.05,rounding_size=0.12",
                            fc=COLORS["ci"], ec="#444", lw=1.2))
ax.text(7, 0.52, "GitHub Actions:  flake8  ->  pytest (+coverage)  ->  download/EDA  ->  train (MLflow)  ->  "
        "docker build + smoke test  ->  upload artifacts & logs", ha="center", va="center", fontsize=10)
fig.tight_layout()
OUT.parent.mkdir(exist_ok=True)
fig.savefig(OUT, dpi=140)
print("wrote", OUT)
