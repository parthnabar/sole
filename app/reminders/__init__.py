from flask import Blueprint

bp = Blueprint('reminders', __name__, template_folder='../templates/reminders')


@bp.before_request
def require_login():
    from flask_login import current_user
    if not current_user.is_authenticated:
        from flask import redirect, url_for, request
        return redirect(url_for('auth.login', next=request.url))


from app.reminders import routes  # noqa: E402
