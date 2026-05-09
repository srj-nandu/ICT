# Careermitra

Careermitra is a Flask web application for resume analysis. Users can upload a
resume, choose one or more target job roles, and receive a skill-match report
with matched skills, missing skills, generated charts, and stored analysis
records.

## What The App Does

- Registers and authenticates users.
- Stores user profile details and uploaded resumes.
- Extracts readable text from PDF, DOCX, TXT, and RTF resumes.
- Compares extracted skills with predefined job-role skill sets.
- Generates match percentages, missing-skill lists, and chart images.
- Lets users review previous uploads and delete stored resume data.
- Gives admins a wider dashboard view of stored records.
- Saves contact form messages.

## Project Layout

| Path | Purpose |
| --- | --- |
| `app.py` | Main Flask app, resume parsing, analysis, page context builders, and app factory. |
| `frontend.py` | Route registration for pages, form submissions, downloads, and delete actions. |
| `backend.py` | Shared helpers for database connections and simple template rendering. |
| `data_store.py` | Database, user, profile, resume, analysis, contact, and cleanup operations. |
| `db_structure.py` | SQLite table definitions and migration helpers for required columns. |
| `skill_library.py` | Job-role definitions and the skills used for resume matching. |
| `templates/` | HTML templates rendered by the app. |
| `static/` | CSS, JavaScript, generated chart images, and report screenshots. |
| `storage/` | Runtime data such as the SQLite database, JSON files, uploads, and records. |
| `tools/` | Scripts used to generate project report assets and PDF reports. |

## Requirements

The project uses Python and the packages listed in `requirements.txt`:

```txt
Flask
gunicorn
PyMuPDF
numpy
pandas
matplotlib
```

## Run Locally

Create and activate a virtual environment, install dependencies, then start the
Flask app:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

By default the app runs at:

```txt
http://127.0.0.1:8000
```

You can change the host or port with environment variables:

```powershell
$env:HOST = "127.0.0.1"
$env:PORT = "8001"
.\.venv\Scripts\python.exe app.py
```

## Main User Flow

1. Open the home page.
2. Register or log in.
3. Upload a resume from the upload page.
4. Select one or more job roles.
5. Review the generated result page.
6. Use the dashboard or profile page to revisit or delete stored data.

## Data And Generated Files

The app creates runtime files under `storage/` and generated chart images under
`static/generated/`. These files are application data, not source code. Uploaded
resume files and extracted text are grouped by user and record IDs so they can be
reviewed or deleted later.

The SQLite database is stored at:

```txt
storage/resumevault.sqlite3
```

## Deployment Notes

For production-style hosting, the project exposes `app = create_app()` in
`app.py`, so a WSGI server can run:

```txt
gunicorn app:app
```

Set a secure `SECRET_KEY` environment variable outside development.

## Maintenance Notes

- Keep new job-role skills in `skill_library.py`.
- Keep database schema changes in `db_structure.py`.
- Keep storage and database operations in `data_store.py`.
- Keep route definitions in `frontend.py`.
- Keep user-facing templates in `templates/` and styles/scripts in `static/`.
