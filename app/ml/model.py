import os
import json
import joblib
import numpy as np
import pandas as pd
from flask import current_app

from .preprocessor import build_feature_vector, get_all_feature_columns

LABELS = ['At-Risk', 'Average', 'Good', 'Excellent']

_model_cache = {}


def _load(key, path):
    if key not in _model_cache:
        _model_cache[key] = joblib.load(path)
    return _model_cache[key]


def get_model():
    return _load('model', current_app.config['MODEL_PATH'])


def get_scaler():
    return _load('scaler', current_app.config['SCALER_PATH'])


def get_training_stats():
    return _load('stats', current_app.config['TRAINING_STATS_PATH'])


def is_model_ready():
    return os.path.exists(current_app.config['MODEL_PATH'])


def predict_student(cgpa, avg_ca, avg_exam, attendance, courses, level, gender, department):
    """
    Run inference for a single student and return (label, probabilities_dict).
    """
    model = get_model()
    scaler = get_scaler()
    stats = get_training_stats()

    # Impute any None values with training means
    cgpa = cgpa if cgpa is not None else stats.get('cgpa_mean', 2.5)
    avg_ca = avg_ca if avg_ca is not None else stats.get('avg_ca_score_mean', 30.0)
    avg_exam = avg_exam if avg_exam is not None else stats.get('avg_exam_score_mean', 40.0)
    attendance = attendance if attendance is not None else stats.get('attendance_rate_mean', 75.0)
    courses = courses if courses is not None else stats.get('courses_registered_mean', 6)
    level = level if level is not None else 100

    feat_df = build_feature_vector(cgpa, avg_ca, avg_exam, attendance, courses, level, gender, department)

    # Scale continuous columns
    cont_cols = ['cgpa', 'avg_ca_score', 'avg_exam_score', 'attendance_rate', 'courses_registered', 'level']
    feat_df[cont_cols] = scaler.transform(feat_df[cont_cols])

    proba = model.predict_proba(feat_df)[0]
    class_idx = int(np.argmax(proba))
    label = LABELS[class_idx]
    risk_prob = float(proba[0])  # probability of At-Risk class

    proba_dict = {LABELS[i]: float(proba[i]) for i in range(len(LABELS))}
    return label, risk_prob, proba_dict


def predict_bulk(records_df):
    """
    Predict for a DataFrame with columns matching student feature schema.
    Returns (labels list, risk_probabilities list, proba_dicts list).
    """
    model = get_model()
    scaler = get_scaler()

    from .preprocessor import preprocess_dataframe, load_training_stats
    stats = get_training_stats()
    feat_df = preprocess_dataframe(records_df.copy(), training_stats=stats)

    cont_cols = ['cgpa', 'avg_ca_score', 'avg_exam_score', 'attendance_rate', 'courses_registered', 'level']
    feat_df[cont_cols] = scaler.transform(feat_df[cont_cols])

    probas = model.predict_proba(feat_df)
    labels = [LABELS[int(np.argmax(p))] for p in probas]
    risk_probs = [float(p[0]) for p in probas]
    proba_dicts = [{LABELS[i]: float(p[i]) for i in range(len(LABELS))} for p in probas]
    return labels, risk_probs, proba_dicts


def explain_prediction(cgpa, avg_ca, avg_exam, attendance, courses, level, gender, department):
    """
    Compute SHAP values for a single student prediction for interpretability.
    Returns a dict of {feature_name: shap_value}.
    """
    try:
        import shap
        model = get_model()
        scaler = get_scaler()
        stats = get_training_stats()

        cgpa = cgpa if cgpa is not None else stats.get('cgpa_mean', 2.5)
        avg_ca = avg_ca if avg_ca is not None else stats.get('avg_ca_score_mean', 30.0)
        avg_exam = avg_exam if avg_exam is not None else stats.get('avg_exam_score_mean', 40.0)
        attendance = attendance if attendance is not None else stats.get('attendance_rate_mean', 75.0)
        courses = courses if courses is not None else stats.get('courses_registered_mean', 6)
        level = level if level is not None else 100

        feat_df = build_feature_vector(cgpa, avg_ca, avg_exam, attendance, courses, level, gender, department)
        cont_cols = ['cgpa', 'avg_ca_score', 'avg_exam_score', 'attendance_rate', 'courses_registered', 'level']
        feat_df[cont_cols] = scaler.transform(feat_df[cont_cols])

        explainer = shap.TreeExplainer(model)
        shap_vals = explainer.shap_values(feat_df)

        # Use SHAP values for the predicted class
        label, _, _ = predict_student(cgpa, avg_ca, avg_exam, attendance, courses, level, gender, department)
        class_idx = LABELS.index(label)

        if isinstance(shap_vals, list):
            vals = shap_vals[class_idx][0]
        else:
            vals = shap_vals[0]

        feature_names = get_all_feature_columns()
        shap_dict = {feature_names[i]: float(vals[i]) for i in range(len(feature_names))}

        # Return only the meaningful human-readable features
        readable = {
            'CGPA': shap_dict.get('cgpa', 0),
            'Avg CA Score': shap_dict.get('avg_ca_score', 0),
            'Avg Exam Score': shap_dict.get('avg_exam_score', 0),
            'Attendance Rate': shap_dict.get('attendance_rate', 0),
            'Courses Registered': shap_dict.get('courses_registered', 0),
            'Level of Study': shap_dict.get('level', 0),
        }
        return readable

    except Exception:
        # Graceful fallback — return empty dict if SHAP fails
        return {}
