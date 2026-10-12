FROM python:3.11-slim
 
WORKDIR /app
 
# Install EXACTLY what training used -- this is the whole point
COPY model_export/requirements.txt .
# Heavy-weight all required dependencies
# RUN pip install --no-cache-dir -r requirements.txt
# Install lightweight runtime packages required for scoring
# RUN pip install --no-cache-dir mlflow-skinny scikit-learn==1.5.0 pandas numpy
# Install runtime web & inference dependencies
RUN pip install --no-cache-dir "fastapi<0.115.0" "uvicorn[standard]" pandas scikit-learn mlflow-skinny
 
COPY model_export/ /app/model_export/

COPY score_batch.py . 
ENTRYPOINT ["python", "score_batch.py"]

COPY serve_churn.py .
EXPOSE 8001
CMD ["uvicorn", "serve_churn:app", "--host", "0.0.0.0", "--port", "8001"]
