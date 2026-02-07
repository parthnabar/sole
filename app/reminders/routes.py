from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from app.reminders import bp
from app.extensions import db
from app.models import Reminder


@bp.route('/')
def list_reminders():
    filter_status = request.args.get('filter', 'all')

    if filter_status == 'pending':
        reminders = Reminder.query.filter_by(is_completed=False)\
            .order_by(Reminder.due_at.asc()).all()
    elif filter_status == 'completed':
        reminders = Reminder.query.filter_by(is_completed=True)\
            .order_by(Reminder.due_at.desc()).all()
    else:
        reminders = Reminder.query.order_by(
            Reminder.is_completed.asc(),
            Reminder.due_at.asc()
        ).all()

    pending_count = Reminder.query.filter_by(is_completed=False).count()
    completed_count = Reminder.query.filter_by(is_completed=True).count()

    if request.headers.get('HX-Request') and request.args.get('partial'):
        return render_template('reminders/_list_items.html',
                               reminders=reminders, filter_status=filter_status)

    return render_template('reminders/list.html',
                           reminders=reminders,
                           filter_status=filter_status,
                           pending_count=pending_count,
                           completed_count=completed_count)


@bp.route('/new')
def new_reminder():
    return render_template('reminders/_form.html', reminder=None)


@bp.route('/', methods=['POST'])
def create_reminder():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    due_date = request.form.get('due_date', '').strip()
    due_time = request.form.get('due_time', '').strip()

    if not title:
        flash('Title is required.', 'error')
        return redirect(url_for('reminders.new_reminder'))

    try:
        if due_date and due_time:
            due_at = datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
        elif due_date:
            due_at = datetime.strptime(due_date, "%Y-%m-%d").replace(hour=9, minute=0)
        else:
            flash('Due date is required.', 'error')
            return redirect(url_for('reminders.new_reminder'))
    except ValueError:
        flash('Invalid date format.', 'error')
        return redirect(url_for('reminders.new_reminder'))

    reminder = Reminder(
        title=title,
        description=description,
        due_at=due_at,
        source='manual'
    )
    db.session.add(reminder)
    db.session.commit()

    flash('Reminder created!', 'success')
    return redirect(url_for('reminders.list_reminders'))


@bp.route('/<int:id>/edit')
def edit_reminder(id):
    reminder = Reminder.query.get_or_404(id)
    return render_template('reminders/_form.html', reminder=reminder)


@bp.route('/<int:id>', methods=['POST'])
def update_reminder(id):
    reminder = Reminder.query.get_or_404(id)
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    due_date = request.form.get('due_date', '').strip()
    due_time = request.form.get('due_time', '').strip()

    if not title:
        flash('Title is required.', 'error')
        return redirect(url_for('reminders.edit_reminder', id=id))

    try:
        if due_date and due_time:
            reminder.due_at = datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
        elif due_date:
            reminder.due_at = datetime.strptime(due_date, "%Y-%m-%d").replace(hour=9, minute=0)
    except ValueError:
        flash('Invalid date format.', 'error')
        return redirect(url_for('reminders.edit_reminder', id=id))

    reminder.title = title
    reminder.description = description
    db.session.commit()

    flash('Reminder updated!', 'success')
    return redirect(url_for('reminders.list_reminders'))


@bp.route('/<int:id>/complete', methods=['POST'])
def toggle_complete(id):
    reminder = Reminder.query.get_or_404(id)
    reminder.is_completed = not reminder.is_completed
    db.session.commit()

    if request.headers.get('HX-Request'):
        return render_template('reminders/_reminder_item.html', r=reminder)

    return redirect(url_for('reminders.list_reminders'))


@bp.route('/<int:id>/dismiss', methods=['POST'])
def dismiss_reminder(id):
    reminder = Reminder.query.get_or_404(id)
    reminder.is_dismissed = True
    db.session.commit()

    if request.headers.get('HX-Request'):
        return ''

    return redirect(url_for('reminders.list_reminders'))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete_reminder(id):
    reminder = Reminder.query.get_or_404(id)
    db.session.delete(reminder)
    db.session.commit()

    if request.headers.get('HX-Request'):
        return ''

    flash('Reminder deleted.', 'success')
    return redirect(url_for('reminders.list_reminders'))
