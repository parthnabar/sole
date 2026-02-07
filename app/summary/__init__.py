from flask import Blueprint

bp = Blueprint('summary', __name__, template_folder='../templates/summary')

from app.summary import routes  # noqa: E402
