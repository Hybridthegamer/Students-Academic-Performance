import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import MinMaxScaler
from flask import current_app


FEATURE_COLUMNS = [
    'cgpa',
    'avg_ca_score',
    'avg_exam_score',
    'attendance_rate',
    'courses_registered',
    'level',
    'gender_Male',
    'gender_Female',
    'gender_Other',
]

DEPARTMENTS = [
    'Computer Science', 'Electrical Engineering', 'Mechanical Engineering',
    'Civil Engineering', 'Business Administration', 'Accounting', 'Economics',
    'Medicine', 'Law', 'Mass Communication', 'Other',
]

DEPARTMENT_COLS = [f'dept_{d.replace(" ", "_")}' for d in DEPARTMENTS]


def get_all_feature_columns():
    return FEATURE_COLUMNS + DEPARTMENT_COLS


def build_feature_vector(cgpa, avg_ca, avg_exam, attendance, courses, level, gender, department):
    """Construct a single-row DataFrame matching the training feature schema."""
    row = {
        'cgpa': cgpa,
        'avg_ca_score': avg_ca,
        'avg_exam_score': avg_exam,
        'attendance_rate': attendance,
        'courses_registered': courses,
        'level': level,
        'gender_Male': 1 if gender == 'Male' else 0,
        'gender_Female': 1 if gender == 'Female' else 0,
        'gender_Other': 1 if gender not in ('Male', 'Female') else 0,
    }

    normalized_dept = department.strip().title() if department else 'Other'
    if normalized_dept not in DEPARTMENTS:
        normalized_dept = 'Other'

    for dept in DEPARTMENTS:
        col = f'dept_{dept.replace(" ", "_")}'
        row[col] = 1 if dept == normalized_dept else 0

    return pd.DataFrame([row], columns=get_all_feature_columns())


def preprocess_dataframe(df, training_stats=None):
    """
    Preprocess a raw DataFrame of student records into model-ready features.

    Steps:
      1. Compute derived fields (CGPA, avg scores, attendance).
      2. Impute missing values with training-set means.
      3. Min-max scale continuous features.
      4. One-hot encode gender and department.
    """
    continuous_cols = ['cgpa', 'avg_ca_score', 'avg_exam_score', 'attendance_rate',
                       'courses_registered', 'level']

    if training_stats:
        for col in continuous_cols:
            if col in df.columns:
                df[col] = df[col].fillna(training_stats.get(f'{col}_mean', 0))
    else:
        for col in continuous_cols:
            if col in df.columns:
                df[col] = df[col].fillna(df[col].mean())

    # One-hot gender
    gender_dummies = pd.get_dummies(df['gender'], prefix='gender')
    for g in ['gender_Male', 'gender_Female', 'gender_Other']:
        if g not in gender_dummies.columns:
            gender_dummies[g] = 0

    # One-hot department
    dept_col = df['department'].apply(
        lambda d: d.strip().title() if isinstance(d, str) else 'Other'
    ).apply(lambda d: d if d in DEPARTMENTS else 'Other')
    dept_dummies = pd.get_dummies(dept_col, prefix='dept')
    for dept in DEPARTMENTS:
        col = f'dept_{dept.replace(" ", "_")}'
        if col not in dept_dummies.columns:
            dept_dummies[col] = 0

    feature_df = pd.concat([
        df[continuous_cols].reset_index(drop=True),
        gender_dummies[['gender_Male', 'gender_Female', 'gender_Other']].reset_index(drop=True),
        dept_dummies[[f'dept_{d.replace(" ", "_")}' for d in DEPARTMENTS]].reset_index(drop=True),
    ], axis=1)

    return feature_df


def load_scaler():
    path = current_app.config['SCALER_PATH']
    return joblib.load(path)


def load_training_stats():
    path = current_app.config['TRAINING_STATS_PATH']
    return joblib.load(path)
