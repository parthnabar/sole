import os
import markdown
from flask import Flask
from markupsafe import Markup
from app.config import DevelopmentConfig
from app.extensions import db, scheduler, csrf


def create_app(config_class=None):
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')

    if config_class is None:
        config_class = DevelopmentConfig
    app.config.from_object(config_class)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance'), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)

    # Register Jinja2 filters
    @app.template_filter('markdown')
    def markdown_filter(text):
        if not text:
            return ''
        return Markup(markdown.markdown(text, extensions=['extra', 'nl2br', 'sane_lists']))

    @app.template_filter('truncate_words')
    def truncate_words_filter(text, length=100):
        if not text:
            return ''
        if len(text) <= length:
            return text
        return text[:length].rsplit(' ', 1)[0] + '...'

    # Register context processor for notification count
    @app.context_processor
    def inject_notification_count():
        from datetime import datetime
        from app.models import Reminder
        try:
            count = Reminder.query.filter(
                Reminder.due_at <= datetime.utcnow(),
                Reminder.is_completed == False,
                Reminder.is_dismissed == False
            ).count()
        except Exception:
            count = 0
        return {'notification_count': count}

    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.notes import bp as notes_bp
    app.register_blueprint(notes_bp, url_prefix='/notes')

    from app.reminders import bp as reminders_bp
    app.register_blueprint(reminders_bp, url_prefix='/reminders')

    from app.documents import bp as documents_bp
    app.register_blueprint(documents_bp, url_prefix='/documents')

    from app.email import bp as email_bp
    app.register_blueprint(email_bp, url_prefix='/email')

    from app.summary import bp as summary_bp
    app.register_blueprint(summary_bp, url_prefix='/summary')

    # Create database tables
    with app.app_context():
        db.create_all()

    # Initialize scheduler
    scheduler.init_app(app)

    from app.tasks.scheduler import check_due_reminders, auto_generate_daily_summary
    scheduler.add_job(
        id='check_reminders',
        func=check_due_reminders,
        args=[app],
        trigger='interval',
        seconds=60,
        replace_existing=True
    )
    scheduler.add_job(
        id='auto_daily_summary',
        func=auto_generate_daily_summary,
        args=[app],
        trigger='cron',
        hour=8,
        minute=0,
        replace_existing=True
    )
    scheduler.start()

    return app
