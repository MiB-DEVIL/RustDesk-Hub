from fastapi import APIRouter, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database.database import SessionLocal
from app.models.event_log import EventLog
from app.services.event_log_service import add_event_log
from app.services.settings_service import get_settings_dict
from app.services.time_service import register_time_filters

router=APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)

@router.post("/api/agent/log")
def receive_agent_log(rustdesk_id:str=Form(""),hostname:str=Form(""),level:str=Form("INFO"),event_type:str=Form("agent"),message:str=Form(""),x_api_key:str=Header(default="")):
    db=SessionLocal(); s=get_settings_dict(db); expected=s.get("agent_api_key","OpenDeskAgent2026")
    if x_api_key!=expected:
        db.close(); raise HTTPException(status_code=401,detail="Invalid API key")
    add_event_log(db,rustdesk_id,hostname,level,event_type,message); db.close()
    return {"status":"ok"}

@router.get("/logs", response_class=HTMLResponse)
def logs_page(request:Request, level:str="", search:str=""):
    if "user" not in request.session: return RedirectResponse("/login",status_code=303)
    db=SessionLocal(); q=db.query(EventLog)
    if level: q=q.filter(EventLog.level==level.upper())
    if search:
        p=f"%{search}%"
        q=q.filter((EventLog.hostname.ilike(p)) | (EventLog.rustdesk_id.ilike(p)) | (EventLog.message.ilike(p)) | (EventLog.event_type.ilike(p)))
    rows=q.order_by(EventLog.created_at.desc()).limit(500).all(); db.close()
    return templates.TemplateResponse(request=request,name="logs.html",context={"rows":rows,"selected_level":level,"search":search})

@router.post("/logs/clear")
def clear_logs(request:Request):
    if "user" not in request.session: return RedirectResponse("/login",status_code=303)
    db=SessionLocal(); db.query(EventLog).delete(); db.commit(); db.close()
    return RedirectResponse("/logs",status_code=303)
