from datetime import datetime, timedelta
from flask import render_template
from flask_login import login_required
from app.main import bp
from app.models import Note, Reminder, Document, EmailCache, DailySummary


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

    # Upcoming reminders (next 24h, not completed)
    upcoming_reminders = Reminder.query.filter(
        Reminder.due_at <= now + timedelta(hours=24),
        Reminder.due_at >= now,
        Reminder.is_completed == False
    ).order_by(Reminder.due_at.asc()).limit(5).all()

    # Overdue reminders
    overdue_reminders = Reminder.query.filter(
        Reminder.due_at < now,
        Reminder.is_completed == False
    ).order_by(Reminder.due_at.desc()).limit(5).all()

    # Recent notes
    recent_notes = Note.query.order_by(Note.updated_at.desc()).limit(5).all()

    # Get greeting based on time of day
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

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
