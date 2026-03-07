import json
import base64
import anthropic
from flask import current_app


def get_client():
    """Lazy-initialize the Anthropic client."""
    return anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])


def summarize_email(subject: str, sender: str, body: str) -> str:
    """Summarize a single email into 2-3 sentences."""
    try:
        client = get_client()
        message = client.messages.create(
            model=current_app.config['CLAUDE_MODEL'],
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    "Summarize this email concisely in 2-3 sentences. "
                    "Focus on the key action items or information.\n\n"
                    f"From: {sender}\n"
                    f"Subject: {subject}\n\n"
                    f"{body[:3000]}"
                )
            }]
        )
        return message.content[0].text
    except Exception as e:
        return f"Could not generate summary: {str(e)}"


def triage_email(subject: str, sender: str, body: str) -> dict:
    """Analyze an email and return priority, whether it needs a response, category, and reason.

    Returns a dict with:
        - priority: "high", "medium", or "low"
        - needs_response: true/false
        - category: "action_required", "informational", "promotional", "social", "notification"
        - reason: short explanation of the triage decision
    """
    try:
        client = get_client()
        message = client.messages.create(
            model=current_app.config['CLAUDE_MODEL'],
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    "Analyze this email and determine its priority and whether it requires a response. "
                    "Return ONLY a JSON object with these fields:\n"
                    '- "priority": "high", "medium", or "low"\n'
                    '  - high = urgent, time-sensitive, requires action, from a real person expecting a reply\n'
                    '  - medium = useful information, might need action but not urgent\n'
                    '  - low = promotional, automated notifications, newsletters, no-reply addresses\n'
                    '- "needs_response": true or false (does the sender expect a reply from me?)\n'
                    '- "category": one of "action_required", "informational", "promotional", "social", "notification"\n'
                    '- "reason": one short sentence explaining your triage decision\n\n'
                    "Return ONLY valid JSON, no other text.\n\n"
                    f"From: {sender}\n"
                    f"Subject: {subject}\n\n"
                    f"{body[:3000]}"
                )
            }]
        )
        response_text = message.content[0].text.strip()
        # Extract JSON from response
        if response_text.startswith('{'):
            return json.loads(response_text)
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(response_text[start:end])
        return {}
    except (json.JSONDecodeError, Exception):
        return {}


def summarize_document(filename: str, text: str) -> str:
    """Summarize an uploaded document."""
    try:
        client = get_client()
        truncated = text[:8000]
        message = client.messages.create(
            model=current_app.config['CLAUDE_MODEL'],
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    f"Summarize this document in 3-5 sentences. "
                    f"Highlight the main topics and key points.\n\n"
                    f"Document: {filename}\n\n"
                    f"{truncated}"
                )
            }]
        )
        return message.content[0].text
    except Exception as e:
        return f"Could not generate summary: {str(e)}"


def extract_reminders_from_note(title: str, content: str) -> list:
    """Extract actionable items from a note, return structured list."""
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    weekday = datetime.now().strftime('%A')
    try:
        client = get_client()
        message = client.messages.create(
            model=current_app.config['CLAUDE_MODEL'],
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": (
                    "Analyze this note and extract any actionable items, tasks, deadlines, "
                    "or reminders. Return a JSON array of objects. Each object should have:\n"
                    '- "title": short description of the task\n'
                    '- "description": more detail if available\n'
                    '- "suggested_date": ISO date string (YYYY-MM-DD) if a date is mentioned, or null\n'
                    '- "suggested_time": time in HH:MM format if mentioned, or null\n\n'
                    f"Today's date is {today} ({weekday}). Resolve any relative dates "
                    f"like 'tomorrow', 'next week', 'Friday', etc. into actual YYYY-MM-DD dates.\n\n"
                    "If there are no actionable items, return an empty array [].\n"
                    "Return ONLY the JSON array, no other text.\n\n"
                    f"Note Title: {title}\n\n"
                    f"{content[:4000]}"
                )
            }]
        )
        response_text = message.content[0].text.strip()
        # Try to extract JSON from the response
        if response_text.startswith('['):
            return json.loads(response_text)
        # Try to find JSON array in the response
        start = response_text.find('[')
        end = response_text.rfind(']') + 1
        if start != -1 and end > start:
            return json.loads(response_text[start:end])
        return []
    except (json.JSONDecodeError, Exception):
        return []


