from __future__ import annotations

import html
import json
import os
import re
import uuid
import zlib
import zipfile
from collections import Counter
from datetime import datetime
from data_store import (
    authenticate_user,
    create_user,
    delete_record,
    delete_resume,
    delete_user_resume_files,
    ensure_storage,
    get_analysis_result,
    get_or_create_combined_job_role,
    get_user_profile,
    insert_analysis_result,
    insert_resume,
    list_job_roles,
    load_records,
    list_user_resumes,
    save_contact_message,
    persist_record,
    update_user_profile,
)
from flask import Flask, abort, redirect, request, send_file, session
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
import xml.etree.ElementTree as ET

from backend import render_frontend_template
from frontend import (
    CONTACT_PAGE,
    DASHBOARD_PAGE,
    INDEX_PAGE,
    LOGIN_PAGE,
    PROFILE_PAGE,
    REGISTER_PAGE,
    RESULT_PAGE,
    UPLOAD_PAGE,
    register_routes,
)
from skill_library import SKILL_LIBRARY
import fitz
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
STORAGE_ROOT = BASE_DIR / "storage"
RECORDS_ROOT = STORAGE_ROOT / "records"
TEMPLATES_ROOT = BASE_DIR / "templates"
STATIC_ROOT = BASE_DIR / "static"
UPLOADS_ROOT = STORAGE_ROOT / "uploads"
GRAPHS_ROOT = STATIC_ROOT / "generated"
SESSION_COOKIE = "resumevault_session"
MAX_UPLOAD_SIZE = 8 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:(?:\+\d{1,3})?[\s.-]?)?(?:\(?\d{3,4}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}")

PDF_TEXT_RE = re.compile(rb"\((?:\\.|[^\\()])*\)\s*Tj")
PDF_ARRAY_TEXT_RE = re.compile(rb"\[(.*?)\]\s*TJ", re.S)
PDF_LITERAL_RE = re.compile(rb"\((?:\\.|[^\\()])*\)")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def compact_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def decode_pdf_literal(data: bytes) -> str:
    inner = data[1:-1]
    result: list[str] = []
    index = 0
    while index < len(inner):
        current = inner[index]
        if current != 92:
            result.append(chr(current))
            index += 1
            continue

        index += 1
        if index >= len(inner):
            break
        escaped = inner[index]
        mapping = {
            ord("n"): "\n",
            ord("r"): "\r",
            ord("t"): "\t",
            ord("b"): "\b",
            ord("f"): "\f",
            ord("("): "(",
            ord(")"): ")",
            ord("\\"): "\\",
        }
        if escaped in mapping:
            result.append(mapping[escaped])
            index += 1
            continue

        if 48 <= escaped <= 55:
            octal_digits = bytes([escaped])
            for _ in range(2):
                if index + 1 < len(inner) and 48 <= inner[index + 1] <= 55:
                    index += 1
                    octal_digits += bytes([inner[index]])
                else:
                    break
            result.append(chr(int(octal_digits, 8)))
            index += 1
            continue

        result.append(chr(escaped))
        index += 1

    return "".join(result)


def extract_text_from_pdf_bytes(blob: bytes) -> str:
    snippets: list[str] = []
    for raw_stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", blob, re.S):
        possible_streams = [raw_stream]
        try:
            possible_streams.append(zlib.decompress(raw_stream))
        except zlib.error:
            pass

        for decoded in possible_streams:
            for match in PDF_TEXT_RE.finditer(decoded):
                literal = decode_pdf_literal(match.group()[:-3].strip())
                if literal.strip():
                    snippets.append(literal)

            for array_match in PDF_ARRAY_TEXT_RE.finditer(decoded):
                for literal_match in PDF_LITERAL_RE.finditer(array_match.group(1)):
                    literal = decode_pdf_literal(literal_match.group())
                    if literal.strip():
                        snippets.append(literal)

    if not snippets:
        fallback = re.findall(rb"[A-Za-z][A-Za-z0-9@&(),./:+\- ]{20,}", blob)
        snippets = [item.decode("latin-1", errors="ignore") for item in fallback[:20]]

    return compact_text("\n".join(snippets))[:25000]


def extract_text_from_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        try:
            document_xml = archive.read("word/document.xml")
        except KeyError:
            return ""

    root = ET.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        pieces = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
        joined = "".join(pieces).strip()
        if joined:
            paragraphs.append(joined)
    return compact_text("\n".join(paragraphs))


def extract_text_from_rtf(raw_text: str) -> str:
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw_text)
    text = re.sub(r"\\par[d]? ?", "\n", text)
    text = re.sub(r"\\[a-zA-Z]+\d* ?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    return compact_text(text)


def extract_resume_text(file_path: Path) -> tuple[str, str]:
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return (
            compact_text(file_path.read_text(encoding="utf-8", errors="replace")),
            "Plain text extracted directly from the uploaded file.",
        )
    if suffix == ".docx":
        text = extract_text_from_docx(file_path)
        note = (
            "DOCX text extracted from the document structure."
            if text
            else "DOCX uploaded successfully, but no readable text was found."
        )
        return text, note
    if suffix == ".pdf":
        text = extract_text_from_pdf_bytes(file_path.read_bytes())
        note = (
            "PDF text recovered with a lightweight parser."
            if text
            else (
                "PDF uploaded successfully. Text extraction was limited, "
                "so the analysis is metadata-focused."
            )
        )
        return text, note
    if suffix == ".rtf":
        text = extract_text_from_rtf(file_path.read_text(encoding="utf-8", errors="replace"))
        note = (
            "RTF text cleaned into plain text for analysis."
            if text
            else "RTF uploaded successfully, but the text could not be normalized."
        )
        return text, note
    return "", "File stored successfully. This format is not configured for text extraction."


def extract_candidate_name(text: str, fallback_filename: str) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or "@" in candidate or len(candidate) > 60:
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,58}", candidate):
            return candidate.title()
    stem = Path(fallback_filename).stem.replace("-", " ").replace("_", " ").strip()
    return stem.title() if stem else "Unknown Candidate"


