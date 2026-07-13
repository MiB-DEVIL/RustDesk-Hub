from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from app.database.database import SessionLocal
from app.models.event_log import EventLog


PUBLIC_WRITE_PREFIXES = (
    "/login",
    "/api/agent/",
)

READ_ONLY_BLOCKED_GET_PREFIXES = (
    "/clients/delete/",
    "/groups/delete/",
)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AccessControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = unquote(request.url.path)
        method = request.method.upper()

        # Agent/API writes authenticate with their API key and do not use
        # a browser session.
        if any(path.startswith(prefix) for prefix in PUBLIC_WRITE_PREFIXES):
            return await call_next(request)

        username = request.session.get("user")
        is_admin = bool(request.session.get("is_admin", False))

        blocked = False

        if username and not is_admin:
            if method not in SAFE_METHODS:
                blocked = True

            if method == "GET" and any(
                path.startswith(prefix)
                for prefix in READ_ONLY_BLOCKED_GET_PREFIXES
            ):
                blocked = True

        if blocked:
            db = SessionLocal()
            try:
                db.add(
                    EventLog(
                        level="WARNING",
                        event_type="audit",
                        hostname="OpenDesk Hub",
                        rustdesk_id="",
                        message=(
                            f"{username} — tentative refusée : "
                            f"{method} {path}"
                        ),
                    )
                )
                db.commit()
            finally:
                db.close()

            return RedirectResponse(
                "/dashboard?error=read_only",
                status_code=303,
            )

        response = await call_next(request)

        detailed_audit_prefixes = (
            "/users",
            "/profile/password",
        )

        should_audit_success = (
            username
            and is_admin
            and method not in SAFE_METHODS
            and not any(
                path.startswith(prefix)
                for prefix in PUBLIC_WRITE_PREFIXES
            )
            and not any(
                path.startswith(prefix)
                for prefix in detailed_audit_prefixes
            )
            and response.status_code < 400
        )

        if should_audit_success:
            forwarded_for = request.headers.get("x-forwarded-for", "")
            client_ip = (
                forwarded_for.split(",")[0].strip()
                if forwarded_for
                else (
                    request.client.host
                    if request.client
                    else "inconnue"
                )
            )

            db = SessionLocal()
            try:
                db.add(
                    EventLog(
                        level="INFO",
                        event_type="audit",
                        hostname="OpenDesk Hub",
                        rustdesk_id="",
                        message=(
                            f"{username} — action autorisée : "
                            f"{method} {path} — IP {client_ip}"
                        ),
                    )
                )
                db.commit()
            finally:
                db.close()

        return response
