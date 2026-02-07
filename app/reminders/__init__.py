from flask import Blueprint

bp = Blueprint('reminders', __name__, template_folder='../templates/reminders')

from app.reminders import routes  # noqa: E402
