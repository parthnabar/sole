import base64
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from flask import current_app
from app.extensions import db
from app.models import OAuthToken

logger = logging.getLogger(__name__)


def get_oauth_token():
    """Get the stored OAuth token for Google."""
    return OAuthToken.query.filter_by(provider='google').first()


def get_credentials(token: OAuthToken):
    """Build Google credentials from stored token."""
    creds = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=current_app.config['GOOGLE_CLIENT_ID'],
        client_secret=current_app.config['GOOGLE_CLIENT_SECRET'],
        scopes=['https://www.googleapis.com/auth/gmail.readonly']
    )
    return creds


def refresh_token_if_needed(token: OAuthToken):
    """Refresh the access token if expired."""
    creds = get_credentials(token)

    if creds.expired and creds.refresh_token:
        logger.info("Access token expired, refreshing...")
        try:
            creds.refresh(Request())
            token.access_token = creds.token
            token.refresh_token = creds.refresh_token or token.refresh_token
            token.token_expiry = creds.expiry
            token.updated_at = datetime.utcnow()
            db.session.commit()
            logger.info("Token refreshed successfully. New expiry: %s", creds.expiry)
        except Exception as e:
            logger.error("Token refresh failed: %s", str(e))
            raise Exception(f"Failed to refresh token: {str(e)}")
    else:
        logger.info("Token still valid (expired=%s, has_refresh=%s)", creds.expired, bool(creds.refresh_token))

    return creds


def get_gmail_service(token: OAuthToken):
    """Build a Gmail API service object."""
    creds = refresh_token_if_needed(token)
    return build('gmail', 'v1', credentials=creds)


def fetch_recent_emails(service, max_results=20):
    """Fetch recent emails from Gmail."""
    results = service.users().messages().list(
        userId='me',
        maxResults=max_results,
        labelIds=['INBOX']
    ).execute()

    messages = results.get('messages', [])
    emails = []

    for msg_ref in messages:
        msg = service.users().messages().get(
            userId='me',
            id=msg_ref['id'],
            format='full'
        ).execute()

        headers = {h['name'].lower(): h['value'] for h in msg['payload']['headers']}

        # Extract body text
        body_text = extract_body(msg['payload'])

        # Parse date
        received_at = None
        date_str = headers.get('date', '')
        if date_str:
            try:
                received_at = parsedate_to_datetime(date_str)
            except Exception:
                pass

        emails.append({
            'gmail_id': msg['id'],
            'thread_id': msg.get('threadId'),
            'subject': headers.get('subject', '(No Subject)'),
            'sender': headers.get('from', 'Unknown'),
            'snippet': msg.get('snippet', ''),
            'body_text': body_text[:5000] if body_text else '',
            'received_at': received_at,
        })

    return emails


def extract_body(payload):
    """Extract plain text body from a Gmail message payload."""
    body_text = ''

    if payload.get('mimeType') == 'text/plain' and payload.get('body', {}).get('data'):
        body_text = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')
    elif payload.get('parts'):
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
                break
            elif part.get('parts'):
                body_text = extract_body(part)
                if body_text:
                    break

    return body_text
