# CLAUDE.md — Sole

> **Sole** is Parth's personal AI assistant app. The git repo / directory is named
> `Assistant`, but the product is **Sole** — when the user says "Sole" they mean this project.

## What Sole is

A self-hosted, single-user AI assistant built with Flask. Today it's primarily a
**note-taker and reminder system**, with several AI features layered on top
(document Q&A, Gmail triage, daily briefings, handwritten-note OCR).

**Direction:** This is an actively growing project. Parth intends to build out **more AI
features over time** — Sole should be treated as an evolving AI assistant platform, not a
finished note app. When suggesting designs, favor extensibility and reuse of the existing
AI plumbing (`app/ai.py`, the blueprint structure) so new AI capabilities slot in cleanly.

## Tech stack

- **Backend:** Flask 3.1 (app factory in `app/__init__.py`), blueprint-per-feature
- **DB:** SQLAlchemy. SQLite locally (`instance/assistant.db`), PostgreSQL in production (Render). Tables auto-created via `db.create_all()` — there are **no migrations** (Alembic/Flask-Migrate not in use).
- **AI:** Anthropic Python SDK. All Claude calls live in `app/ai.py`. Model is configurable via `CLAUDE_MODEL` env var.
- **Auth:** Single hardcoded user (id=1) via Flask-Login; credentials from `APP_USERNAME`/`APP_PASSWORD`. Google OAuth (Gmail readonly) for email features.
- **Scheduling:** Flask-APScheduler — reminder check every 60s, daily summary at 08:00.
- **Frontend:** Server-rendered Jinja2 + HTMX (partials in `_*.html`), Quill.js rich text editor, vanilla JS in `app/static/js/app.js`.
- **Deploy:** Render (`render.yaml`), gunicorn, free tier (512MB, 1 worker) — keep memory/batch sizes small.

## Project layout

```
app/
  __init__.py        # app factory, blueprint registration, Jinja filters, scheduler setup
  config.py          # Config / Development / Production; env-driven settings
  models.py          # Note, Document, Reminder, EmailCache, DailySummary, OAuthToken
  ai.py              # ALL Claude/Anthropic calls (the AI layer)
  extensions.py      # db, scheduler, csrf, login_manager singletons
  auth/              # login/logout, Google OAuth flow
  main/              # dashboard
  notes/             # notes CRUD, handwritten OCR, AI reminder extraction
  reminders/         # reminders CRUD, due/overdue logic
  documents/         # upload, text extraction (pdf/docx/txt), summary, Q&A
  email/             # Gmail fetch + AI summarize/triage
  summary/           # daily briefing generation + views
  tasks/scheduler.py # background jobs
run.py               # entrypoint (loads .env, creates app)
render.yaml          # Render deploy config
```

## Conventions

- **New feature = new blueprint** under `app/<feature>/`, registered in `app/__init__.py`.
- **All Claude calls go in `app/ai.py`** as standalone functions that read the model from `current_app.config['CLAUDE_MODEL']`. Don't scatter `anthropic` calls across blueprints.
- AI functions that expect JSON should parse defensively (find first `{`/`[`, last `}`/`]`) and fail soft by returning `{}`/`[]`/an error string — see existing patterns in `app/ai.py`.
- HTMX partials are named `_something.html` and returned for in-place swaps.
- Store note/user HTML through `bleach` sanitization (already wired for note content).
- Keep production-tier memory in mind: truncate text sent to Claude (note the `[:3000]`/`[:8000]` slices), small batch sizes.

## Running locally

```bash
source venv/bin/activate
pip install -r requirements.txt
python run.py            # http://localhost:5000, debug on
```
Requires a `.env` with at least `ANTHROPIC_API_KEY`, `APP_USERNAME`, `APP_PASSWORD`
(and `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` for email features).

## Companion docs

- **[SKILLS.md](SKILLS.md)** — catalog of Sole's AI capabilities (what each one does, which `ai.py` function and route powers it, and ideas for future features). Read it to understand the AI surface area before adding to it.

---

## Keeping these docs current (self-updating protocol)

**These docs are meant to stay alive. Whenever you make a change that affects the
information above, update CLAUDE.md and/or SKILLS.md in the same change — don't wait to
be asked.** Specifically:

- **Added/removed a blueprint or feature** → update the Project layout tree, and add/remove the matching entry in SKILLS.md.
- **Added/changed a Claude call in `app/ai.py`** → update the relevant SKILLS.md capability entry (function name, what it does, model usage).
- **Changed the stack, deploy setup, env vars, or run steps** → update Tech stack / Running locally.
- **Changed a convention** (naming, where AI calls live, sanitization, etc.) → update Conventions.
- **Learned a durable fact about Parth's goals or Sole's direction** → reflect it in "What Sole is" here, and save it to memory if it's the kind of cross-session context worth recalling later.

When you finish a task, do a quick check: "did anything I just changed make a line in
CLAUDE.md or SKILLS.md inaccurate?" If yes, fix it before reporting done. Keep edits
surgical and factual — these are reference docs, not changelogs, so don't append history
or restate the task that prompted the change.
