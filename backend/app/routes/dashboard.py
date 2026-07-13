import asyncio

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.services.dashboard_service import build_dashboard_snapshot
from app.services.time_service import register_time_filters

router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    try:
        snapshot = build_dashboard_snapshot(db)
    finally:
        db.close()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "snapshot": snapshot,
            "username": request.session["user"],
        },
    )


@router.get("/api/dashboard/snapshot")
def dashboard_snapshot(request: Request):
    if "user" not in request.session:
        return {"authenticated": False}

    db = SessionLocal()
    try:
        return build_dashboard_snapshot(db)
    finally:
        db.close()


@router.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket):
    session = websocket.scope.get("session", {})
    if "user" not in session:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    try:
        while True:
            db = SessionLocal()
            try:
                snapshot = build_dashboard_snapshot(db)
            finally:
                db.close()

            await websocket.send_json(snapshot)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
