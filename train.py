import pandas as pd
import xgboost as xgb
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import log_loss
import joblib
import optuna
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Loading telemetry dataset...")
    df = pd.read_csv("GUIDE_Test.csv", low_memory=False, on_bad_lines='skip', nrows=50000, encoding='utf-8')

    df['IncidentGrade'] = df['IncidentGrade'].fillna('Unknown')
    detector_counts = df.groupby('DetectorId')['IncidentGrade'].value_counts().unstack(fill_value=0)

    for col in ['TruePositive', 'FalsePositive']:
        if col not in detector_counts.columns:
            detector_counts[col] = 0

    detector_counts['total'] = detector_counts.sum(axis=1)
    detector_counts['historical_fp_rate'] = detector_counts['FalsePositive'] / detector_counts['total']
    detector_counts['historical_tp_rate'] = detector_counts['TruePositive'] / detector_counts['total']
    detector_counts.to_csv("detector_historical_stats.csv")

    df = df.merge(detector_counts['historical_fp_rate'], on='DetectorId', how='left')
    df['historical_fp_rate'] = df['historical_fp_rate'].fillna(0.0)

    features = ['Category', 'MitreTechniques', 'historical_fp_rate']
    X = df[features].copy()
    y = df['IncidentGrade']

    # Preprocessing
    X['MitreTechniques'] = X['MitreTechniques'].fillna('None')
    X['Category'] = X['Category'].fillna('Other')

    le_cat = LabelEncoder()
    le_mitre = LabelEncoder()
    le_target = LabelEncoder()

    # To handle unseen labels in inference, we map known classes here, and in inference we fall back to -1
    X['Category'] = le_cat.fit_transform(X['Category'].astype(str))
    X['MitreTechniques'] = le_mitre.fit_transform(X['MitreTechniques'].astype(str))
    y_encoded = le_target.fit_transform(y.astype(str))

    joblib.dump(le_cat, "le_cat.pkl")
    joblib.dump(le_mitre, "le_mitre.pkl")
    joblib.dump(le_target, "le_target.pkl")

    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.3, stratify=y_encoded, random_state=42)
    sample_weights = compute_sample_weight(class_weight='balanced', y=y_train)

    def objective(trial):
        params = {
            'objective': 'multi:softprob',
            'num_class': len(np.unique(y_encoded)),
            'eval_metric': 'mlogloss',
            'max_depth': trial.suggest_int('max_depth', 3, 9),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
            'n_estimators': trial.suggest_int('n_estimators', 50, 300),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0)
        }
        
        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train, sample_weight=sample_weights)
        
        y_pred_proba = model.predict_proba(X_test)
        loss = log_loss(y_test, y_pred_proba)
        return loss

    logger.info("Starting Optuna hyperparameter tuning...")
    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=10) # 10 trials for demonstration speed

    best_params = study.best_params
    best_params['objective'] = 'multi:softprob'
    best_params['num_class'] = len(np.unique(y_encoded))
    best_params['eval_metric'] = 'mlogloss'

    logger.info(f"Training final model with best params: {best_params}")
    final_model = xgb.XGBClassifier(**best_params)
    final_model.fit(X_train, y_train, sample_weight=sample_weights)

    joblib.dump(final_model, "triage_xgboost_model.pkl")
    logger.info("Preprocessing complete. Tuned XGBoost model successfully trained and exported.")

if __name__ == "__main__":
    main()