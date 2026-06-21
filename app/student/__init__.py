from flask import Blueprint

student = Blueprint('student', __name__)

from . import routes  # noqa: F401, E402
