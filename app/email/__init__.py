from flask import Blueprint

bp = Blueprint('email', __name__, template_folder='../templates/email')

from app.email import routes  # noqa: E402