def generate_daily_summary(emails: list, notes: list,
                           reminders: list, documents: list) -> str:
    """Generate a daily briefing combining all data sources."""
    try:
        client = get_client()

        sections = []

        if emails:
            email_text = "\n".join(
                f"- From {e.get('sender', 'Unknown')}: {e.get('subject', 'No subject')} "
                f"({e.get('summary', e.get('snippet', 'No summary'))})"
                for e in emails[:10]
            )
            sections.append(f"## Emails Today\n{email_text}")

        if notes:
            notes_text = "\n".join(
                f"- {n.get('title', 'Untitled')}: {n.get('content', '')[:100]}"
                for n in notes[:10]
            )
            sections.append(f"## Notes Created/Updated Today\n{notes_text}")

        if reminders:
            reminder_text = "\n".join(
                f"- {'[COMPLETED] ' if r.get('is_completed') else ''}"
                f"{r.get('title', 'Untitled')} (due: {r.get('due_at', 'unknown')})"
                for r in reminders[:10]
            )
            sections.append(f"## Reminders\n{reminder_text}")

        if documents:
            doc_text = "\n".join(
                f"- {d.get('original_name', 'Unnamed')}: {d.get('summary', 'No summary')[:100]}"
                for d in documents[:10]
            )
            sections.append(f"## Documents Uploaded Today\n{doc_text}")

        if not sections:
            return "No activity recorded today. Start by creating notes, setting reminders, or uploading documents."

        combined = "\n\n".join(sections)

        message = client.messages.create(
            model=current_app.config['CLAUDE_MODEL'],
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": (
                    "Based on the following daily activity data, create a concise daily briefing. "
                    "Organize it into clear sections, highlight priorities and action items, "
                    "and provide a brief overall summary at the top. Use markdown formatting.\n\n"
                    f"{combined}"
                )
            }]
        )
        return message.content[0].text
    except Exception as e:
        return f"Could not generate daily summary: {str(e)}"


def analyze_document(text: str, question: str) -> str:
    """Answer a question about a document's content."""
    try:
        client = get_client()
        truncated = text[:8000]
        message = client.messages.create(
            model=current_app.config['CLAUDE_MODEL'],
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    "Based on the following document content, answer the question.\n\n"
                    f"Document:\n{truncated}\n\n"
                    f"Question: {question}"
                )
            }]
        )
        return message.content[0].text
    except Exception as e:
        return f"Could not analyze document: {str(e)}"


def extract_handwritten_note(image_data: bytes, media_type: str) -> dict:
    """Use Claude's vision to extract text from a handwritten note image.

    Returns a dict with:
        - title: a generated title for the note
        - content: the full extracted text in clean markdown format
    """
    try:
        client = get_client()
        image_b64 = base64.standard_b64encode(image_data).decode('utf-8')

        message = client.messages.create(
            model=current_app.config['CLAUDE_MODEL'],
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "This is a photo of a handwritten note. Please:\n"
                            "1. Carefully read and transcribe ALL the handwritten text in the image.\n"
                            "2. Preserve the original structure (headings, bullet points, numbered lists, etc).\n"
                            "3. Clean up the formatting into readable Markdown.\n"
                            "4. If there are diagrams or drawings, describe them briefly in [brackets].\n"
                            "5. Generate a short, descriptive title for this note.\n\n"
                            "Return ONLY a JSON object with two fields:\n"
                            '- "title": a short descriptive title (max 10 words)\n'
                            '- "content": the full transcribed text in clean Markdown format\n\n'
                            "Return ONLY valid JSON, no other text."
                        ),
                    },
                ],
            }]
        )

        response_text = message.content[0].text.strip()
        # Extract JSON
        if response_text.startswith('{'):
            return json.loads(response_text)
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(response_text[start:end])
        # Fallback: use the raw response as content
        return {
            'title': 'Handwritten Note',
            'content': response_text
        }
    except json.JSONDecodeError:
        # If JSON parsing fails, use raw response
        return {
            'title': 'Handwritten Note',
            'content': message.content[0].text.strip() if message else 'Could not parse response'
        }
    except Exception as e:
        return {
            'title': 'Error',
            'content': f"Could not extract text from image: {str(e)}"
        }
