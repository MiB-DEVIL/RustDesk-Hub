from collections import defaultdict
from datetime import datetime, timedelta
import csv
import io
import json

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.client import Client
from app.models.professional_inventory import ProfessionalInventory
from app.services.time_service import register_time_filters


router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


def _load_json(raw, fallback):
    try:
        value = json.loads(raw or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return value


def _software_rows(db):
    rows = (
        db.query(Client, ProfessionalInventory)
        .join(
            ProfessionalInventory,
            ProfessionalInventory.client_id == Client.id,
        )
        .order_by(Client.name.asc())
        .all()
    )

    catalog = defaultdict(
        lambda: {
            "name": "",
            "version": "",
            "publisher": "",
            "architecture": "",
            "machines": set(),
            "machine_ids": set(),
        }
    )

    machine_count = 0

    for client, inventory in rows:
        machine_count += 1
        software = _load_json(inventory.software_json, [])

        if not isinstance(software, list):
            continue

        seen_on_machine = set()

        for item in software:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or "").strip()
            if not name:
                continue

            version = str(item.get("version") or "").strip()
            publisher = str(item.get("publisher") or "").strip()
            architecture = str(
                item.get("architecture") or ""
            ).strip()

            key = (
                name.lower(),
                version.lower(),
                publisher.lower(),
                architecture.lower(),
            )

            record = catalog[key]
            record["name"] = name
            record["version"] = version
            record["publisher"] = publisher
            record["architecture"] = architecture

            if key not in seen_on_machine:
                record["machines"].add(client.name)
                record["machine_ids"].add(client.id)
                seen_on_machine.add(key)

    result = []

    for record in catalog.values():
        result.append(
            {
                "name": record["name"],
                "version": record["version"],
                "publisher": record["publisher"],
                "architecture": record["architecture"],
                "machine_count": len(record["machine_ids"]),
                "machines": sorted(record["machines"]),
            }
        )

    result.sort(
        key=lambda item: (
            item["name"].lower(),
            item["version"].lower(),
        )
    )

    return result, machine_count


@router.get("/software", response_class=HTMLResponse)
def software_catalog(
    request: Request,
    search: str = "",
    publisher: str = "",
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    rows, machine_count = _software_rows(db)
    db.close()

    publishers = sorted(
        {
            item["publisher"]
            for item in rows
            if item["publisher"]
        },
        key=str.lower,
    )

    search_value = search.strip().lower()
    publisher_value = publisher.strip().lower()

    filtered = []

    for item in rows:
        searchable = " ".join(
            [
                item["name"],
                item["version"],
                item["publisher"],
                item["architecture"],
                " ".join(item["machines"]),
            ]
        ).lower()

        if search_value and search_value not in searchable:
            continue

        if (
            publisher_value
            and item["publisher"].lower() != publisher_value
        ):
            continue

        filtered.append(item)

    unique_names = len(
        {item["name"].lower() for item in rows}
    )
    total_installations = sum(
        item["machine_count"] for item in rows
    )

    return templates.TemplateResponse(
        request=request,
        name="software_catalog.html",
        context={
            "rows": filtered,
            "publishers": publishers,
            "search": search,
            "selected_publisher": publisher,
            "machine_count": machine_count,
            "unique_names": unique_names,
            "total_installations": total_installations,
        },
    )


@router.get("/software/export.csv")
def software_export(
    request: Request,
    search: str = "",
    publisher: str = "",
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    rows, _ = _software_rows(db)
    db.close()

    search_value = search.strip().lower()
    publisher_value = publisher.strip().lower()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "Logiciel",
            "Version",
            "Éditeur",
            "Architecture",
            "Nombre de machines",
            "Machines",
        ]
    )

    for item in rows:
        searchable = " ".join(
            [
                item["name"],
                item["version"],
                item["publisher"],
                item["architecture"],
                " ".join(item["machines"]),
            ]
        ).lower()

        if search_value and search_value not in searchable:
            continue

        if (
            publisher_value
            and item["publisher"].lower() != publisher_value
        ):
            continue

        writer.writerow(
            [
                item["name"],
                item["version"],
                item["publisher"],
                item["architecture"],
                item["machine_count"],
                ", ".join(item["machines"]),
            ]
        )

    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="opendesk-logiciels.csv"'
            )
        },
    )


def _parse_french_date(value):
    if not value:
        return None

    for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(
                str(value).strip(),
                date_format,
            )
        except ValueError:
            continue

    return None


@router.get("/update-compliance", response_class=HTMLResponse)
def update_compliance(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    rows = (
        db.query(Client, ProfessionalInventory)
        .outerjoin(
            ProfessionalInventory,
            ProfessionalInventory.client_id == Client.id,
        )
        .order_by(Client.name.asc())
        .all()
    )

    now = datetime.utcnow()
    warning_limit = now - timedelta(days=60)
    critical_limit = now - timedelta(days=120)

    results = []
    compliant = 0
    warning = 0
    critical = 0
    unknown = 0

    for client, inventory in rows:
        hotfixes = (
            _load_json(inventory.hotfixes_json, [])
            if inventory
            else []
        )

        latest_date = None
        latest_kb = ""

        if isinstance(hotfixes, list):
            for item in hotfixes:
                if not isinstance(item, dict):
                    continue

                installed = _parse_french_date(
                    item.get("installed_on")
                )

                if installed and (
                    latest_date is None
                    or installed > latest_date
                ):
                    latest_date = installed
                    latest_kb = str(
                        item.get("hotfix_id") or ""
                    )

        if latest_date is None:
            state = "unknown"
            label = "Inconnu"
            unknown += 1
        elif latest_date < critical_limit:
            state = "critical"
            label = "Critique"
            critical += 1
        elif latest_date < warning_limit:
            state = "warning"
            label = "À vérifier"
            warning += 1
        else:
            state = "healthy"
            label = "À jour"
            compliant += 1

        results.append(
            {
                "client_id": client.id,
                "machine": client.name,
                "hostname": client.hostname or "-",
                "online": bool(client.online),
                "state": state,
                "label": label,
                "latest_date": latest_date,
                "latest_kb": latest_kb,
                "hotfix_count": (
                    len(hotfixes)
                    if isinstance(hotfixes, list)
                    else 0
                ),
            }
        )

    db.close()

    coverage = len(results) - unknown
    compliance_rate = (
        round((compliant / coverage) * 100, 1)
        if coverage > 0
        else 0
    )

    results.sort(
        key=lambda item: (
            {
                "critical": 0,
                "warning": 1,
                "unknown": 2,
                "healthy": 3,
            }.get(item["state"], 4),
            item["machine"].lower(),
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="update_compliance.html",
        context={
            "rows": results,
            "compliant": compliant,
            "warning": warning,
            "critical": critical,
            "unknown": unknown,
            "compliance_rate": compliance_rate,
        },
    )
