import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import joblib

from sklearn.model_selection import train_test_split, cross_validate
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score, roc_curve

import mlflow
import mlflow.sklearn


def build_preprocessing_pipeline():
    num_features = ["age", "trestbps", "chol", "thalach", "oldpeak"]
    cat_features = ["sex", "cp", "fbs", "restecg", "exang", "slope", "ca", "thal"]

    num_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])

    cat_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])

    preprocessor = ColumnTransformer(transformers=[
        ("num", num_transformer, num_features),
        ("cat", cat_transformer, cat_features)
    ])
    return preprocessor

def train_and_evaluate():
    data = pd.read_csv("data/heart_disease.csv")
    data["target"] = (data["target"] > 0).astype(int)

    X = data.drop("target", axis=1)
    y = data["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    preprocessor = build_preprocessing_pipeline()

    models = {
        "Logistic_Regression": LogisticRegression(C=1.0, max_iter=1000, random_state=42),
        "Random_Forest": RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    }

    MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("Heart_Disease_Classification")

    best_roc_auc = 0.0
    best_pipeline = None
    best_model_name = ""

    for model_name, clf in models.items():
        with mlflow.start_run(run_name=model_name):
            full_pipeline = Pipeline([
                ("preprocessor", preprocessor),
                ("classifier", clf)
            ])

            # Cross validation
            cv_results = cross_validate(
                full_pipeline, X_train, y_train, cv=5, 
                scoring=["accuracy", "precision", "recall", "roc_auc"]
            )

            # Fit on training set
            full_pipeline.fit(X_train, y_train)

            # Evaluate on test set
            y_pred = full_pipeline.predict(X_test)
            y_proba = full_pipeline.predict_proba(X_test)[:, 1]

            acc = accuracy_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred)
            rec = recall_score(y_test, y_pred)
            auc = roc_auc_score(y_test, y_proba)

            # Log parameters and metrics to MLflow
            if model_name == "Logistic_Regression":
                mlflow.log_param("C", 1.0)
                mlflow.log_param("max_iter", 1000)
            elif model_name == "Random_Forest":
                mlflow.log_param("n_estimators", 100)
                mlflow.log_param("max_depth", 5)

            mlflow.log_metric("cv_mean_roc_auc", np.mean(cv_results["test_roc_auc"]))
            mlflow.log_metric("test_accuracy", acc)
            mlflow.log_metric("test_precision", prec)
            mlflow.log_metric("test_recall", rec)
            mlflow.log_metric("test_roc_auc", auc)

            # ROC Curve Artifact
            fpr, tpr, _ = roc_curve(y_test, y_proba)
            plt.figure(figsize=(6, 4))
            plt.plot(fpr, tpr, label=f"{model_name} (AUC = {auc:.3f})")
            plt.plot([0, 1], [0, 1], 'k--')
            plt.xlabel("False Positive Rate")
            plt.ylabel("True Positive Rate")
            plt.title("ROC Curve")
            plt.legend()
            plot_path = f"data/{model_name}_roc.png"
            plt.savefig(plot_path)
            plt.close()
            mlflow.log_artifact(plot_path)

            # Log Model Artifact
            mlflow.sklearn.log_model(full_pipeline, "model")

            print(f"[{model_name}] Test Acc: {acc:.4f} | Test AUC: {auc:.4f}")

            if auc > best_roc_auc:
                best_roc_auc = auc
                best_pipeline = full_pipeline
                best_model_name = model_name

    # Save champion model locally
    os.makedirs("models", exist_ok=True)
    joblib.dump(best_pipeline, "models/best_model.pkl")
    print(f"Saved Champion Model ({best_model_name}) to 'models/best_model.pkl'.")

if __name__ == "__main__":
    train_and_evaluate()