def extract_years_experience(text: str) -> str | None:
    explicit = re.search(r"(\d{1,2})\+?\s+years? of experience", text, re.I)
    if explicit:
        return explicit.group(1)
    summary = re.search(r"(\d{1,2})\+?\s+years?", text, re.I)
    if summary:
        return summary.group(1)
    return None


def analyze_resume(text: str, filename: str, extraction_note: str) -> dict[str, Any]:
    normalized_text = compact_text(text)
    word_count = len(re.findall(r"\b\w+\b", normalized_text))
    email_match = EMAIL_RE.search(normalized_text)
    phone_match = PHONE_RE.search(normalized_text)
    years_experience = extract_years_experience(normalized_text)

    category_hits: dict[str, list[dict[str, Any]]] = {}
    skill_counter: Counter[str] = Counter()
    for category, skills in SKILL_LIBRARY.items():
        matches: list[dict[str, Any]] = []
        for skill_name, patterns in skills.items():
            count = sum(len(re.findall(pattern, normalized_text, re.I)) for pattern in patterns)
            if count:
                matches.append({"name": skill_name, "count": count})
                skill_counter[skill_name] += count
        if matches:
            matches.sort(key=lambda item: (-item["count"], item["name"]))
            category_hits[category] = matches

    top_skills = [skill for skill, _count in skill_counter.most_common(8)]
    confidence_score = min(100, 25 + min(word_count, 600) // 8 + len(top_skills) * 5)
    analysis_mode = "Detailed" if word_count >= 60 else "Metadata-focused"

    summary_bits: list[str] = []
    if top_skills:
        summary_bits.append(f"Strongest detected skills: {', '.join(top_skills[:4])}.")
    if years_experience:
        summary_bits.append(f"Resume text suggests around {years_experience}+ years of experience.")
    if not summary_bits:
        summary_bits.append(
            "The resume was stored successfully, but only a limited amount "
            "of text was available for skill analysis."
        )
    summary_bits.append(extraction_note)

    return {
        "candidate_name": extract_candidate_name(normalized_text, filename),
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "years_experience": years_experience or "",
        "word_count": word_count,
        "analysis_mode": analysis_mode,
        "confidence_score": confidence_score,
        "summary": " ".join(summary_bits),
        "top_skills": top_skills,
        "categories": category_hits,
    }


def aggregate_skill_counts(records: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for record in records:
        for skill in record.get("analysis", {}).get("top_skills", []):
            counter[skill] += 1
    return counter


def persist_resume(upload: dict[str, Any]) -> str:
    ensure_storage()
    original_filename = upload.get("filename", "")
    if not original_filename:
        raise ValueError("Please choose a resume file before uploading.")

    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}.")

    file_content = upload.get("content", b"")
    if not file_content:
        raise ValueError("The uploaded file is empty.")

    record_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    record_dir = RECORDS_ROOT / record_id
    record_dir.mkdir(parents=True, exist_ok=False)

    source_path = record_dir / f"original{extension or '.bin'}"
    source_path.write_bytes(file_content)

    extracted_text, extraction_note = extract_resume_text(source_path)
    analysis = analyze_resume(extracted_text, original_filename, extraction_note)
    text_path = record_dir / "extracted_text.txt"
    text_path.write_text(extracted_text or extraction_note, encoding="utf-8")

    created_at = datetime.now().isoformat(timespec="seconds")
    metadata = {
        "record_id": record_id,
        "created_at": created_at,
        "original_filename": original_filename,
        "stored_filename": source_path.name,
        "content_type": upload.get("content_type", "application/octet-stream"),
        "extension": extension,
        "size_bytes": len(file_content),
        "candidate_name": analysis["candidate_name"],
        "extraction_note": extraction_note,
        "storage_layout": {
            "folder": str(record_dir.relative_to(BASE_DIR)),
            "source_file": source_path.name,
            "text_file": text_path.name,
            "analysis_file": "analysis.json",
            "metadata_file": "metadata.json",
        },
    }

    write_json(record_dir / "metadata.json", metadata)
    write_json(record_dir / "analysis.json", analysis)
    persist_record(metadata, analysis)
    return record_id


def all_skill_patterns() -> dict[str, tuple[str, ...]]:
    skills: dict[str, tuple[str, ...]] = {}
    for category_skills in SKILL_LIBRARY.values():
        skills.update(category_skills)
    return skills


def extract_pdf_text_with_pymupdf(file_path: Path) -> str:
    try:
        with fitz.open(file_path) as document:
            pages = [page.get_text("text") for page in document]
    except Exception as exc:
        raise ValueError("We could not parse that PDF. Please upload a readable text-based PDF.") from exc

    text = compact_text("\n".join(pages))
    if not text:
        raise ValueError("No readable text was found in the PDF. Please upload a text-based resume PDF.")
    return text[:50000]


def extract_skills_from_text(text: str) -> list[str]:
    found: list[str] = []
    for skill_name, patterns in all_skill_patterns().items():
        if any(re.search(pattern, text, re.I) for pattern in patterns):
            found.append(skill_name)
    return sorted(found, key=str.lower)


def normalize_skill_name(skill: str) -> str:
    return re.sub(r"\s+", " ", skill.strip().lower())


def merge_skills(*skill_groups: list[str]) -> list[str]:
    merged: dict[str, str] = {}
    for skills in skill_groups:
        for skill in skills:
            normalized = normalize_skill_name(skill)
            if normalized:
                merged[normalized] = normalized
    return sorted(merged.values())


def calculate_skill_gap(extracted_skills: list[str], required_skills: list[str]) -> dict[str, Any]:
    required_lookup = {normalize_skill_name(skill): normalize_skill_name(skill) for skill in required_skills}
    extracted_lookup = {skill.lower(): skill for skill in extracted_skills}
    rows = []
    for key, skill in required_lookup.items():
        rows.append({"skill": skill, "matched": key in extracted_lookup})

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("The selected job role does not have required skills configured.")

    match_values = frame["matched"].astype(int).to_numpy(dtype=float)
    match_percentage = float(np.round(np.mean(match_values) * 100, 2))
    matched = frame.loc[frame["matched"], "skill"].tolist()
    missing = frame.loc[~frame["matched"], "skill"].tolist()
    return {
        "match_percentage": match_percentage,
        "matched_skills": matched,
        "missing_skills": missing,
    }


def save_analysis_graphs(match_percentage: float, matched_count: int, missing_skills: list[str]) -> tuple[Path, Path]:
    GRAPHS_ROOT.mkdir(parents=True, exist_ok=True)
    graph_token = uuid.uuid4().hex
    match_path = GRAPHS_ROOT / f"{graph_token}_match.png"
    missing_path = GRAPHS_ROOT / f"{graph_token}_missing.png"

    plt.figure(figsize=(5.5, 3.6))
    plt.bar(["Match", "Gap"], [match_percentage, 100 - match_percentage], color=["#0f766e", "#c2410c"])
    plt.ylim(0, 100)
    plt.ylabel("Percentage")
    plt.title("Skill Match Graph")
    plt.tight_layout()
    plt.savefig(match_path, dpi=140)
    plt.close()

    labels = missing_skills or ["No missing skills"]
    values = [1 for _item in labels]
    colors = ["#c2410c" for _item in labels] if missing_skills else ["#0f766e"]
    height = max(3.6, min(7.5, 0.46 * len(labels) + 1.5))
    plt.figure(figsize=(7, height))
    plt.barh(labels, values, color=colors)
    plt.xlabel("Missing skill indicator")
    plt.title(f"Missing Skills Visualization ({matched_count} matched)")
    plt.xticks([])
    plt.tight_layout()
    plt.savefig(missing_path, dpi=140)
    plt.close()

    return match_path, missing_path


def analyze_uploaded_resume(
    user: dict[str, Any],
    upload: dict[str, Any],
    job_role_ids: list[str] | str,
    replace_old: bool = False,
) -> str:
    ensure_storage()
    original_filename = upload.get("filename", "").strip()
    if not original_filename:
        raise ValueError("Please choose a PDF resume before uploading.")
    extension = Path(original_filename).suffix.lower()
    if extension != ".pdf":
        raise ValueError("Only PDF resumes are allowed for analysis.")

    file_content = upload.get("content", b"")
    if not file_content:
        raise ValueError("The uploaded PDF is empty.")

    selected_role_ids = [job_role_ids] if isinstance(job_role_ids, str) else job_role_ids
    job_role = get_or_create_combined_job_role(selected_role_ids)
    required_skills = job_role["required_skills"]
    if replace_old:
        delete_user_resume_files(user["user_id"])

    user_upload_root = UPLOADS_ROOT / user["user_id"]
    user_upload_root.mkdir(parents=True, exist_ok=True)
    stored_filename = (
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}-"
        f"{uuid.uuid4().hex[:8]}-"
        f"{secure_filename(original_filename)}"
    )
    file_path = user_upload_root / stored_filename
    text_path = user_upload_root / f"{Path(stored_filename).stem}.txt"

    try:
        file_path.write_bytes(file_content)
        extracted_text = extract_pdf_text_with_pymupdf(file_path)
        text_path.write_text(extracted_text, encoding="utf-8")
        extracted_skills = extract_skills_from_text(extracted_text)
        if not extracted_skills:
            raise ValueError(
                "No known skills were detected in this resume. "
                "Please upload a resume with clearer skill details."
            )

        gap = calculate_skill_gap(extracted_skills, required_skills)
        graph_match_path, graph_missing_path = save_analysis_graphs(
            gap["match_percentage"],
            len(gap["matched_skills"]),
            gap["missing_skills"],
        )
        resume_id = insert_resume(user["user_id"], original_filename, stored_filename, file_path, text_path)
        return insert_analysis_result(
            resume_id,
            user["user_id"],
            job_role["job_role_id"],
            gap["match_percentage"],
            extracted_skills,
            gap["matched_skills"],
            gap["missing_skills"],
            graph_match_path,
            graph_missing_path,
        )
    except ValueError:
        if file_path.exists():
            file_path.unlink()
        if text_path.exists():
            text_path.unlink()
        raise
    except Exception as exc:
        if file_path.exists():
            file_path.unlink()
        if text_path.exists():
            text_path.unlink()
        raise ValueError("Something went wrong while analyzing the resume. Please try another PDF.") from exc


