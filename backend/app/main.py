from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database.database import Base, SessionLocal, engine

from app.models.agent_action import AgentAction
from app.models.client import Client
from app.models.event_log import EventLog
from app.models.group import Group
from app.models.inventory import Inventory
from app.models.professional_inventory import ProfessionalInventory
from app.models.machine_change import MachineChange
from app.models.setting import Setting
from app.models.user import User

from app.routes.actions import router as actions_router
from app.routes.administration import router as administration_router
from app.routes.address_book import router as address_book_router
from app.routes.agent import router as agent_router
from app.routes.auth import router as auth_router
from app.routes.clients import router as clients_router
from app.routes.dashboard import router as dashboard_router
from app.routes.diagnostic import router as diagnostic_router
from app.routes.groups import router as groups_router
from app.routes.inventory import router as inventory_router
from app.routes.logs import router as logs_router
from app.routes.machines import router as machines_router
from app.routes.notifications import router as notifications_router
from app.routes.settings import router as settings_router
from app.routes.tasks import router as tasks_router
from app.routes.users import router as users_router
from app.routes.audit import router as audit_router
from app.routes.profile import router as profile_router
from app.routes.fleet_inventory import router as fleet_inventory_router
from app.middleware.access_control import AccessControlMiddleware

from app.services.init_admin import create_default_admin
from app.services.settings_service import ensure_default_settings

Base.metadata.create_all(bind=engine)

db = SessionLocal()
create_default_admin(db)
ensure_default_settings(db)
db.close()

app = FastAPI(
    title="OpenDesk Hub",
    version="1.2.1"
)

# L'ordre est important : Starlette exécute en premier le dernier
# middleware ajouté. SessionMiddleware doit donc envelopper
# AccessControlMiddleware afin que request.session soit disponible.
app.add_middleware(AccessControlMiddleware)

app.add_middleware(
    SessionMiddleware,
    secret_key="OpenDeskHubSuperSecret2026",
    max_age=28800,
    same_site="lax",
)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(diagnostic_router)
app.include_router(clients_router)
app.include_router(groups_router)
app.include_router(agent_router)
app.include_router(address_book_router)
app.include_router(inventory_router)
app.include_router(actions_router)
app.include_router(administration_router)
app.include_router(logs_router)
app.include_router(settings_router)
app.include_router(machines_router)
app.include_router(notifications_router)
app.include_router(tasks_router)
app.include_router(users_router)
app.include_router(audit_router)
app.include_router(profile_router)
app.include_router(fleet_inventory_router)

@app.get("/")
def root():
    return {
        "application": "OpenDesk Hub",
        "version": "1.2.1",
        "database": "sqlite",
        "status": "running"
    }
