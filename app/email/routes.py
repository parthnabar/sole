import os
import uuid
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app, session
from app.email import bp
from app.extensions import db, csrf
from app.models import EmailCache, OAuthToken
from app.email.gmail_service import get_oauth_token, get_gmail_service, fetch_recent_emails
from app import ai

# Allow HTTP for local development OAuth
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


def _apply_triage(email_obj):
    """Run AI triage on an email and set its fields. Returns True if triaged."""
    try:
        body = email_obj.body_text or email_obj.snippet or ''
        triage = ai.triage_email(
            email_obj.subject or '(No Subject)',
            email_obj.sender or 'Unknown',
            body
        )
        if triage:
            email_obj.priority = triage.get('priority', 'medium')
            email_obj.needs_response = triage.get('needs_response', False)
            email_obj.category = triage.get('category', 'informational')
            email_obj.triage_reason = triage.get('reason', '')
            return True
    except Exception:
        pass
    return False


def _get_filtered_emails(filter_type):
    """Return filtered email query based on filter type."""
    query = EmailCache.query

    if filter_type == 'needs_response':
        query = query.filter(EmailCache.needs_response == True)
    elif filter_type == 'important':
        query = query.filter(
            (EmailCache.priority == 'high') | (EmailCache.needs_response == True)
        )
    elif filter_type == 'high':
        query = query.filter(EmailCache.priority == 'high')
    elif filter_type == 'medium':
        query = query.filter(EmailCache.priority == 'medium')
    elif filter_type == 'low':
        query = query.filter(EmailCache.priority == 'low')

    return query.order_by(EmailCache.received_at.desc()).all()


@bp.route('/')
def inbox():
    token = get_oauth_token()
    is_connected = token is not None

    filter_type = request.args.get('filter', 'all')
    emails = _get_filtered_emails(filter_type)

    # Count for filter badges
    all_count = EmailCache.query.count()
    important_count = EmailCache.query.filter(
        (EmailCache.priority == 'high') | (EmailCache.needs_response == True)
    ).count()
    needs_response_count = EmailCache.query.filter(EmailCache.needs_response == True).count()

    return render_template('email/inbox.html',
                           emails=emails,
                           is_connected=is_connected,
                           current_filter=filter_type,
                           all_count=all_count,
                           important_count=important_count,
                           needs_response_count=needs_response_count)


@bp.route('/connect')
def connect_gmail():
    """Initiate Gmail OAuth2 flow."""
    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": current_app.config['GOOGLE_CLIENT_ID'],
                    "client_secret": current_app.config['GOOGLE_CLIENT_SECRET'],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=['https://www.googleapis.com/auth/gmail.readonly'],
            redirect_uri=url_for('email.oauth_callback', _external=True)
        )

        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        session['oauth_state'] = state

        return redirect(auth_url)
    except Exception as e:
        flash(f'Could not initiate Gmail connection: {str(e)}', 'error')
        return redirect(url_for('email.inbox'))


@bp.route('/callback')
def oauth_callback():
    """Handle OAuth2 callback from Google."""
    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": current_app.config['GOOGLE_CLIENT_ID'],
                    "client_secret": current_app.config['GOOGLE_CLIENT_SECRET'],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=['https://www.googleapis.com/auth/gmail.readonly'],
            redirect_uri=url_for('email.oauth_callback', _external=True),
            state=session.get('oauth_state')
        )

        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials

        # Store or update token
        token = get_oauth_token()
        if token:
            token.access_token = creds.token
            token.refresh_token = creds.refresh_token or token.refresh_token
            token.token_expiry = creds.expiry
            token.scopes = ','.join(creds.scopes) if creds.scopes else ''
            token.updated_at = datetime.utcnow()
        else:
            token = OAuthToken(
                provider='google',
                access_token=creds.token,
                refresh_token=creds.refresh_token,
                token_expiry=creds.expiry,
                scopes=','.join(creds.scopes) if creds.scopes else ''
            )
            db.session.add(token)

        db.session.commit()
        flash('Gmail connected successfully!', 'success')

    except Exception as e:
        flash(f'Failed to connect Gmail: {str(e)}', 'error')

    return redirect(url_for('email.inbox'))


@bp.route('/disconnect', methods=['POST'])
def disconnect_gmail():
    """Remove stored OAuth tokens."""
    token = get_oauth_token()
    if token:
        db.session.delete(token)
        db.session.commit()

    flash('Gmail disconnected.', 'success')
    return redirect(url_for('email.inbox'))


