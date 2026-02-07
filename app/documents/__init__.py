from flask import Blueprint

bp = Blueprint('documents', __name__, template_folder='../templates/documents')

from app.documents import routes  # noqa: E402
