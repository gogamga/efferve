"""REST API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from efferve.alerts.manager import (
    create_rule,
    delete_rule,
    get_rule,
    list_rules,
    update_rule,
)
from efferve.alerts.models import AlertRule, TriggerType
from efferve.config import settings
from efferve.database import get_session
from efferve.persona.engine import (
    assign_device,
    create_person,
    delete_person,
    get_person,
    get_person_devices,
    get_present_persons,
    list_persons,
    unassign_device,
)
from efferve.persona.models import Person
from efferve.registry.models import Device, DeviceClassification, PresenceLog
from efferve.registry.store import (
    get_all_devices,
    get_device,
    get_presence_history,
    get_present_devices,
    set_display_name,
)

router = APIRouter(prefix="/api")


# Request models
class UpdateDeviceRequest(BaseModel):
    display_name: str


class CreatePersonRequest(BaseModel):
    name: str


class AssignDeviceRequest(BaseModel):
    mac_address: str


class CreateAlertRuleRequest(BaseModel):
    name: str
    webhook_url: str
    trigger_type: TriggerType = TriggerType.both
    person_id: int | None = None
    mac_address: str | None = None


class UpdateAlertRuleRequest(BaseModel):
    name: str | None = None
    webhook_url: str | None = None
    trigger_type: TriggerType | None = None
    person_id: int | None = None
    mac_address: str | None = None
    enabled: bool | None = None


@router.get("/devices")
def list_devices(
    classification: DeviceClassification | None = None,
    session: Session = Depends(get_session),
) -> list[Device]:
    return get_all_devices(session, classification=classification)


@router.get("/devices/{mac}")
def device_detail(
    mac: str,
    session: Session = Depends(get_session),
) -> Device:
    device = get_device(session, mac)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/presence")
def presence_summary(
    session: Session = Depends(get_session),
) -> dict[str, int | list[Device]]:
    grace = settings.presence_grace_period
    devices = get_present_devices(session, grace_seconds=grace)
    return {
        "present_count": len(devices),
        "grace_seconds": grace,
        "devices": devices,
    }


# --- Device Management ---


@router.patch("/devices/{mac}")
def update_device(
    mac: str,
    request: UpdateDeviceRequest,
    session: Session = Depends(get_session),
) -> Device:
    device = set_display_name(session, mac, request.display_name)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


# --- Presence History ---


@router.get("/presence/history")
def get_history(
    mac: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> list[PresenceLog]:
    return get_presence_history(session, mac_address=mac, limit=limit)


# --- Persona CRUD ---


@router.get("/persons")
def list_all_persons(
    session: Session = Depends(get_session),
) -> list[Person]:
    return list_persons(session)


@router.post("/persons", status_code=201)
def create_new_person(
    request: CreatePersonRequest,
    session: Session = Depends(get_session),
) -> Person:
    return create_person(session, request.name)


# Literal path must come before {person_id} parametric path
@router.get("/persons/presence")
def get_persons_present(
    session: Session = Depends(get_session),
) -> list[dict[str, int | str | list[dict[str, str]]]]:
    grace = settings.presence_grace_period
    return get_present_persons(session, grace_seconds=grace)


@router.get("/persons/{person_id}")
def get_person_detail(
    person_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Person | list[Device]]:
    person = get_person(session, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    devices = get_person_devices(session, person_id)
    return {"person": person, "devices": devices}


@router.delete("/persons/{person_id}")
def delete_existing_person(
    person_id: int,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    if not delete_person(session, person_id):
        raise HTTPException(status_code=404, detail="Person not found")
    return {"status": "deleted"}


@router.post("/persons/{person_id}/devices")
def assign_device_to_person(
    person_id: int,
    request: AssignDeviceRequest,
    session: Session = Depends(get_session),
) -> dict[str, int | str]:
    try:
        link = assign_device(session, person_id, request.mac_address)
        return {"person_id": link.person_id, "mac_address": link.mac_address}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/persons/{person_id}/devices/{mac}")
def unassign_device_from_person(
    person_id: int,
    mac: str,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    if not unassign_device(session, person_id, mac):
        raise HTTPException(status_code=404, detail="Device assignment not found")
    return {"status": "unassigned"}


# --- Alert Rules CRUD ---


@router.get("/alerts")
def list_alert_rules(
    enabled_only: bool = False,
    session: Session = Depends(get_session),
) -> list[AlertRule]:
    return list_rules(session, enabled_only=enabled_only)


@router.post("/alerts", status_code=201)
def create_alert_rule(
    request: CreateAlertRuleRequest,
    session: Session = Depends(get_session),
) -> AlertRule:
    return create_rule(
        session,
        name=request.name,
        webhook_url=request.webhook_url,
        trigger_type=request.trigger_type,
        person_id=request.person_id,
        mac_address=request.mac_address,
    )


@router.get("/alerts/{rule_id}")
def get_alert_rule(
    rule_id: int,
    session: Session = Depends(get_session),
) -> AlertRule:
    rule = get_rule(session, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.patch("/alerts/{rule_id}")
def update_alert_rule(
    rule_id: int,
    request: UpdateAlertRuleRequest,
    session: Session = Depends(get_session),
) -> AlertRule:
    # Only pass non-None values to update_rule
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    rule = update_rule(session, rule_id, **updates)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.delete("/alerts/{rule_id}")
def delete_alert_rule(
    rule_id: int,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    if not delete_rule(session, rule_id):
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"status": "deleted"}
