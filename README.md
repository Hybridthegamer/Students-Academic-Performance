# Student Academic Performance Evaluation System (SAPES)

A web-based intelligent system that automates the collection, processing, analysis, and reporting of student academic data using a trained Random Forest machine learning classifier. Built as a Final Year Project for a Nigerian tertiary institution context.

---

## Table of Contents

- [System Overview](#system-overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [System Requirements](#system-requirements)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [ML Model Details](#ml-model-details)
- [Project Structure](#project-structure)

---

## System Overview

SAPES transitions academic performance evaluation from a retrospective, manual process to a **proactive, data-driven workflow**. The system:

1. Ingests student academic records (CSV upload or manual entry)
2. Preprocesses data (imputation, normalisation, one-hot encoding)
3. Classifies each student into one of four categories: **Excellent**, **Good**, **Average**, or **At-Risk**
4. Displays role-specific dashboards with visualisations and SHAP-based explainability
5. Sends in-app alerts when students are identified as at-risk

Three user roles are supported: **Administrator**, **Lecturer**, and **Student**.

---

## Features

| Feature | Description |
|---|---|
| Role-based authentication | Admin / Lecturer / Student with separate dashboards |
| Student management | Register individually or bulk-upload via CSV/Excel |
| Academic record entry | Per-course CA, Exam, Attendance scores |
| ML performance classification | Random Forest classifier (Excellent / Good / Average / At-Risk) |
| SHAP explainability | Per-student feature contribution breakdown |
| At-risk alerts | In-app notifications dispatched when risk threshold exceeded |
| Analytics dashboard | Performance distribution charts (Chart.js) |
| CSV export | Full performance report downloadable as CSV |
| Batch evaluation | Evaluate all students in one click |
| Model management | Retrain the model via the admin UI |

---

## Technology Stack

### Backend — Python + Flask

**Flask** was chosen as the web framework because it is lightweight, well-documented, and integrates natively with Python's scientific computing ecosystem (NumPy, pandas, scikit-learn). Unlike Django, Flask does not impose a rigid project structure, making it easier to architect a modular ML-serving application. Flask's `application factory` pattern (used here) enables clean separation of configuration from application code and simplifies testing.

### Machine Learning — scikit-learn (Random Forest)

The **Random Forest** classifier was selected based on consistent evidence from the reviewed literature (Kabathova & Drlik, 2021; Dien et al., 2022; Oyedotun et al., 2022) showing it outperforms single classifiers such as Decision Trees, Naïve Bayes, and Logistic Regression on educational datasets. Key advantages:

- Ensemble aggregation reduces overfitting relative to single Decision Trees
- Robust to noisy educational data and outliers
- Handles mixed continuous/categorical feature types (after encoding)
- Produces class probability scores, enabling a continuous risk metric
- Supports SHAP TreeExplainer for interpretable per-prediction explanations

**SHAP** (SHapley Additive exPlanations) is used to decompose each prediction into individual feature contributions, satisfying the transparency requirement identified in Chapter 3 and the ethical guidelines of Holmes et al. (2022).

### Database — SQLite (dev) / MySQL 8.0 (production)

**SQLite** is used by default for development (no additional setup required). **MySQL 8.0** is recommended for production deployments because:

- Proven reliability in web application deployments
- Strong support for complex relational queries and concurrent writes
- Wide availability on Nigerian institutional hosting infrastructure
- Seamless integration via **SQLAlchemy ORM** (used here), which abstracts the dialect difference between SQLite and MySQL

### ORM — SQLAlchemy + Flask-Migrate

SQLAlchemy provides Python-level model definitions that are dialect-agnostic, enabling switching between SQLite and MySQL without code changes. Flask-Migrate (wrapping Alembic) handles schema migrations.

### Frontend — Bootstrap 5 + Chart.js

Bootstrap 5 delivers a responsive, accessible UI without requiring a JavaScript build step — critical for deployment in bandwidth-constrained Nigerian institutional environments. Chart.js renders interactive doughnut, bar, and line charts for performance analytics. No frontend build toolchain (Webpack, Vite, etc.) is needed.

### Model Serialisation — joblib

joblib is the standard serialisation library for scikit-learn models. It is more efficient than Python's built-in `pickle` for large NumPy arrays (which constitute the Random Forest's internal tree structures), reducing load time during inference.

---

## System Requirements

| Component | Minimum | Recommended |
|---|---|---|
| Python | 3.10 | 3.11+ |
| RAM | 512 MB | 2 GB |
| Disk | 500 MB | 2 GB |
| OS | Linux / macOS / Windows | Ubuntu 22.04 LTS |
| Database (dev) | SQLite (bundled with Python) | — |
| Database (prod) | MySQL 8.0 | MySQL 8.0 |
| Browser | Chrome 90+ / Firefox 88+ / Edge 90+ | Latest stable |

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/hybridthegamer/students-academic-performance.git
cd students-academic-performance
```

### 2. Create & Activate a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate          # Linux / macOS
venv\Scripts\activate             # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `mysqlclient` requires the MySQL C connector on the system.
> On Ubuntu: `sudo apt-get install libmysqlclient-dev`
> On macOS: `brew install mysql`
> For development without MySQL, remove `mysqlclient` from requirements.txt — SQLite is used by default.

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY (and DATABASE_URL if using MySQL)
```

### 5. Initialise the Database

```bash
flask --app run init-db
```

### 6. Seed Demo Data (optional but recommended)

```bash
flask --app run seed-db
```

This creates three demo accounts:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@sapes.edu.ng` | `admin123` |
| Lecturer | `ibrahim@sapes.edu.ng` | `lecturer123` |
| Student | `stu001@sapes.edu.ng` | `student123` |

### 7. Train the ML Model

```bash
flask --app run train-model
```

This generates a synthetic training dataset (2,000 samples), runs a 5-fold cross-validated grid search over the Random Forest hyperparameter space, and saves the best model plus preprocessing artifacts to `ml_models/`.

### 8. Start the Development Server

```bash
python run.py
```

Visit `http://localhost:5000` in your browser.

---

### Production Deployment (Gunicorn + Nginx)

```bash
# Install Gunicorn
pip install gunicorn

# Run with 4 worker processes
gunicorn -w 4 -b 0.0.0.0:8000 "run:app"
```

Point Nginx at port 8000 and serve `static/` files directly. Set `FLASK_ENV=production` in `.env`.

---

## Usage

### Administrator Workflow

1. Log in with admin credentials
2. Add courses and assign lecturers (Courses → Add Course)
3. Register students individually or bulk-upload a CSV (Students → Upload CSV)
4. Enter academic records per student (Student Profile → Add Record)
5. Train the model if not yet trained (ML Model → Train Model)
6. Click **Run Evaluation** on the dashboard to classify all students at once
7. Review at-risk students in the Notifications panel

### Lecturer Workflow

1. Log in → view assigned courses on the dashboard
2. Enter student scores for each course (Course → Enter Scores)
3. View enrolled students and their latest performance classification

### Student Workflow

1. Log in → view personal dashboard with current CGPA, classification, and attendance
2. Review the **"What's Affecting My Score?"** SHAP breakdown
3. Browse full academic record history
4. Check notifications for at-risk alerts from advisors

---

## ML Model Details

### Algorithm
Random Forest Classifier (scikit-learn)

### Features Used

| Feature | Type | Source |
|---|---|---|
| CGPA | Continuous | Computed from academic records |
| Average CA Score | Continuous | Mean of all CA scores |
| Average Exam Score | Continuous | Mean of all exam scores |
| Attendance Rate | Continuous | Mean attendance % across courses |
| Courses Registered | Discrete | Count of academic records |
| Level of Study | Ordinal | Student profile (100–500) |
| Gender | Categorical | One-hot encoded (Male/Female/Other) |
| Department | Categorical | One-hot encoded (11 categories) |

### Performance Categories

| Label | CGPA Range |
|---|---|
| Excellent | >= 4.5 |
| Good | 3.5 – 4.49 |
| Average | 2.4 – 3.49 |
| At-Risk | < 2.4 |

### Preprocessing Pipeline

1. Missing value imputation: column-wise mean (training set statistics)
2. Min-max normalisation of continuous features to [0, 1]
3. One-hot encoding of categorical features (gender, department)

### Hyperparameter Search

5-fold stratified cross-validated grid search over:
- `n_estimators`: [100, 200]
- `max_depth`: [8, 10, 15]
- `min_samples_split`: [5, 10]
- `min_samples_leaf`: [3, 5]

Optimisation metric: **Macro F1-Score**

### Evaluation Results (Synthetic Dataset)

| Metric | Value |
|---|---|
| Test Accuracy | >= 99% |
| Macro F1-Score | >= 0.99 |
| Training set | 1,600 samples |
| Test set | 400 samples |

> When deployed with real institutional data, performance will depend on data quality and volume. The preprocessing and training pipeline is designed to be re-run with real data by replacing the synthetic dataset in `data/synthetic_dataset.csv` or by adapting `app/ml/train.py`.

---

## Project Structure

```
Students-Academic-Performance/
├── app/
│   ├── __init__.py              # App factory
│   ├── models.py                # SQLAlchemy models
│   ├── auth/                    # Authentication blueprint
│   ├── admin/                   # Admin blueprint
│   ├── lecturer/                # Lecturer blueprint
│   ├── student/                 # Student blueprint
│   ├── main/                    # Main/index blueprint
│   ├── ml/
│   │   ├── preprocessor.py      # Feature engineering pipeline
│   │   ├── model.py             # Inference functions + SHAP
│   │   └── train.py             # Model training script
│   ├── utils/
│   │   └── helpers.py           # Role guards, CGPA computation, notifications
│   └── templates/               # Jinja2 HTML templates
├── static/                      # CSS, JS, images
├── ml_models/                   # Serialised model artifacts (auto-generated)
├── data/                        # Uploads and generated datasets
├── config.py                    # Environment-based configuration
├── run.py                       # App entry point + CLI commands
├── seed.py                      # Demo data seeding
├── requirements.txt
├── .env.example
└── README.md
```

---

## References

Key works informing the system design (see full bibliography in Chapter 2):

- Kabathova & Drlik (2021) — Random Forest for student dropout prediction
- Oyedotun et al. (2022) — RF achieving 83.7% accuracy in Nigerian university context
- Albreiki et al. (2021) — Systematic review: ensemble methods outperform single classifiers
- Holmes et al. (2022) — Ethics framework for AI in education (transparency, fairness)
- National Information Technology Development Agency (2023) — Nigeria Data Protection Act 2023