from __future__ import annotations

import sqlite3


DATABASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    headline TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contacts (
    message_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    user_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    candidate_name TEXT NOT NULL,
    extraction_note TEXT NOT NULL,
    storage_folder TEXT NOT NULL,
    source_file TEXT NOT NULL,
    text_file TEXT NOT NULL,
    analysis_file TEXT NOT NULL,
    metadata_file TEXT NOT NULL,
    analysis_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resumes (
    resume_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    extracted_text_path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_roles (
    job_role_id TEXT PRIMARY KEY,
    title TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS job_role_skills (
    job_role_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    PRIMARY KEY (job_role_id, skill_id),
    FOREIGN KEY (job_role_id) REFERENCES job_roles(job_role_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analysis_results (
    result_id TEXT PRIMARY KEY,
    resume_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    job_role_id TEXT NOT NULL,
    match_percentage REAL NOT NULL,
    extracted_skills_json TEXT NOT NULL,
    matched_skills_json TEXT NOT NULL,
    missing_skills_json TEXT NOT NULL,
    graph_match_path TEXT NOT NULL,
    graph_missing_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (job_role_id) REFERENCES job_roles(job_role_id) ON DELETE CASCADE
);
"""


REQUIRED_COLUMNS = (
    ("users", "role", "TEXT NOT NULL DEFAULT 'user'"),
    ("records", "user_id", "TEXT NOT NULL DEFAULT ''"),
)


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = [
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    ]
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def init_database(connection: sqlite3.Connection) -> None:
    connection.executescript(DATABASE_SCHEMA)
    for table_name, column_name, definition in REQUIRED_COLUMNS:
        ensure_column(connection, table_name, column_name, definition)
