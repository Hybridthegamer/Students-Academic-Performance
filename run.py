import os
from app import create_app, db
from app.models import User, Student, Lecturer, Course, AcademicRecord, PerformanceResult, Notification

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    return dict(
        db=db, User=User, Student=Student, Lecturer=Lecturer,
        Course=Course, AcademicRecord=AcademicRecord,
        PerformanceResult=PerformanceResult, Notification=Notification,
    )


@app.cli.command('init-db')
def init_db():
    """Create all database tables."""
    db.create_all()
    print('Database tables created.')


@app.cli.command('seed-db')
def seed_db():
    """Seed the database with demo data."""
    from seed import seed_demo_data
    seed_demo_data(app, db)


@app.cli.command('train-model')
def train_model():
    """Train the Random Forest model."""
    import os
    from app.ml.train import train
    model_dir = app.config['MODEL_DIR']
    os.makedirs(os.path.join(app.root_path, '..', 'data'), exist_ok=True)
    _, metrics = train(model_dir, verbose=True)
    print(f"Training complete. Accuracy: {metrics['accuracy']:.1%}")


if __name__ == '__main__':
    import sys
    if sys.platform == 'win32':
        # waitress is a production-grade pure-Python WSGI server for Windows
        # (gunicorn does not support Windows)
        try:
            from waitress import serve
            print('Starting SAPES on http://localhost:5000 (waitress)')
            serve(app, host='0.0.0.0', port=5000)
        except ImportError:
            app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        app.run(host='0.0.0.0', port=5000, debug=True)