def html_message_block(message: str, kind: str) -> str:
    if not message:
        return ""
    safe_kind = "success" if kind == "success" else "warning"
    return f'<div class="flash {safe_kind}">{html.escape(message)}</div>'


def render_template(template_name: str, context: dict[str, Any]) -> str:
    return render_frontend_template(template_name, context)


def value_attr(text: str) -> str:
    return html.escape(text or "", quote=True)


def textarea_value(text: str) -> str:
    return html.escape(text or "")


def nav_links(active: str, logged_in: bool) -> str:
    items = [(INDEX_PAGE, "Home", "home")]
    if logged_in:
        items.extend(
            [
                (DASHBOARD_PAGE, "Dashboard", "dashboard"),
                (UPLOAD_PAGE, "Upload Resume", "upload"),
                (PROFILE_PAGE, "Profile", "profile"),
                (CONTACT_PAGE, "Contact Us", "contact"),
            ]
        )
    else:
        items.append((CONTACT_PAGE, "Contact Us", "contact"))
    if not logged_in:
        items.extend(
            [
                (LOGIN_PAGE, "Login", "login"),
                (REGISTER_PAGE, "Register", "register"),
            ]
        )

    links: list[str] = []
    for href, label, key in items:
        class_name = "nav-link active" if key == active else "nav-link"
        links.append(f'<a class="{class_name}" href="{href}">{label}</a>')
    return "".join(links)


