from __future__ import annotations

from http import HTTPStatus
from typing import Any

from flask import abort, redirect, request


INDEX_PAGE = "/templates/index.html"
DASHBOARD_PAGE = "/templates/dashboard.html"
UPLOAD_PAGE = "/templates/upload.html"
PROFILE_PAGE = "/templates/profile.html"
RESULT_PAGE = "/templates/result.html"
CONTACT_PAGE = "/templates/contact.html"
LOGIN_PAGE = "/templates/login.html"
REGISTER_PAGE = "/templates/register.html"


def register_routes(app: Any, handlers: dict[str, Any]) -> None:
    @app.route("/", methods=["GET"])
    @app.route(INDEX_PAGE, methods=["GET"])
    def index() -> Any:
        return handlers["build_home_page"](
            handlers["get_current_user"](),
            request.args.get("message", ""),
            request.args.get("kind", "success"),
        )

    @app.route("/favicon.ico", methods=["GET"])
    def favicon() -> Any:
        return "", HTTPStatus.NO_CONTENT

    @app.route(DASHBOARD_PAGE, methods=["GET"])
    def dashboard() -> Any:
        user = handlers["get_current_user"]()
        if not user:
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to open the dashboard.", "kind": "warning"},
            )
        return handlers["build_dashboard_page"](
            user,
            request.args.get("message", ""),
            request.args.get("kind", "success"),
        )

    @app.route(UPLOAD_PAGE, methods=["GET"])
    def upload_page() -> Any:
        user = handlers["get_current_user"]()
        if not user:
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to upload resumes.", "kind": "warning"},
            )
        return handlers["build_upload_page"](
            user,
            request.args.get("message", ""),
            request.args.get("kind", "success"),
        )

    @app.route(PROFILE_PAGE, methods=["GET"])
    def profile_page() -> Any:
        user = handlers["get_current_user"]()
        if not user:
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to open your profile.", "kind": "warning"},
            )
        return handlers["build_profile_page"](
            user,
            request.args.get("message", ""),
            request.args.get("kind", "success"),
        )

    @app.route(f"{RESULT_PAGE}/<result_id>", methods=["GET"])
    def result_page(result_id: str) -> Any:
        user = handlers["get_current_user"]()
        if not user:
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {
                    "message": "Please log in to view analysis results.",
                    "kind": "warning",
                },
            )
        try:
            return handlers["build_result_page"](
                user,
                result_id,
                request.args.get("message", ""),
                request.args.get("kind", "success"),
            )
        except ValueError as exc:
            return handlers["handle_form_error"](DASHBOARD_PAGE, str(exc))

    @app.route(CONTACT_PAGE, methods=["GET"])
    def contact() -> Any:
        user = handlers["get_current_user"]()
        form_data = {
            "name": request.args.get("name", ""),
            "email": request.args.get("email", ""),
            "subject": request.args.get("subject", ""),
            "message": request.args.get("message_text", ""),
        }
        return handlers["build_contact_page"](
            user,
            request.args.get("message", ""),
            request.args.get("kind", "success"),
            form_data,
        )

    @app.route(LOGIN_PAGE, methods=["GET"])
    def login_page() -> Any:
        if handlers["get_current_user"]():
            return redirect(DASHBOARD_PAGE)
        return handlers["build_login_page"](
            request.args.get("message", ""),
            request.args.get("kind", "success"),
            request.args.get("email", ""),
        )

    @app.route(REGISTER_PAGE, methods=["GET"])
    def register_page() -> Any:
        if handlers["get_current_user"]():
            return redirect(DASHBOARD_PAGE)
        return handlers["build_register_page"](
            request.args.get("message", ""),
            request.args.get("kind", "success"),
            request.args.get("name", ""),
            request.args.get("email", ""),
        )

    @app.route("/download", methods=["GET"])
    def download() -> Any:
        if not handlers["get_current_user"]():
            abort(HTTPStatus.FORBIDDEN, "Please log in to download files.")
        record_id = request.args.get("id", "")
        kind = request.args.get("kind", "source")
        return handlers["file_response"](handlers["resolve_download_file"](record_id, kind))

    @app.route(REGISTER_PAGE, methods=["POST"])
    def register_post() -> Any:
        try:
            user = handlers["create_user"](
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("password", ""),
            )
            handlers["store_current_user"](user)
            return handlers["redirect_with_params"](
                DASHBOARD_PAGE,
                {
                    "message": f"Welcome, {user['name']}. Your account is ready.",
                    "kind": "success",
                },
            )
        except ValueError as exc:
            return handlers["handle_form_error"](REGISTER_PAGE, str(exc))

    @app.route(LOGIN_PAGE, methods=["POST"])
    def login_post() -> Any:
        try:
            user = handlers["authenticate_user"](
                request.form.get("email", ""),
                request.form.get("password", ""),
            )
            handlers["store_current_user"](user)
            return handlers["redirect_with_params"](
                DASHBOARD_PAGE,
                {"message": f"Welcome back, {user['name']}.", "kind": "success"},
            )
        except ValueError as exc:
            return handlers["handle_form_error"](LOGIN_PAGE, str(exc))

    @app.route("/logout", methods=["POST"])
    def logout_post() -> Any:
        handlers["clear_session"]()
        return handlers["redirect_with_params"](
            LOGIN_PAGE,
            {"message": "You have been logged out.", "kind": "success"},
        )

    @app.route(CONTACT_PAGE, methods=["POST"])
    def contact_post() -> Any:
        try:
            handlers["save_contact_message"](
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("subject", ""),
                request.form.get("message", ""),
                handlers["get_current_user"](),
            )
            return handlers["redirect_with_params"](
                CONTACT_PAGE,
                {
                    "message": "Your message has been saved. We will reach out soon.",
                    "kind": "success",
                },
            )
        except ValueError as exc:
            return handlers["handle_form_error"](CONTACT_PAGE, str(exc))

    @app.route(UPLOAD_PAGE, methods=["POST"])
    def upload_post() -> Any:
        user = handlers["get_current_user"]()
        if not user:
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to upload resumes.", "kind": "warning"},
            )
        try:
            result_id = handlers["analyze_uploaded_resume"](
                user,
                handlers["flask_upload_to_dict"]("resume"),
                request.form.getlist("job_role_ids") or [request.form.get("job_role_id", "")],
                request.form.get("replace_old") == "yes",
            )
            return handlers["redirect_with_params"](
                f"{RESULT_PAGE}/{result_id}",
                {"message": "Resume analyzed successfully. Your skill gap report is ready.", "kind": "success"},
            )
        except ValueError as exc:
            return handlers["handle_form_error"](UPLOAD_PAGE, str(exc))

    @app.route(PROFILE_PAGE, methods=["POST"])
    def profile_post() -> Any:
        user = handlers["get_current_user"]()
        if not user:
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to update your profile.", "kind": "warning"},
            )
        try:
            handlers["update_user_profile"](
                user["user_id"],
                request.form.get("full_name", ""),
                request.form.get("phone", ""),
                request.form.get("headline", ""),
                request.form.get("location", ""),
            )
            user["name"] = request.form.get("full_name", "").strip()
            handlers["store_current_user"](user)
            return handlers["redirect_with_params"](
                PROFILE_PAGE,
                {"message": "Profile updated successfully.", "kind": "success"},
            )
        except ValueError as exc:
            return handlers["handle_form_error"](PROFILE_PAGE, str(exc))

    @app.route("/resume-delete", methods=["POST"])
    def resume_delete_post() -> Any:
        user = handlers["get_current_user"]()
        if not user:
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to delete resumes.", "kind": "warning"},
            )
        try:
            handlers["delete_resume"](
                request.form.get("resume_id", ""),
                user["user_id"],
                user.get("role") == "admin",
            )
            return handlers["redirect_with_params"](
                PROFILE_PAGE,
                {
                    "message": "Resume and generated analysis files deleted.",
                    "kind": "success",
                },
            )
        except ValueError as exc:
            return handlers["redirect_with_params"](
                PROFILE_PAGE,
                {"message": str(exc), "kind": "warning"},
            )

    @app.route("/old-data-delete", methods=["POST"])
    def old_data_delete_post() -> Any:
        user = handlers["get_current_user"]()
        if not user:
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to delete old data.", "kind": "warning"},
            )
        deleted_count = handlers["delete_user_resume_files"](user["user_id"])
        return_to = request.form.get("return_to", PROFILE_PAGE)
        if return_to not in {UPLOAD_PAGE, PROFILE_PAGE, DASHBOARD_PAGE}:
            return_to = PROFILE_PAGE
        label = "item" if deleted_count == 1 else "items"
        return handlers["redirect_with_params"](
            return_to,
            {
                "message": f"Deleted {deleted_count} old data {label} and generated files.",
                "kind": "success",
            },
        )

    @app.route("/delete", methods=["POST"])
    def delete_post() -> Any:
        if not handlers["get_current_user"]():
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to manage records.", "kind": "warning"},
            )
        try:
            record_id = request.form.get("record_id", "").strip()
            if not record_id:
                raise ValueError("No record id was provided for deletion.")
            handlers["delete_record"](record_id)
            return handlers["redirect_with_params"](
                DASHBOARD_PAGE,
                {
                    "message": "Record deleted and its folder was removed from storage.",
                    "kind": "success",
                },
            )
        except ValueError as exc:
            return handlers["handle_form_error"]("/delete", str(exc))

    @app.route("/bulk-delete", methods=["POST"])
    def bulk_delete_post() -> Any:
        if not handlers["get_current_user"]():
            return handlers["redirect_with_params"](
                LOGIN_PAGE,
                {"message": "Please log in to manage records.", "kind": "warning"},
            )
        record_ids = [
            record_id.strip()
            for record_id in request.form.getlist("record_ids")
            if record_id.strip()
        ]
        if not record_ids:
            return handlers["redirect_with_params"](
                DASHBOARD_PAGE,
                {"message": "Select at least one record first.", "kind": "warning"},
            )

        deleted_count = 0
        try:
            for record_id in record_ids:
                handlers["delete_record"](record_id)
                deleted_count += 1
        except ValueError as exc:
            return handlers["handle_form_error"]("/bulk-delete", str(exc))

        label = "record" if deleted_count == 1 else "records"
        return handlers["redirect_with_params"](
            DASHBOARD_PAGE,
            {
                "message": f"Deleted {deleted_count} selected {label}.",
                "kind": "success",
            },
        )
