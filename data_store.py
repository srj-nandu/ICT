from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
import re

from backend import get_db_connection
from db_structure import init_database
from skill_library import ROLE_SKILLS


BASE_DIR = Path(__file__).resolve().parent
STORAGE_ROOT = BASE_DIR / "storage"
RECORDS_ROOT = STORAGE_ROOT / "records"
TEMPLATES_ROOT = BASE_DIR / "templates"
STATIC_ROOT = BASE_DIR / "static"
USERS_FILE = STORAGE_ROOT / "users.json"
CONTACTS_FILE = STORAGE_ROOT / "contacts.json"
DISPLAY_DATE_FORMAT = "%d %b %Y, %I:%M %p"
UPLOADS_ROOT = STORAGE_ROOT / "uploads"
GRAPHS_ROOT = STATIC_ROOT / "generated"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
STORAGE_READY = False

DEFAULT_JOB_ROLES = {role: details["skills"] for role, details in ROLE_SKILLS.items()}


def seed_job_roles() -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as connection:
        for title, skills in DEFAULT_JOB_ROLES.items():
            job_role_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"resumevault:{title}").hex
            connection.execute(
                """
                INSERT OR IGNORE INTO job_roles (job_role_id, title, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_role_id, title, ROLE_SKILLS[title]["description"], now),
            )
            for skill_name in skills:
                skill_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"resumevault:skill:{skill_name.lower()}").hex
                connection.execute(
                    "INSERT OR IGNORE INTO skills (skill_id, name) VALUES (?, ?)",
                    (skill_id, skill_name),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO job_role_skills (job_role_id, skill_id)
                    VALUES (?, ?)
                    """,
                    (job_role_id, skill_id),
                )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def persist_record_to_database(
    connection: sqlite3.Connection, metadata: dict[str, Any], analysis: dict[str, Any]
) -> None:
    storage_layout = metadata.get("storage_layout", {})
    connection.execute(
        """
        INSERT OR REPLACE INTO records (
            record_id,
            created_at,
            user_id,
            original_filename,
            stored_filename,
            content_type,
            extension,
            size_bytes,
            candidate_name,
            extraction_note,
            storage_folder,
            source_file,
            text_file,
            analysis_file,
            metadata_file,
            analysis_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metadata.get("record_id", ""),
            metadata.get("created_at", ""),
            metadata.get("user_id", ""),
            metadata.get("original_filename", ""),
            metadata.get("stored_filename", ""),
            metadata.get("content_type", "application/octet-stream"),
            metadata.get("extension", ""),
            int(metadata.get("size_bytes", 0) or 0),
            metadata.get("candidate_name", ""),
            metadata.get("extraction_note", ""),
            storage_layout.get("folder", ""),
            storage_layout.get("source_file", ""),
            storage_layout.get("text_file", ""),
            storage_layout.get("analysis_file", "analysis.json"),
            storage_layout.get("metadata_file", "metadata.json"),
            json.dumps(analysis),
        ),
    )


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"


def format_timestamp(iso_string: str) -> str:
    try:
        return datetime.fromisoformat(iso_string).strftime(DISPLAY_DATE_FORMAT)
    except ValueError:
        return iso_string


def hydrate_record(metadata: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    record_id = metadata.get("record_id", "")
    metadata = dict(metadata)
    metadata["analysis"] = analysis
    metadata["created_display"] = format_timestamp(metadata.get("created_at", ""))
    metadata["size_display"] = format_bytes(int(metadata.get("size_bytes", 0) or 0))
    metadata["source_url"] = f"/download?id={quote(record_id)}&kind=source"
    metadata["text_url"] = f"/download?id={quote(record_id)}&kind=text"
    metadata["analysis_url"] = f"/download?id={quote(record_id)}&kind=analysis"
    metadata["metadata_url"] = f"/download?id={quote(record_id)}&kind=metadata"
    return metadata


def build_record_from_row(row: sqlite3.Row) -> dict[str, Any]:
    analysis_json = row["analysis_json"] or "{}"
    try:
        analysis = json.loads(analysis_json)
    except json.JSONDecodeError:
        analysis = {}

    metadata = {
        "record_id": row["record_id"],
        "created_at": row["created_at"],
        "user_id": row["user_id"],
        "original_filename": row["original_filename"],
        "stored_filename": row["stored_filename"],
        "content_type": row["content_type"],
        "extension": row["extension"],
        "size_bytes": row["size_bytes"],
        "candidate_name": row["candidate_name"],
        "extraction_note": row["extraction_note"],
        "storage_layout": {
            "folder": row["storage_folder"],
            "source_file": row["source_file"],
            "text_file": row["text_file"],
            "analysis_file": row["analysis_file"],
            "metadata_file": row["metadata_file"],
        },
    }
    return hydrate_record(metadata, analysis)


def read_json_file(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_record(record_dir: Path) -> dict[str, Any] | None:
    metadata_path = record_dir / "metadata.json"
    analysis_path = record_dir / "analysis.json"
    if not metadata_path.exists() or not analysis_path.exists():
        return None

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    if "storage_layout" not in metadata:
        metadata["storage_layout"] = {
            "folder": str(record_dir.relative_to(BASE_DIR)),
            "source_file": metadata.get("stored_filename", ""),
            "text_file": "extracted_text.txt",
            "analysis_file": "analysis.json",
            "metadata_file": "metadata.json",
        }
    return hydrate_record(metadata, analysis)


def migrate_legacy_data() -> None:
    with get_db_connection() as connection:
        for user in read_json_file(USERS_FILE, []):
            connection.execute(
                """
                INSERT OR IGNORE INTO users (
                    user_id,
                    name,
                    email,
                    password_salt,
                    password_hash,
                    role,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.get("user_id", uuid.uuid4().hex),
                    user.get("name", ""),
                    user.get("email", "").strip().lower(),
                    user.get("password_salt", ""),
                    user.get("password_hash", ""),
                    user.get("role", "user"),
                    user.get("created_at", datetime.now().isoformat(timespec="seconds")),
                ),
            )

        for message in read_json_file(CONTACTS_FILE, []):
            connection.execute(
                """
                INSERT OR IGNORE INTO contacts (
                    message_id,
                    name,
                    email,
                    subject,
                    message,
                    created_at,
                    user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.get("message_id", uuid.uuid4().hex),
                    message.get("name", ""),
                    message.get("email", "").strip().lower(),
                    message.get("subject", ""),
                    message.get("message", ""),
                    message.get("created_at", datetime.now().isoformat(timespec="seconds")),
                    message.get("user_id", ""),
                ),
            )

        if RECORDS_ROOT.exists():
            for record_dir in RECORDS_ROOT.iterdir():
                if not record_dir.is_dir():
                    continue
                record = load_record(record_dir)
                if not record:
                    continue
                persist_record_to_database(connection, record, record.get("analysis", {}))


def ensure_storage() -> None:
    global STORAGE_READY
    if STORAGE_READY:
        return
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    RECORDS_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    TEMPLATES_ROOT.mkdir(parents=True, exist_ok=True)
    STATIC_ROOT.mkdir(parents=True, exist_ok=True)
    GRAPHS_ROOT.mkdir(parents=True, exist_ok=True)
    with get_db_connection() as connection:
        init_database(connection)
    seed_job_roles()
    migrate_legacy_data()
    STORAGE_READY = True


def load_records() -> list[dict[str, Any]]:
    ensure_storage()
    with get_db_connection() as connection:
        rows = connection.execute("SELECT * FROM records ORDER BY created_at DESC").fetchall()
    return [build_record_from_row(row) for row in rows]


def persist_record(metadata: dict[str, Any], analysis: dict[str, Any]) -> None:
    ensure_storage()
    with get_db_connection() as connection:
        persist_record_to_database(connection, metadata, analysis)


def delete_record(record_id: str) -> None:
    ensure_storage()
    target = RECORDS_ROOT / record_id
    resolved_root = RECORDS_ROOT.resolve()
    resolved_target = target.resolve(strict=False)
    if resolved_target == resolved_root or resolved_root not in resolved_target.parents:
        raise ValueError("Invalid record selected for deletion.")

    deleted = False
    with get_db_connection() as connection:
        cursor = connection.execute("DELETE FROM records WHERE record_id = ?", (record_id,))
        deleted = cursor.rowcount > 0

    if target.exists():
        shutil.rmtree(target)
        deleted = True
    if not deleted:
        raise ValueError("The selected record could not be found.")


def load_users() -> list[dict[str, Any]]:
    ensure_storage()
    with get_db_connection() as connection:
        rows = connection.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
    return [dict(row) for row in rows]


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()


def find_user_by_email(email: str) -> dict[str, Any] | None:
    ensure_storage()
    email_normalized = email.strip().lower()
    with get_db_connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ?", (email_normalized,)).fetchone()
    return row_to_dict(row)


def create_user(name: str, email: str, password: str, role: str = "user") -> dict[str, Any]:
    ensure_storage()
    name = name.strip()
    email = email.strip().lower()
    if len(name) < 2:
        raise ValueError("Please enter your full name.")
    if not EMAIL_RE.fullmatch(email):
        raise ValueError("Please enter a valid email address.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if find_user_by_email(email):
        raise ValueError("An account with that email already exists.")

    first_user = len(load_users()) == 0
    salt = secrets.token_hex(16)
    user = {
        "user_id": uuid.uuid4().hex,
        "name": name,
        "email": email,
        "password_salt": salt,
        "password_hash": hash_password(password, salt),
        "role": "admin" if first_user else "user",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        with get_db_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    user_id,
                    name,
                    email,
                    password_salt,
                    password_hash,
                    role,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["user_id"],
                    user["name"],
                    user["email"],
                    user["password_salt"],
                    user["password_hash"],
                    user["role"],
                    user["created_at"],
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO user_profiles (user_id, full_name, updated_at)
                VALUES (?, ?, ?)
                """,
                (user["user_id"], user["name"], user["created_at"]),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("An account with that email already exists.") from exc
    return user


def authenticate_user(email: str, password: str) -> dict[str, Any]:
    ensure_storage()
    user = find_user_by_email(email)
    if not user:
        raise ValueError("No account was found for that email.")
    if hash_password(password, user["password_salt"]) != user["password_hash"]:
        raise ValueError("Incorrect password. Please try again.")
    return user


def save_contact_message(
    name: str, email: str, subject: str, message: str, user: dict[str, Any] | None
) -> None:
    ensure_storage()
    name = name.strip()
    email = email.strip().lower()
    subject = subject.strip()
    message = message.strip()

    if len(name) < 2:
        raise ValueError("Please provide your name.")
    if not EMAIL_RE.fullmatch(email):
        raise ValueError("Please provide a valid email address.")
    if len(subject) < 3:
        raise ValueError("Please provide a short subject.")
    if len(message) < 10:
        raise ValueError("Please enter a longer message so we can help properly.")

    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO contacts (
                message_id,
                name,
                email,
                subject,
                message,
                created_at,
                user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                name,
                email,
                subject,
                message,
                datetime.now().isoformat(timespec="seconds"),
                user.get("user_id", "") if user else "",
            ),
        )


