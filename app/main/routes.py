from flask import render_template, redirect, url_for
from flask_login import current_user
from . import main


@main.route('/')
def index():
    if current_user.is_authenticated:
        routes = {
            'admin': 'admin.dashboard',
            'lecturer': 'lecturer.dashboard',
            'student': 'student.dashboard',
        }
        return redirect(url_for(routes.get(current_user.role, 'auth.login')))
    return redirect(url_for('auth.login'))
