from datetime import datetime, date, timedelta
from flask import render_template, request, redirect, url_for, flash
from app.summary import bp
from app.extensions import db
from app.models import DailySummary, Note, Reminder, EmailCache, Document
from app import ai


@bp.route('/')
def daily_summary():
    today = date.today()
    summary = DailySummary.query.filter_by(date=today).first()

    # Past summaries
    past_summaries = DailySummary.query.filter(
        DailySummary.date < today
    ).order_by(DailySummary.date.desc()).limit(10).all()

    return render_template('summary/daily.html',
                           summary=summary,
                           past_summaries=past_summaries)


@bp.route('/generate', methods=['POST'])
def generate_summary():
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # Gather data
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

    # Include upcoming reminders (today + next 3 days)
    reminders_end = datetime.combine(today + timedelta(days=3), datetime.max.time())
    reminders = [
        {
            'title': r.title,
            'due_at': r.due_at.strftime('%b %d, %Y at %I:%M %p'),
            'is_completed': r.is_completed,
        }
        for r in Reminder.query.filter(
            Reminder.due_at >= today_start,
            Reminder.due_at <= reminders_end
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

    # Generate summary
    content = ai.generate_daily_summary(emails, notes, reminders, documents)

    # Save or update
    summary = DailySummary.query.filter_by(date=today).first()
    if summary:
        summary.content = content
        summary.generated_at = datetime.utcnow()
    else:
        summary = DailySummary(date=today, content=content)
        db.session.add(summary)

    db.session.commit()

    if request.headers.get('HX-Request'):
        return render_template('summary/_summary_content.html', summary=summary)

    flash('Daily summary generated!', 'success')
    return redirect(url_for('summary.daily_summary'))


@bp.route('/history/<date_str>')
def view_summary(date_str):
    try:
        summary_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'error')
        return redirect(url_for('summary.daily_summary'))

    summary = DailySummary.query.filter_by(date=summary_date).first_or_404()
    return render_template('summary/view.html', summary=summary)