@bp.route('/refresh', methods=['POST'])
def refresh_emails():
    """Fetch new emails from Gmail, summarize and triage them."""
    token = get_oauth_token()
    if not token:
        flash('Please connect Gmail first.', 'error')
        return redirect(url_for('email.inbox'))

    try:
        service = get_gmail_service(token)
        fetched = fetch_recent_emails(service, max_results=5)

        new_count = 0
        for email_data in fetched:
            # Skip if already cached
            existing = EmailCache.query.filter_by(gmail_id=email_data['gmail_id']).first()
            if existing:
                continue

            # Generate summary
            summary = None
            try:
                summary = ai.summarize_email(
                    email_data['subject'],
                    email_data['sender'],
                    email_data['body_text'] or email_data['snippet']
                )
            except Exception:
                summary = None

            cached = EmailCache(
                gmail_id=email_data['gmail_id'],
                thread_id=email_data['thread_id'],
                subject=email_data['subject'],
                sender=email_data['sender'],
                snippet=email_data['snippet'],
                body_text=email_data['body_text'],
                summary=summary,
                received_at=email_data['received_at']
            )

            # Triage the new email
            _apply_triage(cached)

            db.session.add(cached)
            db.session.commit()
            new_count += 1

        # Re-summarize any existing emails missing summaries
        unsummarized = EmailCache.query.filter(
            (EmailCache.summary == None) | (EmailCache.summary == '')
        ).all()
        resummarized = 0
        for email in unsummarized:
            try:
                email.summary = ai.summarize_email(
                    email.subject,
                    email.sender,
                    email.body_text or email.snippet
                )
                resummarized += 1
            except Exception:
                pass

        # Triage any existing emails that haven't been triaged
        untriaged = EmailCache.query.filter(EmailCache.priority == None).all()
        triaged_count = 0
        for email in untriaged:
            if _apply_triage(email):
                triaged_count += 1

        db.session.commit()

        parts = []
        if new_count > 0:
            parts.append(f'Fetched {new_count} new email(s)')
        if resummarized > 0:
            parts.append(f'summarized {resummarized} email(s)')
        if triaged_count > 0:
            parts.append(f'triaged {triaged_count} email(s)')
        if parts:
            flash(f'{" and ".join(parts)}!', 'success')
        else:
            flash('No new emails found.', 'info')

    except Exception as e:
        flash(f'Error fetching emails: {str(e)}', 'error')

    if request.headers.get('HX-Request'):
        filter_type = request.args.get('filter', 'all')
        emails = _get_filtered_emails(filter_type)
        important_count = EmailCache.query.filter(
            (EmailCache.priority == 'high') | (EmailCache.needs_response == True)
        ).count()
        needs_response_count = EmailCache.query.filter(EmailCache.needs_response == True).count()
        return render_template('email/_email_list.html', emails=emails,
                               current_filter=filter_type,
                               important_count=important_count,
                               needs_response_count=needs_response_count)

    return redirect(url_for('email.inbox'))


@bp.route('/filter')
def filter_emails():
    """HTMX endpoint for filtering emails."""
    filter_type = request.args.get('filter', 'all')
    emails = _get_filtered_emails(filter_type)

    important_count = EmailCache.query.filter(
        (EmailCache.priority == 'high') | (EmailCache.needs_response == True)
    ).count()
    needs_response_count = EmailCache.query.filter(EmailCache.needs_response == True).count()

    return render_template('email/_email_list.html', emails=emails,
                           current_filter=filter_type,
                           important_count=important_count,
                           needs_response_count=needs_response_count)


@bp.route('/summarize', methods=['POST'])
def summarize_pasted():
    """Summarize a pasted email."""
    subject = request.form.get('subject', '').strip()
    sender = request.form.get('sender', '').strip()
    body = request.form.get('body', '').strip()

    if not body:
        flash('Please paste email content.', 'error')
        return redirect(url_for('email.inbox'))

    # Generate summary
    summary = ai.summarize_email(
        subject or '(No Subject)',
        sender or 'Unknown',
        body
    )

    cached = EmailCache(
        gmail_id=f"pasted-{uuid.uuid4().hex[:12]}",
        subject=subject or '(No Subject)',
        sender=sender or 'Pasted Email',
        snippet=body[:200],
        body_text=body,
        summary=summary,
        received_at=datetime.utcnow()
    )

    # Triage the pasted email too
    _apply_triage(cached)

    db.session.add(cached)
    db.session.commit()

    flash('Email summarized and triaged!', 'success')

    if request.headers.get('HX-Request'):
        emails = EmailCache.query.order_by(EmailCache.received_at.desc()).all()
        return render_template('email/_email_list.html', emails=emails,
                               current_filter='all')

    return redirect(url_for('email.inbox'))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete_email(id):
    email = EmailCache.query.get_or_404(id)
    db.session.delete(email)
    db.session.commit()

    if request.headers.get('HX-Request'):
        return ''

    return redirect(url_for('email.inbox'))
