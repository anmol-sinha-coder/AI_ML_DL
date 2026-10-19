import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

def perform_eda(data_path="data/heart_disease.csv", output_dir="data/eda_plots"):
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(data_path)
    
    # Missing values
    print("--- Missing Values ---")
    print(df.isnull().sum()[df.isnull().sum() > 0])
    
    # Target Binarization (0 = No Heart Disease, 1 = Heart Disease present)
    df["target"] = (df["target"] > 0).astype(int)
    
    # 1. Class Balance Plot
    plt.figure(figsize=(6, 4))
    sns.countplot(x="target", data=df, palette="viridis")
    plt.title("Class Distribution (Heart Disease Target)")
    plt.xlabel("Target (0: Normal, 1: Disease)")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "class_balance.png"))
    plt.close()
    
    # 2. Histograms of Numerical Features
    num_cols = ["age", "trestbps", "chol", "thalach", "oldpeak"]
    df[num_cols].hist(figsize=(10, 8), bins=15, color="skyblue", edgecolor="black")
    plt.suptitle("Feature Distributions")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "feature_histograms.png"))
    plt.close()
    
    # 3. Correlation Heatmap
    plt.figure(figsize=(12, 8))
    sns.heatmap(df.corr(), annot=True, fmt=".2f", cmap="coolwarm", linewidths=0.5)
    plt.title("Feature Correlation Heatmap")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "correlation_heatmap.png"))
    plt.close()

    print(f"EDA plots saved successfully in '{output_dir}'.")

if __name__ == "__main__":
    perform_eda()