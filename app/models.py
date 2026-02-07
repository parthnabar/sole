from datetime import datetime, date
from app.extensions import db


class Note(db.Model):
    __tablename__ = 'note'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False, default='')
    source = db.Column(db.String(20), nullable=False, default='manual')  # manual, handwritten
    source_image = db.Column(db.String(255), nullable=True)  # filename of uploaded image
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    reminders = db.relationship('Reminder', backref='note', lazy=True, cascade='all, delete-orphan')

    @property
    def is_handwritten(self):
        return self.source == 'handwritten'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Document(db.Model):
    __tablename__ = 'document'

    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False, unique=True)
    file_type = db.Column(db.String(10), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    extracted_text = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"


class Reminder(db.Model):
    __tablename__ = 'reminder'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_at = db.Column(db.DateTime, nullable=False)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    is_dismissed = db.Column(db.Boolean, nullable=False, default=False)
    source = db.Column(db.String(20), nullable=False, default='manual')
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def is_due(self):
        return not self.is_completed and not self.is_dismissed and self.due_at <= datetime.utcnow()

    @property
    def is_overdue(self):
        return not self.is_completed and self.due_at < datetime.utcnow()

    @property
    def status_label(self):
        if self.is_completed:
            return 'completed'
        if self.is_overdue:
            return 'overdue'
        return 'pending'


class EmailCache(db.Model):
    __tablename__ = 'email_cache'

    id = db.Column(db.Integer, primary_key=True)
    gmail_id = db.Column(db.String(100), nullable=False, unique=True)
    thread_id = db.Column(db.String(100), nullable=True)
    subject = db.Column(db.String(500), nullable=True)
    sender = db.Column(db.String(255), nullable=True)
    snippet = db.Column(db.Text, nullable=True)
    body_text = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    # Triage fields
    priority = db.Column(db.String(20), nullable=True)  # high, medium, low
    needs_response = db.Column(db.Boolean, nullable=True, default=None)
    triage_reason = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)  # action_required, informational, promotional, social

    received_at = db.Column(db.DateTime, nullable=True)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def priority_label(self):
        return self.priority or 'unknown'

    @property
    def is_important(self):
        return self.priority == 'high' or self.needs_response is True


class DailySummary(db.Model):
    __tablename__ = 'daily_summary'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False)
    generated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class OAuthToken(db.Model):
    __tablename__ = 'oauth_token'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False, default='google')
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    scopes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def is_expired(self):
        if self.token_expiry is None:
            return True
        return datetime.utcnow() >= self.token_expiry