def get_user_profile(user_id: str) -> dict[str, Any]:
    ensure_storage()
    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT users.user_id, users.name, users.email, users.role, users.created_at,
                   COALESCE(user_profiles.full_name, users.name) AS full_name,
                   COALESCE(user_profiles.phone, '') AS phone,
                   COALESCE(user_profiles.headline, '') AS headline,
                   COALESCE(user_profiles.location, '') AS location,
                   COALESCE(user_profiles.updated_at, users.created_at) AS updated_at
            FROM users
            LEFT JOIN user_profiles ON user_profiles.user_id = users.user_id
            WHERE users.user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        raise ValueError("User profile could not be found.")
    return dict(row)


def update_user_profile(user_id: str, full_name: str, phone: str, headline: str, location: str) -> None:
    ensure_storage()
    full_name = full_name.strip()
    if len(full_name) < 2:
        raise ValueError("Please enter your full name.")
    now = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_profiles (user_id, full_name, phone, headline, location, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                phone = excluded.phone,
                headline = excluded.headline,
                location = excluded.location,
                updated_at = excluded.updated_at
            """,
            (user_id, full_name, phone.strip(), headline.strip(), location.strip(), now),
        )
        connection.execute("UPDATE users SET name = ? WHERE user_id = ?", (full_name, user_id))


def list_job_roles() -> list[dict[str, Any]]:
    ensure_storage()
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT job_roles.job_role_id, job_roles.title, job_roles.description,
                   GROUP_CONCAT(skills.name, ', ') AS skills
            FROM job_roles
            LEFT JOIN job_role_skills ON job_role_skills.job_role_id = job_roles.job_role_id
            LEFT JOIN skills ON skills.skill_id = job_role_skills.skill_id
            GROUP BY job_roles.job_role_id
            ORDER BY job_roles.title
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_job_role(job_role_id: str) -> dict[str, Any]:
    ensure_storage()
    with get_db_connection() as connection:
        role = connection.execute(
            "SELECT * FROM job_roles WHERE job_role_id = ?",
            (job_role_id,),
        ).fetchone()
        if not role:
            raise ValueError("Please select a valid job role.")
        skills = connection.execute(
            """
            SELECT skills.name
            FROM skills
            JOIN job_role_skills ON job_role_skills.skill_id = skills.skill_id
            WHERE job_role_skills.job_role_id = ?
            ORDER BY skills.name
            """,
            (job_role_id,),
        ).fetchall()
    payload = dict(role)
    payload["required_skills"] = [row["name"] for row in skills]
    return payload


def get_or_create_combined_job_role(job_role_ids: list[str]) -> dict[str, Any]:
    unique_ids = list(dict.fromkeys(job_role_id.strip() for job_role_id in job_role_ids if job_role_id.strip()))
    if not unique_ids:
        raise ValueError("Please select at least one job role.")
    if len(unique_ids) == 1:
        return get_job_role(unique_ids[0])

    roles = [get_job_role(job_role_id) for job_role_id in unique_ids]
    title = " + ".join(role["title"] for role in roles)
    description = "Combined skill target for: " + ", ".join(role["title"] for role in roles)
    combined_key = "|".join(sorted(unique_ids))
    combined_role_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"resumevault:combined:{combined_key}").hex

    required_skills: dict[str, str] = {}
    for role in roles:
        for skill in role["required_skills"]:
            normalized = re.sub(r"\s+", " ", skill.strip().lower())
            if normalized:
                required_skills[normalized] = normalized

    now = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO job_roles (job_role_id, title, description, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (combined_role_id, title, description, now),
        )
        for skill_name in sorted(required_skills.values()):
            skill_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"resumevault:skill:{skill_name.lower()}").hex
            connection.execute(
                "INSERT OR IGNORE INTO skills (skill_id, name) VALUES (?, ?)",
                (skill_id, skill_name),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO job_role_skills (job_role_id, skill_id)
                VALUES (?, ?)
                """,
                (combined_role_id, skill_id),
            )

    return {
        "job_role_id": combined_role_id,
        "title": title,
        "description": description,
        "required_skills": sorted(required_skills.values()),
    }