def auth_block(user: dict[str, Any] | None) -> str:
    if user:
        display_name = html.escape(user.get("name", "Member"))
        role = html.escape(user.get("role", "user").title())
        return (
            f'<div class="auth-stack">'
            f'<span class="user-chip">{display_name} | {role}</span>'
            f'<form action="/logout" method="post"><button class="ghost-button" type="submit">Logout</button></form>'
            f"</div>"
        )
    return (
        '<div class="auth-stack">'
        f'<a class="ghost-link" href="{LOGIN_PAGE}">Sign in</a>'
        f'<a class="solid-link" href="{REGISTER_PAGE}">Get Started</a>'
        "</div>"
    )


def render_skill_totals(records: list[dict[str, Any]]) -> str:
    totals = aggregate_skill_counts(records)
    if not totals:
        return '<div class="empty-chip">Upload resumes to build a shared skill snapshot.</div>'

    rows: list[str] = []
    highest = max(totals.values())
    for skill, count in totals.most_common(8):
        width = max(16, int((count / highest) * 100))
        rows.append(
            f"""
            <div class="skill-row">
                <span>{html.escape(skill)}</span>
                <div class="skill-meter"><b style="width:{width}%"></b></div>
                <strong>{count}</strong>
            </div>
            """
        )
    return "".join(rows)


