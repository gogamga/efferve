"""REST API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from efferve.config import settings
from efferve.database import get_session
from efferve.registry.models import Device, DeviceClassification
from efferve.registry.store import get_all_devices, get_device, get_present_devices

router = APIRouter(prefix="/api")


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
) -> dict:
    grace = settings.presence_grace_period
    devices = get_present_devices(session, grace_seconds=grace)
    return {
        "present_count": len(devices),
        "grace_seconds": grace,
        "devices": devices,
    }