def insert_resume(
    user_id: str,
    original_filename: str,
    stored_filename: str,
    file_path: Path,
    extracted_text_path: Path,
) -> str:
    ensure_storage()
    resume_id = uuid.uuid4().hex
    uploaded_at = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO resumes (
                resume_id, user_id, original_filename, stored_filename,
                file_path, extracted_text_path, uploaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resume_id,
                user_id,
                original_filename,
                stored_filename,
                str(file_path.relative_to(BASE_DIR)),
                str(extracted_text_path.relative_to(BASE_DIR)),
                uploaded_at,
            ),
        )
    return resume_id


def insert_analysis_result(
    resume_id: str,
    user_id: str,
    job_role_id: str,
    match_percentage: float,
    extracted_skills: list[str],
    matched_skills: list[str],
    missing_skills: list[str],
    graph_match_path: Path,
    graph_missing_path: Path,
) -> str:
    ensure_storage()
    result_id = uuid.uuid4().hex
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO analysis_results (
                result_id, resume_id, user_id, job_role_id, match_percentage,
                extracted_skills_json, matched_skills_json, missing_skills_json,
                graph_match_path, graph_missing_path, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id,
                resume_id,
                user_id,
                job_role_id,
                match_percentage,
                json.dumps(extracted_skills),
                json.dumps(matched_skills),
                json.dumps(missing_skills),
                str(graph_match_path.relative_to(BASE_DIR)),
                str(graph_missing_path.relative_to(BASE_DIR)),
                created_at,
            ),
        )
    return result_id