def render_record_cards(records: list[dict[str, Any]]) -> str:
    if not records:
        return """
        <section class="empty-state">
            <h3>No resumes stored yet</h3>
            <p>
                Upload a TXT, DOCX, PDF, or RTF resume to generate structured
                metadata, extracted text, and a skills overview.
            </p>
        </section>
        """

    cards: list[str] = []
    for record in records:
        analysis = record.get("analysis", {})
        top_skills = analysis.get("top_skills", [])
        tags = "".join(f'<span class="tag">{html.escape(skill)}</span>' for skill in top_skills[:6])
        if not tags:
            tags = '<span class="tag muted">Awaiting stronger text signals</span>'

        years_experience = analysis.get("years_experience")
        experience = f"{years_experience}+ years" if years_experience else "Not detected"
        record_id = html.escape(record.get("record_id", ""), quote=True)
        original_filename = html.escape(record.get("original_filename", ""))
        size_display = html.escape(record.get("size_display", ""))
        analysis_mode = html.escape(analysis.get("analysis_mode", "Metadata-focused"))
        searchable_text = " ".join(
            [
                record.get("candidate_name", ""),
                record.get("original_filename", ""),
                " ".join(top_skills),
            ]
        ).lower()

        cards.append(
            f"""
            <article class="record-card" data-search="{html.escape(searchable_text)}">
                <div class="card-top">
                    <label class="record-select">
                        <input type="checkbox" name="record_ids" value="{record_id}" form="bulkSelectionForm">
                        <span>
                            <p class="eyebrow">{html.escape(record.get("created_display", ""))}</p>
                            <h3>{html.escape(record.get("candidate_name", "Unknown Candidate"))}</h3>
                        </span>
                    </label>
                    <div class="card-status">
                        <span class="selected-pill">Selected</span>
                        <span class="score">{analysis.get("confidence_score", 0)}% match confidence</span>
                    </div>
                </div>
                <p class="file-line">{original_filename} &middot; {size_display}</p>
                <p class="summary">{html.escape(analysis.get("summary", ""))}</p>
                <div class="tag-wrap">{tags}</div>
                <div class="info-grid">
                    <div><span>Mode</span><strong>{analysis_mode}</strong></div>
                    <div><span>Words</span><strong>{analysis.get("word_count", 0)}</strong></div>
                    <div><span>Email</span><strong>{html.escape(analysis.get("email") or "Not found")}</strong></div>
                    <div><span>Experience</span><strong>{html.escape(experience)}</strong></div>
                </div>
                <div class="action-row">
                    <a href="{record.get("source_url", "#")}">Source</a>
                    <a href="{record.get("text_url", "#")}">Text</a>
                    <a href="{record.get("analysis_url", "#")}">Analysis</a>
                    <a href="{record.get("metadata_url", "#")}">Metadata</a>
                    <form action="/delete" method="post">
                        <input type="hidden" name="record_id" value="{html.escape(record.get("record_id", ""))}">
                        <button type="submit" class="danger">Delete</button>
                    </form>
                </div>
            </article>
            """
        )
    return "".join(cards)


def render_job_role_choices(selected_ids: list[str] | None = None) -> str:
    selected = set(selected_ids or [])
    choices: list[str] = []
    for role in list_job_roles():
        checked = " checked" if role["job_role_id"] in selected else ""
        skills = html.escape(role.get("skills") or "")
        role_id = html.escape(role["job_role_id"], quote=True)
        choices.append(
            f"""
            <label class="role-check">
                <input type="checkbox" name="job_role_ids" value="{role_id}"{checked}>
                <span>
                    <strong>{html.escape(role["title"])}</strong>
                    <small>{skills}</small>
                </span>
            </label>
            """
        )
    return "".join(choices)


