import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import pandas as pd
import os

# Set MLflow tracking URI (Placeholder for managed service tracking URI)
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("churn_prediction")

def train_churn_model():
    with mlflow.start_run():
        # Dummy Training Data Generation
        # In a real environment, query this data via the Feast Feature Store API
        data = {
            'total_transactions_30d': [10, 2, 5, 0, 20],
            'total_spend_30d': [500.0, 20.0, 150.0, 0.0, 2000.0],
            'churned': [0, 1, 0, 1, 0]
        }
        df = pd.DataFrame(data)
        
        X = df[['total_transactions_30d', 'total_spend_30d']]
        y = df['churned']
        
        # Hyperparameters
        n_estimators = 100
        max_depth = 5
        mlflow.log_param("n_estimators", n_estimators)
        mlflow.log_param("max_depth", max_depth)
        
        # Train Model
        clf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        clf.fit(X, y)
        
        # Evaluate
        preds = clf.predict(X)
        accuracy = accuracy_score(y, preds)
        mlflow.log_metric("accuracy", accuracy)
        
        # Log Model to Registry
        mlflow.sklearn.log_model(clf, "churn_model_rf")
        print(f"Model trained with accuracy {accuracy}")

if __name__ == "__main__":
    train_churn_model()
