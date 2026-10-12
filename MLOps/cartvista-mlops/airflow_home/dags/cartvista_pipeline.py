"""CartVista weekly retrain pipeline: data -> train x2 -> gate -> promote."""
from datetime import datetime, timedelta
import subprocess, json, pathlib, csv
from airflow.decorators import dag, task
 
PROJECT = pathlib.Path(__file__).resolve().parents[2]   # cartvista-mlops
AUC_GATE = 0.96          # a model below this bar must NOT become champion
 
def run(cmd):
    r = subprocess.run(cmd, cwd=PROJECT, shell=True,
                       capture_output=True, text=True)
    print(r.stdout, r.stderr)
    r.check_returncode()
    return r.stdout

def log_gate_failure(context):
    log_file = PROJECT / "gate_failures.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exception = context.get("exception")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] Quality Gate Failure: {exception}\n")
 
@dag(schedule="0 2 * * 1",  start_date=datetime(2026,1,1),  catchup=False,  tags=["cartvista"])
def cartvista_weekly_retrain():
 
    @task
    def refresh_data():
        run("python generate_data.py")
 
    @task
    def train_logreg():
        run("python train_tracked.py --model logreg --C 1.0")
 
    @task
    def train_rf():
        run("python train_tracked.py --model rf --n-estimators 200 --max-depth 8")

    @task
    def train_gb():
        run("python train_tracked.py --model gb --n-estimators 100 --max-depth 3 --learning-rate 0.1")
 
    @task(on_failure_callback=log_gate_failure)
    def validate_best() -> float:
        import mlflow
        from mlflow import MlflowClient
        mlflow.set_tracking_uri(f"sqlite:///{PROJECT}/mlflow.db")
        client = MlflowClient()
        exp = client.get_experiment_by_name("cartvista-churn")
        best = client.search_runs([exp.experiment_id],
                order_by=["metrics.test_auc DESC"], max_results=1)[0]
        auc = best.data.metrics["test_auc"]
        print(f"Best AUC this cycle: {auc:.4f} (gate: {AUC_GATE})")
        if auc < AUC_GATE:
            raise ValueError(f"Quality gate FAILED: {auc:.4f} < {AUC_GATE}")
        return auc
 
    @task
    def promote():
        run("python register_model.py")

    @task
    def score_weekly():
        # Export freshly promoted champion artifacts
        run("python export_champion.py")
        # Execute batch scoring container using mounted volume
        run(f"docker run --rm -v {PROJECT}:/data cartvista-scorer:v1 /data/churn_data.csv /data/scored.csv")



    @task(retries=2, retry_delay=timedelta(seconds=30))
    def train_logreg():
        run("python train_tracked.py --model logreg --C 1.0")

    @task(retries=2, retry_delay=timedelta(seconds=30))
    def train_rf():
        run("python train_tracked.py --model rf --n-estimators 200 --max-depth 8")

    @task(retries=2, retry_delay=timedelta(seconds=30))
    def train_rf():
        run("python train_tracked.py --model gb --n-estimators 200 --max-depth 6 --learning-rate 0.2")


    d = refresh_data()
    gate = validate_best()
    d >> [train_logreg(), train_rf()] >> gate >> promote() >> score_weekly()

 
cartvista_weekly_retrain()