def render_resume_rows(resumes: list[dict[str, Any]]) -> str:
    if not resumes:
        return '<tr><td colspan="5" class="text-center text-muted py-4">No resumes uploaded yet.</td></tr>'
    rows: list[str] = []
    for resume in resumes:
        result_id = resume.get("result_id", "")
        result_url = f"{RESULT_PAGE}/{html.escape(result_id)}"
        result_link = (
            f'<a class="btn btn-sm btn-outline-success" href="{result_url}">Open result</a>'
            if result_id
            else '<span class="text-muted">Pending</span>'
        )
        delete_form = f"""
            <form action="/resume-delete" method="post" class="d-inline">
                <input type="hidden" name="resume_id" value="{html.escape(resume.get("resume_id", ""), quote=True)}">
                <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
            </form>
        """
        rows.append(
            f"""
            <tr>
                <td>{html.escape(resume.get("original_filename", ""))}</td>
                <td>{html.escape(resume.get("job_role_title") or "Not selected")}</td>
                <td>{resume.get("match_percentage", 0) or 0}%</td>
                <td>{html.escape(resume.get("uploaded_at", ""))}</td>
                <td class="text-nowrap">{result_link} {delete_form}</td>
            </tr>
            """
        )
    return "".join(rows)


def render_missing_skill_badges(skills: list[str]) -> str:
    if not skills:
        return '<span class="badge text-bg-success">No missing skills</span>'
    return "".join(f'<span class="badge text-bg-warning me-2 mb-2">{html.escape(skill)}</span>' for skill in skills)


def dashboard_context(user: dict[str, Any], message: str = "", kind: str = "success") -> dict[str, Any]:
    records = load_records()
    include_all = user.get("role") == "admin"
    resumes = list_user_resumes(user.get("user_id", ""), include_all=include_all)
    analyzed_count = sum(1 for item in records if item.get("analysis", {}).get("word_count", 0) > 0)
    structured_files = len(records) * 4
    top_skill = aggregate_skill_counts(records).most_common(1)
    top_skill_label = html.escape(top_skill[0][0]) if top_skill else "Waiting for uploads"
    latest_match = max([float(item.get("match_percentage") or 0) for item in resumes], default=0)

    return {
        "page_title": "Dashboard | Careermitra",
        "nav_links": nav_links("dashboard", True),
        "auth_block": auth_block(user),
        "message_block": html_message_block(message, kind),
        "records_count": len(resumes),
        "analyzed_count": sum(1 for item in resumes if item.get("result_id")),
        "structured_files": len(resumes) * 3,
        "top_skill_label": top_skill_label,
        "latest_match": f"{latest_match:g}%",
        "resume_rows": render_resume_rows(resumes),
        "admin_note": (
            "Admin view: showing all uploaded resumes."
            if include_all
            else "User view: showing your uploaded resumes."
        ),
        "skill_totals": render_skill_totals(records),
        "record_cards": render_record_cards(records),
        "user_name": html.escape(user.get("name", "Member")),
    }


def login_context(
    message: str = "",
    kind: str = "success",
    email: str = "",
) -> dict[str, Any]:
    return {
        "page_title": "Login | Careermitra",
        "nav_links": nav_links("login", False),
        "auth_block": auth_block(None),
        "message_block": html_message_block(message, kind),
        "email_value": value_attr(email),
    }


def register_context(
    message: str = "",
    kind: str = "success",
    name: str = "",
    email: str = "",
) -> dict[str, Any]:
    return {
        "page_title": "Register | Careermitra",
        "nav_links": nav_links("register", False),
        "auth_block": auth_block(None),
        "message_block": html_message_block(message, kind),
        "name_value": value_attr(name),
        "email_value": value_attr(email),
    }


def home_context(
    user: dict[str, Any] | None,
    message: str = "",
    kind: str = "success",
) -> dict[str, Any]:
    return {
        "page_title": "Home | Careermitra",
        "nav_links": nav_links("home", user is not None),
        "auth_block": auth_block(user),
        "message_block": html_message_block(message, kind),
        "primary_href": DASHBOARD_PAGE if user else REGISTER_PAGE,
        "primary_label": "Open Dashboard" if user else "Create Account",
    }


