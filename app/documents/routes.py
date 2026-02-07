import os
import uuid
from flask import render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from app.documents import bp
from app.extensions import db
from app.models import Document
from app.documents.extractors import extract_text
from app import ai


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@bp.route('/')
def list_documents():
    documents = Document.query.order_by(Document.uploaded_at.desc()).all()
    return render_template('documents/list.html', documents=documents)


@bp.route('/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('documents.list_documents'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('documents.list_documents'))

    if not allowed_file(file.filename):
        flash('File type not supported. Use PDF, TXT, or DOCX.', 'error')
        return redirect(url_for('documents.list_documents'))

    # Generate safe server-side filename
    original_name = secure_filename(file.filename)
    file_ext = original_name.rsplit('.', 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{file_ext}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], stored_name)

    file.save(filepath)
    file_size = os.path.getsize(filepath)

    # Extract text
    try:
        extracted_text = extract_text(filepath, file_ext)
    except Exception as e:
        extracted_text = f"Error extracting text: {str(e)}"

    # Generate summary with AI
    summary = None
    if extracted_text and not extracted_text.startswith("Error"):
        try:
            summary = ai.summarize_document(original_name, extracted_text)
        except Exception:
            summary = None

    doc = Document(
        original_name=original_name,
        stored_name=stored_name,
        file_type=file_ext,
        file_size=file_size,
        extracted_text=extracted_text,
        summary=summary
    )
    db.session.add(doc)
    db.session.commit()

    flash('Document uploaded and processed!', 'success')

    if request.headers.get('HX-Request'):
        return render_template('documents/_document_card.html', doc=doc)

    return redirect(url_for('documents.view_document', id=doc.id))


@bp.route('/<int:id>')
def view_document(id):
    doc = Document.query.get_or_404(id)
    return render_template('documents/detail.html', doc=doc)


@bp.route('/<int:id>/analyze', methods=['POST'])
def analyze_doc(id):
    doc = Document.query.get_or_404(id)
    question = request.form.get('question', '').strip()

    if not question:
        return '<div class="qa-answer text-muted">Please enter a question.</div>'

    answer = ai.analyze_document(doc.extracted_text or '', question)
    return render_template('documents/_qa_answer.html', question=question, answer=answer)


@bp.route('/<int:id>/delete', methods=['POST'])
def delete_document(id):
    doc = Document.query.get_or_404(id)

    # Delete the physical file
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.stored_name)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(doc)
    db.session.commit()

    if request.headers.get('HX-Request'):
        return ''

    flash('Document deleted.', 'success')
    return redirect(url_for('documents.list_documents'))
