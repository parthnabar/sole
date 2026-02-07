from flask import Blueprint

bp = Blueprint('notes', __name__, template_folder='../templates/notes')


@bp.before_request
def require_login():
    from flask_login import current_user
    if not current_user.is_authenticated:
        from flask import redirect, url_for, request
        return redirect(url_for('auth.login', next=request.url))


from app.notes import routes  # noqa: E402
