import os
import re
import logging
import markdown
from flask import Flask
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import DevelopmentConfig, ProductionConfig
from app.extensions import db, scheduler, csrf, login_manager


def create_app(config_class=None):
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')

    if config_class is None:
        if os.environ.get('FLASK_ENV') == 'production':
            config_class = ProductionConfig
        else:
            config_class = DevelopmentConfig
    app.config.from_object(config_class)

    # Fix for reverse proxies (Render, Heroku, etc.) so Flask generates
    # correct https:// URLs for OAuth callbacks and url_for(_external=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Configure logging so errors show in Render logs
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    if not app.debug:
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance'), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        if str(user_id) == '1':
            return User(id=1, username=app.config['APP_USERNAME'])
        return None

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
        # Strip HTML tags for clean preview text
        clean = re.sub(r'<[^>]+>', '', text)
        if len(clean) <= length:
            return clean
        return clean[:length].rsplit(' ', 1)[0] + '...'

    @app.template_filter('rich_content')
    def rich_content_filter(text):
        # Prepares note content for loading into the Quill editor. New notes are
        # already HTML; legacy notes are plain text whose spacing/tabs/newlines
        # would collapse when assigned to innerHTML, so convert them to
        # whitespace-preserving HTML.
        from markupsafe import escape
        if not text:
            return ''
        if re.search(r'<(p|br|div|h[1-6]|ul|ol|li|span|strong|em|b|i|u|s|a|blockquote|pre|code)\b', text, re.IGNORECASE):
            return text
        lines = []
        for line in text.split('\n'):
            if line.strip() == '':
                lines.append('<p><br></p>')
                continue
            escaped = str(escape(line))
            escaped = escaped.replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
            escaped = escaped.replace('  ', '&nbsp;&nbsp;')
            lines.append('<p>' + escaped + '</p>')
        return ''.join(lines)

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
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

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
