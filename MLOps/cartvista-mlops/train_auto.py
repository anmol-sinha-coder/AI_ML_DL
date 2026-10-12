import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("cartvista-churn")

mlflow.sklearn.autolog()

df = pd.read_csv("churn_data.csv")
X, y = df.drop(columns=["churn"]), df["churn"]
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

with mlflow.start_run(run_name="rf-autolog"):
    model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    model.fit(X_tr, y_tr)
