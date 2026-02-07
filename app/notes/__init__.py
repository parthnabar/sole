from flask import Blueprint

bp = Blueprint('notes', __name__, template_folder='../templates/notes')

from app.notes import routes  # noqa: E402
