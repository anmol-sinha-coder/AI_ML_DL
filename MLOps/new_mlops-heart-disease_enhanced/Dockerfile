# Serving image for the heart-disease API.
# Build after training so that models/best_model.pkl exists:
#   python -m src.train && docker build -t heart-disease-api:v1 .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_PATH=/app/models/best_model.pkl \
    LOG_FILE=/app/logs/api.log

WORKDIR /app

# Lean runtime dependencies only (no MLflow / matplotlib / test tooling)
COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

COPY src/ /app/src/
COPY models/ /app/models/

# Run as an unprivileged user; /app/logs is writable for the request log
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/logs && chown -R appuser:appuser /app/logs
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
