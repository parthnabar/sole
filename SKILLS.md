# SKILLS.md — Sole's AI capabilities

A catalog of what Sole can do today, what powers each capability, and where Sole is
headed. Sole is Parth's personal AI assistant — currently a **note-taker + reminder**
tool with AI features layered on, and intended to grow into a broader AI assistant.

> Keep this in sync with the code. See the self-updating protocol in
> [CLAUDE.md](CLAUDE.md). All Claude calls live in `app/ai.py`.

---

## Current capabilities

### 1. Notes (core)
Rich-text notes (Quill.js editor) with bold/italic/highlight/font size, stored as
sanitized HTML (`bleach`). Click a note to edit directly. Notes can be created manually
or from a photo of handwriting (see #2).
- **Code:** `app/notes/`, model `Note` in `app/models.py`

### 2. Handwritten-note OCR (AI, vision)
Upload a photo of a handwritten note; Claude's vision transcribes it into clean Markdown,
preserves structure, describes diagrams, and generates a title.
- **AI:** `ai.extract_handwritten_note(image_data, media_type)`
- **Code:** `app/notes/routes.py`; `Note.source = 'handwritten'`

### 3. AI reminder extraction (AI)
Analyzes a note and extracts actionable items / deadlines as structured reminders,
resolving relative dates ("tomorrow", "Friday") against the current date. Suggested
reminders are surfaced for the user to accept; accepted ones link back to the note.
- **AI:** `ai.extract_reminders_from_note(title, content)`
- **Code:** `app/notes/routes.py`, `app/templates/notes/_suggestions.html`

### 4. Reminders (core)
Manual + AI-generated reminders with due dates, completed/dismissed/overdue states.
Bidirectionally linked to notes. A 7-day "upcoming" view on the dashboard; a notification
bell shows the count of currently-due reminders.
- **Code:** `app/reminders/`, model `Reminder`; due-count context processor in `app/__init__.py`

### 5. Document upload, summary & Q&A (AI)
Upload PDF/DOCX/TXT (≤16MB). Sole extracts the text, generates a summary, and lets you
ask questions answered from the document's content.
- **AI:** `ai.summarize_document(filename, text)`, `ai.analyze_document(text, question)`
- **Code:** `app/documents/` (`extractors.py` for pdfplumber/python-docx), model `Document`

### 6. Gmail triage & summaries (AI, integration)
Connect Gmail (Google OAuth, readonly). Sole fetches recent emails, caches them, and uses
Claude to summarize each and triage them (priority high/medium/low, needs-response,
category, reason).
- **AI:** `ai.summarize_email(...)`, `ai.triage_email(...)`
- **Code:** `app/email/` (`gmail_service.py`), models `EmailCache`, `OAuthToken`

### 7. Daily briefing (AI, scheduled)
Once per day (08:00, via APScheduler) Sole combines the day's emails, notes, reminders,
and documents into a single markdown briefing with priorities and action items. Can also
be viewed on demand.
- **AI:** `ai.generate_daily_summary(emails, notes, reminders, documents)`
- **Code:** `app/summary/`, `app/tasks/scheduler.py` (`auto_generate_daily_summary`), model `DailySummary`

### 8. Dashboard
Personalized landing view tying together upcoming reminders, recent notes, and the latest
daily summary.
- **Code:** `app/main/`

---

## How to add a new AI capability

1. Add a function to `app/ai.py` that reads the model from `current_app.config['CLAUDE_MODEL']` and parses output defensively (fail soft).
2. Create or extend a blueprint under `app/<feature>/`; register it in `app/__init__.py`.
3. Add Jinja templates (HTMX partials as `_*.html` for in-place updates).
4. Add a model to `app/models.py` if you need persistence (no migrations — `db.create_all()` handles new tables).
5. **Document it here** as a new entry, and update the layout tree in CLAUDE.md.

---

## Future directions (wishlist)

This section is a living scratchpad for where Sole is headed — add ideas here as they come
up so they aren't lost. Parth wants to expand Sole's AI features beyond notes/reminders.

- _(add ideas here — e.g. conversational chat over all your data, calendar integration, smart search across notes/docs/emails, proactive suggestions, voice capture, prompt caching to cut API cost)_
