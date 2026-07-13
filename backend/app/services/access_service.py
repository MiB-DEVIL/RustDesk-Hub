from fastapi import Request
from fastapi.responses import RedirectResponse


def current_username(request: Request) -> str:
    return str(request.session.get("user", ""))


def is_admin(request: Request) -> bool:
    return bool(request.session.get("is_admin", False))


def require_login(request: Request):
    if not current_username(request):
        return RedirectResponse("/login", status_code=303)
    return None


def require_admin(request: Request):
    login_redirect = require_login(request)
    if login_redirect:
        return login_redirect

    if not is_admin(request):
        return RedirectResponse(
            "/dashboard?error=admin_required",
            status_code=303,
        )

    return None