def upload_context(
    user: dict[str, Any],
    message: str = "",
    kind: str = "success",
) -> dict[str, Any]:
    return {
        "page_title": "Upload Resume | Careermitra",
        "nav_links": nav_links("upload", True),
        "auth_block": auth_block(user),
        "message_block": html_message_block(message, kind),
        "job_role_choices": render_job_role_choices(),
    }


def profile_context(
    user: dict[str, Any],
    message: str = "",
    kind: str = "success",
) -> dict[str, Any]:
    profile = get_user_profile(user["user_id"])
    resumes = list_user_resumes(user["user_id"])
    return {
        "page_title": "Profile | Careermitra",
        "nav_links": nav_links("profile", True),
        "auth_block": auth_block(user),
        "message_block": html_message_block(message, kind),
        "full_name_value": value_attr(profile.get("full_name", "")),
        "email_value": value_attr(profile.get("email", "")),
        "phone_value": value_attr(profile.get("phone", "")),
        "headline_value": value_attr(profile.get("headline", "")),
        "location_value": value_attr(profile.get("location", "")),
        "role_label": html.escape(profile.get("role", "user").title()),
        "resume_rows": render_resume_rows(resumes),
    }


def result_context(
    user: dict[str, Any],
    result_id: str,
    message: str = "",
    kind: str = "success",
) -> dict[str, Any]:
    result = get_analysis_result(result_id, user["user_id"], user.get("role") == "admin")
    return {
        "page_title": "Analysis Result | Careermitra",
        "nav_links": nav_links("result", True),
        "auth_block": auth_block(user),
        "message_block": html_message_block(message, kind),
        "candidate_name": html.escape(result.get("owner_name", "")),
        "resume_filename": html.escape(result.get("original_filename", "")),
        "job_role_title": html.escape(result.get("job_role_title", "")),
        "match_percentage": f"{float(result.get('match_percentage', 0)):g}%",
        "extracted_skills": (
            ", ".join(html.escape(skill) for skill in result.get("extracted_skills", []))
            or "None detected"
        ),
        "matched_skills": ", ".join(html.escape(skill) for skill in result.get("matched_skills", [])) or "None",
        "missing_skill_badges": render_missing_skill_badges(result.get("missing_skills", [])),
        "graph_match_url": html.escape(result.get("graph_match_url", "")),
        "graph_missing_url": html.escape(result.get("graph_missing_url", "")),
        "created_at": html.escape(result.get("created_at", "")),
    }


def contact_context(
    user: dict[str, Any] | None,
    message: str = "",
    kind: str = "success",
    form_data: dict[str, str] | None = None,
) -> dict[str, Any]:
    form_data = form_data or {}
    default_name = user.get("name", "") if user else ""
    default_email = user.get("email", "") if user else ""
    return {
        "page_title": "Contact Us | Careermitra",
        "nav_links": nav_links("contact", user is not None),
        "auth_block": auth_block(user),
        "message_block": html_message_block(message, kind),
        "name_value": value_attr(form_data.get("name", default_name)),
        "email_value": value_attr(form_data.get("email", default_email)),
        "subject_value": value_attr(form_data.get("subject", "")),
        "message_value": textarea_value(form_data.get("message", "")),
    }


def build_dashboard_page(user: dict[str, Any], message: str = "", kind: str = "success") -> str:
    return render_template("dashboard.html", dashboard_context(user, message, kind))


def build_home_page(user: dict[str, Any] | None, message: str = "", kind: str = "success") -> str:
    return render_template("index.html", home_context(user, message, kind))


def build_upload_page(user: dict[str, Any], message: str = "", kind: str = "success") -> str:
    return render_template("upload.html", upload_context(user, message, kind))


def build_profile_page(user: dict[str, Any], message: str = "", kind: str = "success") -> str:
    return render_template("profile.html", profile_context(user, message, kind))


def build_result_page(user: dict[str, Any], result_id: str, message: str = "", kind: str = "success") -> str:
    return render_template("result.html", result_context(user, result_id, message, kind))


def build_login_page(message: str = "", kind: str = "success", email: str = "") -> str:
    return render_template("login.html", login_context(message, kind, email))


def build_register_page(message: str = "", kind: str = "success", name: str = "", email: str = "") -> str:
    return render_template("register.html", register_context(message, kind, name, email))


def build_contact_page(
    user: dict[str, Any] | None,
    message: str = "",
    kind: str = "success",
    form_data: dict[str, str] | None = None,
) -> str:
    return render_template("contact.html", contact_context(user, message, kind, form_data))


