"""
Training script for the SAPES Random Forest classifier.

Generates a synthetic student performance dataset, trains and evaluates the model
using 5-fold cross-validated grid search, then serialises the best model plus
preprocessing artifacts to disk.

Run:
    python -m app.ml.train          (from the project root)
    or
    flask train-model               (via CLI command)
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    roc_auc_score, f1_score
)

LABELS = ['At-Risk', 'Average', 'Good', 'Excellent']
DEPARTMENTS = [
    'Computer Science', 'Electrical Engineering', 'Mechanical Engineering',
    'Civil Engineering', 'Business Administration', 'Accounting', 'Economics',
    'Medicine', 'Law', 'Mass Communication', 'Other',
]


def generate_synthetic_dataset(n_samples=2000, random_state=42):
    """
    Generate a realistic synthetic student dataset for model training.
    Feature distributions are based on ranges documented in Chapter 3.
    """
    rng = np.random.default_rng(random_state)

    # Base CGPA-driven classification assignment
    cgpa = rng.uniform(0.5, 5.0, n_samples)

    avg_ca = np.clip(cgpa / 5.0 * 30 + rng.normal(0, 5, n_samples), 0, 30)
    avg_exam = np.clip(cgpa / 5.0 * 70 + rng.normal(0, 8, n_samples), 0, 70)
    attendance = np.clip(cgpa / 5.0 * 60 + 30 + rng.normal(0, 10, n_samples), 0, 100)
    courses_registered = rng.integers(4, 9, n_samples).astype(float)
    level = rng.choice([100, 200, 300, 400, 500], n_samples)
    gender = rng.choice(['Male', 'Female'], n_samples)
    department = rng.choice(DEPARTMENTS, n_samples)

    # Assign performance label from CGPA
    def cgpa_to_label(c):
        if c < 1.5:
            return 'At-Risk'
        elif c < 2.4:
            return 'At-Risk'
        elif c < 3.5:
            return 'Average'
        elif c < 4.5:
            return 'Good'
        else:
            return 'Excellent'

    labels = np.array([cgpa_to_label(c) for c in cgpa])

    df = pd.DataFrame({
        'cgpa': np.round(cgpa, 2),
        'avg_ca_score': np.round(avg_ca, 2),
        'avg_exam_score': np.round(avg_exam, 2),
        'attendance_rate': np.round(attendance, 2),
        'courses_registered': courses_registered,
        'level': level.astype(float),
        'gender': gender,
        'department': department,
        'performance_category': labels,
    })

    return df


def build_features(df):
    gender_dummies = pd.get_dummies(df['gender'], prefix='gender')
    for col in ['gender_Male', 'gender_Female', 'gender_Other']:
        if col not in gender_dummies.columns:
            gender_dummies[col] = 0

    dept_col = df['department'].apply(
        lambda d: d.strip().title() if isinstance(d, str) else 'Other'
    ).apply(lambda d: d if d in DEPARTMENTS else 'Other')
    dept_dummies = pd.get_dummies(dept_col, prefix='dept')
    for dept in DEPARTMENTS:
        col = f'dept_{dept.replace(" ", "_")}'
        if col not in dept_dummies.columns:
            dept_dummies[col] = 0

    cont_cols = ['cgpa', 'avg_ca_score', 'avg_exam_score', 'attendance_rate', 'courses_registered', 'level']
    feat = pd.concat([
        df[cont_cols].reset_index(drop=True),
        gender_dummies[['gender_Male', 'gender_Female', 'gender_Other']].reset_index(drop=True),
        dept_dummies[[f'dept_{d.replace(" ", "_")}' for d in DEPARTMENTS]].reset_index(drop=True),
    ], axis=1)
    return feat


def train(model_dir, verbose=True):
    os.makedirs(model_dir, exist_ok=True)

    if verbose:
        print("Generating synthetic training dataset...")
    df = generate_synthetic_dataset(n_samples=2000)
    df.to_csv(os.path.join(model_dir, '..', 'data', 'synthetic_dataset.csv'), index=False)

    X = build_features(df)
    y = df['performance_category']

    # Compute and save training statistics for imputation
    cont_cols = ['cgpa', 'avg_ca_score', 'avg_exam_score', 'attendance_rate', 'courses_registered', 'level']
    training_stats = {f'{col}_mean': float(df[col].mean()) for col in cont_cols}
    joblib.dump(training_stats, os.path.join(model_dir, 'training_stats.joblib'))

    # Scale continuous features
    scaler = MinMaxScaler()
    X_cont = X[cont_cols].copy()
    X[cont_cols] = scaler.fit_transform(X_cont)
    joblib.dump(scaler, os.path.join(model_dir, 'scaler.joblib'))
    joblib.dump(list(X.columns), os.path.join(model_dir, 'feature_columns.joblib'))

    # Stratified split: 80% train, 20% test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    if verbose:
        print(f"Training set: {len(X_train)} samples | Test set: {len(X_test)} samples")
        print("Class distribution (train):")
        print(y_train.value_counts())

    # Grid search with 5-fold stratified cross-validation
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [8, 10, 15],
        'min_samples_split': [5, 10],
        'min_samples_leaf': [3, 5],
    }
    base_rf = RandomForestClassifier(random_state=42, n_jobs=-1)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    if verbose:
        print("Running grid search (5-fold CV)...")

    grid_search = GridSearchCV(
        base_rf, param_grid, cv=cv, scoring='f1_macro',
        n_jobs=-1, verbose=0
    )
    grid_search.fit(X_train, y_train)

    best_model = grid_search.best_estimator_
    if verbose:
        print(f"Best params: {grid_search.best_params_}")

    # Evaluate on held-out test set
    y_pred = best_model.predict(X_test)
    y_proba = best_model.predict_proba(X_test)

    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average='macro')
    report = classification_report(y_test, y_pred, target_names=LABELS, zero_division=0)

    if verbose:
        print(f"\nTest Accuracy : {acc:.4f}")
        print(f"Macro F1-Score: {f1:.4f}")
        print("\nClassification Report:")
        print(report)

    # Persist model
    joblib.dump(best_model, os.path.join(model_dir, 'random_forest_model.joblib'))

    # Save evaluation metrics
    metrics = {
        'accuracy': round(acc, 4),
        'macro_f1': round(f1, 4),
        'best_params': grid_search.best_params_,
        'classification_report': report,
        'n_train': len(X_train),
        'n_test': len(X_test),
    }
    with open(os.path.join(model_dir, 'model_metrics.json'), 'w') as fh:
        json.dump(metrics, fh, indent=2)

    if verbose:
        print(f"\nModel artifacts saved to {model_dir}")

    return best_model, metrics


if __name__ == '__main__':
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    model_dir = os.path.join(base, 'ml_models')
    os.makedirs(os.path.join(base, 'data'), exist_ok=True)
    train(model_dir, verbose=True)