def list_user_resumes(user_id: str, include_all: bool = False) -> list[dict[str, Any]]:
    ensure_storage()
    where = "" if include_all else "WHERE resumes.user_id = ?"
    params: tuple[Any, ...] = () if include_all else (user_id,)
    with get_db_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT resumes.*, users.name AS owner_name, users.email AS owner_email,
                   analysis_results.result_id, analysis_results.match_percentage,
                   analysis_results.created_at AS result_created_at,
                   analysis_results.graph_match_path, analysis_results.graph_missing_path,
                   job_roles.title AS job_role_title
            FROM resumes
            JOIN users ON users.user_id = resumes.user_id
            LEFT JOIN analysis_results ON analysis_results.resume_id = resumes.resume_id
            LEFT JOIN job_roles ON job_roles.job_role_id = analysis_results.job_role_id
            {where}
            ORDER BY resumes.uploaded_at DESC
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_analysis_result(result_id: str, user_id: str, is_admin: bool = False) -> dict[str, Any]:
    ensure_storage()
    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT analysis_results.*, resumes.original_filename, resumes.file_path,
                   resumes.extracted_text_path, users.name AS owner_name,
                   job_roles.title AS job_role_title, job_roles.description AS job_role_description
            FROM analysis_results
            JOIN resumes ON resumes.resume_id = analysis_results.resume_id
            JOIN users ON users.user_id = analysis_results.user_id
            JOIN job_roles ON job_roles.job_role_id = analysis_results.job_role_id
            WHERE analysis_results.result_id = ?
            """,
            (result_id,),
        ).fetchone()
    if not row:
        raise ValueError("Analysis result could not be found.")
    result = dict(row)
    if not is_admin and result["user_id"] != user_id:
        raise ValueError("You do not have access to that result.")
    for key in ("extracted_skills_json", "matched_skills_json", "missing_skills_json"):
        try:
            result[key.replace("_json", "")] = json.loads(result[key])
        except json.JSONDecodeError:
            result[key.replace("_json", "")] = []
    result["graph_match_url"] = "/" + result["graph_match_path"].replace("\\", "/")
    result["graph_missing_url"] = "/" + result["graph_missing_path"].replace("\\", "/")
    return result


def delete_user_resume_files(user_id: str) -> int:
    ensure_storage()
    resumes = list_user_resumes(user_id)
    deleted_resume_count = len(resumes)
    with get_db_connection() as connection:
        result_rows = connection.execute(
            """
            SELECT graph_match_path, graph_missing_path
            FROM analysis_results
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()
        orphan_result_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM analysis_results
            LEFT JOIN resumes ON resumes.resume_id = analysis_results.resume_id
            WHERE analysis_results.user_id = ? AND resumes.resume_id IS NULL
            """,
            (user_id,),
        ).fetchone()["total"]

        for resume in resumes:
            for field_name in ("file_path", "extracted_text_path"):
                relative = resume.get(field_name)
                if not relative:
                    continue
                path = (BASE_DIR / relative).resolve(strict=False)
                if any(path == root or root in path.parents for root in [UPLOADS_ROOT.resolve()]) and path.exists():
                    path.unlink()

        for result in result_rows:
            for field_name in ("graph_match_path", "graph_missing_path"):
                relative = result[field_name]
                if not relative:
                    continue
                path = (BASE_DIR / relative).resolve(strict=False)
                graph_root = GRAPHS_ROOT.resolve()
                if (path == graph_root or graph_root in path.parents) and path.exists():
                    path.unlink()

        connection.execute("DELETE FROM analysis_results WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM resumes WHERE user_id = ?", (user_id,))
    return deleted_resume_count + int(orphan_result_count or 0)


def delete_resume(resume_id: str, user_id: str, is_admin: bool = False) -> None:
    ensure_storage()
    resume_id = resume_id.strip()
    if not resume_id:
        raise ValueError("No resume was selected for deletion.")

    with get_db_connection() as connection:
        resume = connection.execute(
            "SELECT * FROM resumes WHERE resume_id = ?",
            (resume_id,),
        ).fetchone()
        if not resume:
            raise ValueError("The selected resume could not be found.")
        resume_data = dict(resume)
        if not is_admin and resume_data["user_id"] != user_id:
            raise ValueError("You do not have permission to delete that resume.")

        graph_rows = connection.execute(
            """
            SELECT graph_match_path, graph_missing_path
            FROM analysis_results
            WHERE resume_id = ?
            """,
            (resume_id,),
        ).fetchall()

        files_to_delete = [
            resume_data.get("file_path", ""),
            resume_data.get("extracted_text_path", ""),
        ]
        for row in graph_rows:
            files_to_delete.extend([row["graph_match_path"], row["graph_missing_path"]])

        allowed_roots = [UPLOADS_ROOT.resolve(), GRAPHS_ROOT.resolve()]
        for relative in files_to_delete:
            if not relative:
                continue
            path = (BASE_DIR / relative).resolve(strict=False)
            if any(path == root or root in path.parents for root in allowed_roots) and path.exists():
                path.unlink()

        connection.execute("DELETE FROM analysis_results WHERE resume_id = ?", (resume_id,))
        connection.execute("DELETE FROM resumes WHERE resume_id = ?", (resume_id,))
