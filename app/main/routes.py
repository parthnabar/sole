from datetime import datetime, timedelta
from flask import render_template, jsonify, current_app
from flask_login import login_required, current_user
from app.main import bp
from app.models import Note, Reminder, Document, EmailCache, DailySummary, OAuthToken


@bp.route('/')
@login_required
def dashboard():
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Stats
    notes_count = Note.query.count()
    pending_reminders = Reminder.query.filter_by(is_completed=False).count()
    docs_count = Document.query.count()
    summaries_count = DailySummary.query.count()

    # Upcoming reminders (next 7 days, not completed)
    upcoming_reminders = Reminder.query.filter(
        Reminder.due_at <= now + timedelta(days=7),
        Reminder.due_at >= now,
        Reminder.is_completed == False
    ).order_by(Reminder.due_at.asc()).limit(10).all()

    # Overdue reminders
    overdue_reminders = Reminder.query.filter(
        Reminder.due_at < now,
        Reminder.is_completed == False
    ).order_by(Reminder.due_at.desc()).limit(5).all()

    # Recent notes
    recent_notes = Note.query.order_by(Note.updated_at.desc()).limit(5).all()

    # Get greeting based on time of day, with user's name
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    display_name = current_app.config.get('APP_DISPLAY_NAME', '') or current_user.username
    if display_name:
        greeting = f"{greeting}, {display_name}"

    return render_template('main/dashboard.html',
                           greeting=greeting,
                           notes_count=notes_count,
                           pending_reminders=pending_reminders,
                           docs_count=docs_count,
                           summaries_count=summaries_count,
                           upcoming_reminders=upcoming_reminders,
                           overdue_reminders=overdue_reminders,
                           recent_notes=recent_notes)


@bp.route('/api/notifications')
@login_required
def notifications():
    return render_template('partials/notification_bell.html')


@bp.route('/health')
@login_required
def health_check():
    """Debug endpoint to verify configuration on Render."""
    token = OAuthToken.query.filter_by(provider='google').first()
    email_count = EmailCache.query.count()

    return jsonify({
        'status': 'ok',
        'config': {
            'anthropic_key_set': bool(current_app.config.get('ANTHROPIC_API_KEY')),
            'anthropic_key_length': len(current_app.config.get('ANTHROPIC_API_KEY', '')),
            'google_client_id_set': bool(current_app.config.get('GOOGLE_CLIENT_ID')),
            'google_client_secret_set': bool(current_app.config.get('GOOGLE_CLIENT_SECRET')),
            'claude_model': current_app.config.get('CLAUDE_MODEL', 'NOT SET'),
        },
        'oauth': {
            'token_exists': token is not None,
            'token_expiry': str(token.token_expiry) if token else None,
            'has_refresh_token': bool(token.refresh_token) if token else False,
        },
        'data': {
            'cached_emails': email_count,
        }
    })