def store_current_user(user: dict[str, Any]) -> None:
    session["user"] = {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "role": user.get("role", "user"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def get_current_user() -> dict[str, Any] | None:
    user = session.get("user")
    return user if isinstance(user, dict) else None


def clear_session() -> None:
    session.pop("user", None)


def redirect_with_params(path: str, params: dict[str, str] | None = None) -> Any:
    location = path
    if params:
        location = f"{path}?{urlencode(params)}"
    return redirect(location, code=HTTPStatus.SEE_OTHER)


def handle_form_error(path: str, message: str) -> Any:
    if path == REGISTER_PAGE:
        return redirect_with_params(REGISTER_PAGE, {"message": message, "kind": "warning"})
    if path == LOGIN_PAGE:
        return redirect_with_params(LOGIN_PAGE, {"message": message, "kind": "warning"})
    if path == CONTACT_PAGE:
        return redirect_with_params(CONTACT_PAGE, {"message": message, "kind": "warning"})
    if path == UPLOAD_PAGE:
        return redirect_with_params(UPLOAD_PAGE, {"message": message, "kind": "warning"})
    if path == PROFILE_PAGE:
        return redirect_with_params(PROFILE_PAGE, {"message": message, "kind": "warning"})
    return redirect_with_params(DASHBOARD_PAGE, {"message": message, "kind": "warning"})


def get_record_directory(record_id: str) -> Path:
    target_dir = RECORDS_ROOT / record_id
    resolved_root = RECORDS_ROOT.resolve()
    resolved_target = target_dir.resolve(strict=False)
    if resolved_target == resolved_root or resolved_root not in resolved_target.parents:
        abort(HTTPStatus.BAD_REQUEST, "Invalid record requested.")
    if not target_dir.exists():
        abort(HTTPStatus.NOT_FOUND, "Requested record could not be found.")
    return target_dir


def resolve_download_file(record_id: str, kind: str) -> Path:
    target_dir = get_record_directory(record_id)
    mapping = {
        "text": target_dir / "extracted_text.txt",
        "analysis": target_dir / "analysis.json",
        "metadata": target_dir / "metadata.json",
    }
    if kind == "source":
        candidates = sorted(
            [
                path
                for path in target_dir.iterdir()
                if path.is_file() and path.name.startswith("original")
            ],
            key=lambda item: item.name,
        )
        file_path = candidates[0] if candidates else None
    else:
        file_path = mapping.get(kind)

    if not file_path or not file_path.exists():
        abort(HTTPStatus.NOT_FOUND, "Requested file could not be found.")
    return file_path


def file_response(file_path: Path) -> Any:
    content_type = {
        ".json": "application/json; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".rtf": "application/rtf",
    }.get(file_path.suffix.lower(), "application/octet-stream")
    return send_file(file_path, mimetype=content_type, as_attachment=True, download_name=file_path.name)


def flask_upload_to_dict(field_name: str) -> dict[str, Any]:
    uploaded_file = request.files.get(field_name)
    if uploaded_file is None:
        return {}
    return {
        "filename": uploaded_file.filename or "",
        "content_type": uploaded_file.mimetype or "application/octet-stream",
        "content": uploaded_file.read(),
    }


def create_app() -> Flask:
    ensure_storage()
    app = Flask(__name__, static_folder=str(STATIC_ROOT), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
    app.config["SESSION_COOKIE_NAME"] = SESSION_COOKIE
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "resumevault-dev-secret")

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_error: RequestEntityTooLarge) -> Any:
        return handle_form_error(request.path, "Uploaded payload exceeds the 8 MB size limit.")

    register_routes(
        app,
        {
            "analyze_uploaded_resume": analyze_uploaded_resume,
            "authenticate_user": authenticate_user,
            "build_contact_page": build_contact_page,
            "build_dashboard_page": build_dashboard_page,
            "build_home_page": build_home_page,
            "build_login_page": build_login_page,
            "build_profile_page": build_profile_page,
            "build_register_page": build_register_page,
            "build_result_page": build_result_page,
            "build_upload_page": build_upload_page,
            "clear_session": clear_session,
            "create_user": create_user,
            "delete_record": delete_record,
            "delete_resume": delete_resume,
            "delete_user_resume_files": delete_user_resume_files,
            "file_response": file_response,
            "flask_upload_to_dict": flask_upload_to_dict,
            "get_current_user": get_current_user,
            "handle_form_error": handle_form_error,
            "redirect_with_params": redirect_with_params,
            "resolve_download_file": resolve_download_file,
            "save_contact_message": save_contact_message,
            "store_current_user": store_current_user,
            "update_user_profile": update_user_profile,
        },
    )

    return app


app = create_app()


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"Careermitra running at http://{host}:{port}")
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
