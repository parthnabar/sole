from datetime import datetime, date
from app.extensions import db
from app.models import Reminder, DailySummary, Note, EmailCache, Document
from app import ai


def check_due_reminders(app):
    """Check for due reminders - runs every 60 seconds."""
    with app.app_context():
        now = datetime.utcnow()
        due_count = Reminder.query.filter(
            Reminder.due_at <= now,
            Reminder.is_completed == False,
            Reminder.is_dismissed == False
        ).count()
        # The count is used by the notification polling endpoint
        # No push notifications; HTMX polling handles the UI update
        return due_count


def auto_generate_daily_summary(app):
    """Auto-generate daily summary - runs once per day."""
    with app.app_context():
        today = date.today()

        # Check if already generated
        existing = DailySummary.query.filter_by(date=today).first()
        if existing:
            return

        # Gather today's data
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        emails = [
            {
                'sender': e.sender,
                'subject': e.subject,
                'summary': e.summary,
                'snippet': e.snippet
            }
            for e in EmailCache.query.filter(
                EmailCache.fetched_at >= today_start,
                EmailCache.fetched_at <= today_end
            ).all()
        ]

        notes = [
            n.to_dict()
            for n in Note.query.filter(
                Note.updated_at >= today_start,
                Note.updated_at <= today_end
            ).all()
        ]

        reminders = [
            {
                'title': r.title,
                'due_at': r.due_at.isoformat(),
                'is_completed': r.is_completed,
            }
            for r in Reminder.query.filter(
                Reminder.due_at >= today_start,
                Reminder.due_at <= today_end
            ).all()
        ]

        documents = [
            {
                'original_name': d.original_name,
                'summary': d.summary,
            }
            for d in Document.query.filter(
                Document.uploaded_at >= today_start,
                Document.uploaded_at <= today_end
            ).all()
        ]

        if not any([emails, notes, reminders, documents]):
            return

        try:
            content = ai.generate_daily_summary(emails, notes, reminders, documents)
            summary = DailySummary(date=today, content=content)
            db.session.add(summary)
            db.session.commit()
        except Exception:
            db.session.rollback()
