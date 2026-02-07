import os
import uuid
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from app.notes import bp
from app.extensions import db, csrf
from app.models import Note, Reminder
from app import ai


def _allowed_image(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', set())


@bp.route('/')
def list_notes():
    q = request.args.get('q', '').strip()
    if q:
        notes = Note.query.filter(
            db.or_(
                Note.title.ilike(f'%{q}%'),
                Note.content.ilike(f'%{q}%')
            )
        ).order_by(Note.updated_at.desc()).all()
    else:
        notes = Note.query.order_by(Note.updated_at.desc()).all()

    if request.headers.get('HX-Request'):
        return render_template('notes/_list_items.html', notes=notes)

    return render_template('notes/list.html', notes=notes, q=q)


@bp.route('/new')
def new_note():
    return render_template('notes/_form.html', note=None)


@bp.route('/', methods=['POST'])
def create_note():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()

    if not title:
        flash('Title is required.', 'error')
        return redirect(url_for('notes.list_notes'))

    note = Note(title=title, content=content)
    db.session.add(note)
    db.session.commit()

    flash('Note created successfully!', 'success')
    return redirect(url_for('notes.view_note', id=note.id))


@bp.route('/<int:id>')
def view_note(id):
    note = Note.query.get_or_404(id)
    reminders = Reminder.query.filter_by(note_id=note.id).all()
    return render_template('notes/detail.html', note=note, reminders=reminders)


@bp.route('/<int:id>/edit')
def edit_note(id):
    note = Note.query.get_or_404(id)
    if request.headers.get('HX-Request'):
        return render_template('notes/_form.html', note=note)
    return render_template('notes/_form.html', note=note)


@bp.route('/<int:id>', methods=['POST'])
def update_note(id):
    note = Note.query.get_or_404(id)
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()

    if not title:
        flash('Title is required.', 'error')
        return redirect(url_for('notes.edit_note', id=note.id))

    note.title = title
    note.content = content
    note.updated_at = datetime.utcnow()
    db.session.commit()

    flash('Note updated successfully!', 'success')
    return redirect(url_for('notes.view_note', id=note.id))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete_note(id):
    note = Note.query.get_or_404(id)

    # Clean up source image if it exists
    if note.source_image:
        img_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'notes', note.source_image)
        if os.path.exists(img_path):
            os.remove(img_path)

    db.session.delete(note)
    db.session.commit()

    if request.headers.get('HX-Request'):
        return ''

    flash('Note deleted.', 'success')
    return redirect(url_for('notes.list_notes'))


@bp.route('/scan-handwritten', methods=['POST'])
def scan_handwritten():
    """Upload a photo of a handwritten note and extract text using AI vision."""
    if 'image' not in request.files:
        flash('No image file uploaded.', 'error')
        return redirect(url_for('notes.list_notes'))

    file = request.files['image']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('notes.list_notes'))

    if not _allowed_image(file.filename):
        flash('Invalid image format. Please upload PNG, JPG, JPEG, GIF, or WebP.', 'error')
        return redirect(url_for('notes.list_notes'))

    # Read the image data
    image_data = file.read()
    ext = file.filename.rsplit('.', 1)[1].lower()

    # Map extension to media type
    media_type_map = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
    }
    media_type = media_type_map.get(ext, 'image/jpeg')

    # Save the image
    notes_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'notes')
    os.makedirs(notes_upload_dir, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex[:12]}.{ext}"
    img_path = os.path.join(notes_upload_dir, stored_name)
    with open(img_path, 'wb') as f:
        f.write(image_data)

    # Extract text using Claude vision
    result = ai.extract_handwritten_note(image_data, media_type)

    title = result.get('title', 'Handwritten Note')
    content = result.get('content', '')

    if not content or content.startswith('Could not extract') or content.startswith('Error'):
        flash(f'Failed to extract text: {content}', 'error')
        # Clean up saved image on failure
        if os.path.exists(img_path):
            os.remove(img_path)
        return redirect(url_for('notes.list_notes'))

    # Create the note
    note = Note(
        title=title,
        content=content,
        source='handwritten',
        source_image=stored_name,
    )
    db.session.add(note)
    db.session.commit()

    flash('Handwritten note scanned and converted!', 'success')
    return redirect(url_for('notes.view_note', id=note.id))


@bp.route('/note-image/<filename>')
def serve_note_image(filename):
    """Serve uploaded note images."""
    from flask import send_from_directory
    notes_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'notes')
    return send_from_directory(notes_upload_dir, filename)


@bp.route('/<int:id>/extract-reminders', methods=['POST'])
def extract_reminders(id):
    note = Note.query.get_or_404(id)

    suggestions = ai.extract_reminders_from_note(note.title, note.content)

    if not suggestions:
        if request.headers.get('HX-Request'):
            return '<div class="suggestions-panel"><p class="text-muted text-sm">No actionable items found in this note.</p></div>'
        flash('No actionable items found in this note.', 'info')
        return redirect(url_for('notes.view_note', id=note.id))

    return render_template('notes/_suggestions.html',
                           suggestions=suggestions,
                           note_id=note.id)


@bp.route('/accept-suggestion', methods=['POST'])
def accept_suggestion():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    suggested_date = request.form.get('suggested_date', '').strip()
    suggested_time = request.form.get('suggested_time', '').strip()
    note_id = request.form.get('note_id', type=int)

    if not title:
        return '<span class="text-danger text-sm">Title is required</span>', 400

    # Parse the due date/time
    try:
        if suggested_date and suggested_time:
            due_at = datetime.strptime(f"{suggested_date} {suggested_time}", "%Y-%m-%d %H:%M")
        elif suggested_date:
            due_at = datetime.strptime(suggested_date, "%Y-%m-%d").replace(hour=9, minute=0)
        else:
            due_at = datetime.utcnow()
    except ValueError:
        due_at = datetime.utcnow()

    reminder = Reminder(
        title=title,
        description=description,
        due_at=due_at,
        source='ai_suggested',
        note_id=note_id
    )
    db.session.add(reminder)
    db.session.commit()

    return render_template('notes/_accepted_suggestion.html', reminder=reminder)
