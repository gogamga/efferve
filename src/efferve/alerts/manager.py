"""Alert evaluation and webhook dispatch."""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import Session, select

from efferve.alerts.models import AlertRule, TriggerType
from efferve.persona.models import Person, PersonDevice
from efferve.registry.store import normalize_mac

logger = logging.getLogger(__name__)


def create_rule(
    session: Session,
    name: str,
    webhook_url: str,
    trigger_type: str = "both",
    person_id: int | None = None,
    mac_address: str | None = None,
) -> AlertRule:
    """Create a new alert rule."""
    rule = AlertRule(
        name=name,
        webhook_url=webhook_url,
        trigger_type=TriggerType(trigger_type),
        person_id=person_id,
        mac_address=normalize_mac(mac_address) if mac_address else None,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def get_rule(session: Session, rule_id: int) -> AlertRule | None:
    """Get a single alert rule by ID."""
    return session.get(AlertRule, rule_id)


def list_rules(session: Session, enabled_only: bool = False) -> list[AlertRule]:
    """List all alert rules, optionally filtering to only enabled rules."""
    stmt = select(AlertRule)
    if enabled_only:
        stmt = stmt.where(AlertRule.enabled == True)  # noqa: E712
    stmt = stmt.order_by(AlertRule.created_at.desc())  # type: ignore[attr-defined]
    return list(session.exec(stmt).all())


def update_rule(session: Session, rule_id: int, **kwargs: object) -> AlertRule | None:
    """Update an alert rule. Return None if not found."""
    rule = session.get(AlertRule, rule_id)
    if rule is None:
        return None

    # Normalize mac_address if provided
    if "mac_address" in kwargs and isinstance(kwargs["mac_address"], str):
        kwargs["mac_address"] = normalize_mac(kwargs["mac_address"])

    # Convert trigger_type to enum if provided as string
    if "trigger_type" in kwargs and isinstance(kwargs["trigger_type"], str):
        kwargs["trigger_type"] = TriggerType(kwargs["trigger_type"])

    for key, value in kwargs.items():
        if hasattr(rule, key):
            setattr(rule, key, value)

    session.commit()
    session.refresh(rule)
    return rule


def delete_rule(session: Session, rule_id: int) -> bool:
    """Delete an alert rule. Return True if deleted, False if not found."""
    rule = session.get(AlertRule, rule_id)
    if rule is None:
        return False

    session.delete(rule)
    session.commit()
    return True


def evaluate_presence_change(
    session: Session,
    mac_address: str,
    event_type: str,
    device_name: str | None = None,
    person_name: str | None = None,
) -> list[dict[str, Any]]:
    """Check all enabled rules and return matched rules + webhook payloads.

    Args:
        session: Database session
        mac_address: MAC address of the device
        event_type: "arrive" or "depart"
        device_name: Display name of the device (optional)
        person_name: Name of the person (optional, will be looked up if not provided)

    Returns:
        List of webhook payloads to dispatch
    """
    mac_address = normalize_mac(mac_address)
    rules = list_rules(session, enabled_only=True)
    payloads = []

    # Look up the person associated with this device
    person_id: int | None = None
    if not person_name:
        # Query PersonDevice to find if this device is linked to a person
        person_device_stmt = select(PersonDevice).where(PersonDevice.mac_address == mac_address)
        person_device = session.exec(person_device_stmt).first()
        if person_device:
            person_id = person_device.person_id
            person = session.get(Person, person_id)
            if person:
                person_name = person.name
    else:
        # If person_name provided, look up the person_id
        person_stmt = (
            select(Person).join(PersonDevice).where(PersonDevice.mac_address == mac_address)
        )
        person = session.exec(person_stmt).first()
        if person:
            person_id = person.id

    for rule in rules:
        # Filter by trigger_type
        if rule.trigger_type == TriggerType.arrive and event_type != "arrive":
            continue
        if rule.trigger_type == TriggerType.depart and event_type != "depart":
            continue

        # Filter by person_id or mac_address
        matched = False
        if rule.person_id is not None:
            # Rule targets a specific person
            if person_id == rule.person_id:
                matched = True
        elif rule.mac_address is not None:
            # Rule targets a specific MAC address
            if mac_address == rule.mac_address:
                matched = True
        else:
            # Rule matches all events
            matched = True

        if not matched:
            continue

        # Build webhook payload
        payload = {
            "event": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "device": {
                "mac_address": mac_address,
                "name": device_name or mac_address,
            },
            "person": (
                {"id": person_id, "name": person_name} if person_id and person_name else None
            ),
            "rule": {
                "id": rule.id,
                "name": rule.name,
            },
            "_webhook_url": rule.webhook_url,  # Internal field for dispatch
        }
        payloads.append(payload)

    return payloads


def dispatch_webhooks(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fire HTTP POSTs for each payload. Return results with status codes.

    Args:
        payloads: List of webhook payloads from evaluate_presence_change

    Returns:
        List of dicts with keys: payload, url, status_code, success, error (if failed)
    """
    results = []

    for payload in payloads:
        # Extract internal webhook URL and remove it from the payload
        url = payload.pop("_webhook_url", None)
        if not url or not isinstance(url, str):
            logger.warning("No webhook URL found in payload: %s", payload)
            continue

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=payload)
                results.append(
                    {
                        "payload": payload,
                        "url": url,
                        "status_code": response.status_code,
                        "success": response.is_success,
                    }
                )
                if response.is_success:
                    logger.info(
                        "Webhook delivered: %s → %s (HTTP %d)",
                        payload["event"],
                        url,
                        response.status_code,
                    )
                else:
                    logger.warning(
                        "Webhook failed: %s → %s (HTTP %d)",
                        payload["event"],
                        url,
                        response.status_code,
                    )
        except Exception as e:
            logger.error("Webhook dispatch error: %s → %s: %s", payload["event"], url, e)
            results.append(
                {
                    "payload": payload,
                    "url": url,
                    "status_code": None,
                    "success": False,
                    "error": str(e),
                }
            )

    return results
