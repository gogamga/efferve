"""Tests for alert rule CRUD and webhook dispatch."""

from unittest.mock import MagicMock, patch

from sqlmodel import Session

from efferve.alerts.manager import (
    create_rule,
    delete_rule,
    dispatch_webhooks,
    evaluate_presence_change,
    get_rule,
    list_rules,
    update_rule,
)
from efferve.alerts.models import AlertRule, TriggerType
from efferve.persona.models import Person, PersonDevice
from efferve.registry.models import Device


def test_create_rule(session: Session):
    rule = create_rule(
        session,
        name="Test Rule",
        webhook_url="https://example.com/hook",
        trigger_type="arrive",
        mac_address="AA:BB:CC:DD:EE:FF",
    )
    assert rule.id is not None
    assert rule.name == "Test Rule"
    assert rule.trigger_type == TriggerType.arrive
    assert rule.mac_address == "AA:BB:CC:DD:EE:FF"


def test_list_rules(session: Session):
    create_rule(session, name="Rule 1", webhook_url="https://example.com/1")
    create_rule(session, name="Rule 2", webhook_url="https://example.com/2")
    assert len(list_rules(session)) == 2


def test_list_rules_enabled_only(session: Session):
    create_rule(session, name="Rule 1", webhook_url="https://example.com/1")
    r2 = create_rule(session, name="Rule 2", webhook_url="https://example.com/2")
    update_rule(session, r2.id, enabled=False)

    rules = list_rules(session, enabled_only=True)
    assert len(rules) == 1
    assert rules[0].name == "Rule 1"


def test_get_rule(session: Session):
    rule = create_rule(session, name="Test", webhook_url="https://example.com/hook")
    fetched = get_rule(session, rule.id)
    assert fetched is not None
    assert fetched.id == rule.id


def test_get_rule_invalid(session: Session):
    assert get_rule(session, 99999) is None


def test_update_rule(session: Session):
    rule = create_rule(session, name="Old", webhook_url="https://example.com/hook")
    updated = update_rule(session, rule.id, name="New")
    assert updated is not None
    assert updated.name == "New"


def test_update_rule_invalid(session: Session):
    assert update_rule(session, 99999, name="Whatever") is None


def test_delete_rule(session: Session):
    rule = create_rule(session, name="Test", webhook_url="https://example.com/hook")
    assert delete_rule(session, rule.id) is True
    assert get_rule(session, rule.id) is None


def test_delete_rule_invalid(session: Session):
    assert delete_rule(session, 99999) is False


def test_evaluate_arrive_event(session: Session):
    create_rule(
        session,
        name="Arrive Only",
        webhook_url="https://example.com/hook",
        trigger_type="arrive",
    )
    payloads = evaluate_presence_change(
        session, mac_address="AA:BB:CC:DD:EE:FF", event_type="arrive"
    )
    assert len(payloads) == 1
    assert payloads[0]["event"] == "arrive"

    # Should NOT match depart
    payloads = evaluate_presence_change(
        session, mac_address="AA:BB:CC:DD:EE:FF", event_type="depart"
    )
    assert len(payloads) == 0


def test_evaluate_depart_event(session: Session):
    create_rule(
        session,
        name="Depart Only",
        webhook_url="https://example.com/hook",
        trigger_type="depart",
    )
    payloads = evaluate_presence_change(
        session, mac_address="AA:BB:CC:DD:EE:FF", event_type="depart"
    )
    assert len(payloads) == 1
    assert payloads[0]["event"] == "depart"


def test_evaluate_both_event(session: Session):
    create_rule(
        session,
        name="Both",
        webhook_url="https://example.com/hook",
        trigger_type="both",
    )
    arrive = evaluate_presence_change(
        session, mac_address="AA:BB:CC:DD:EE:FF", event_type="arrive"
    )
    depart = evaluate_presence_change(
        session, mac_address="AA:BB:CC:DD:EE:FF", event_type="depart"
    )
    assert len(arrive) == 1
    assert len(depart) == 1


def test_evaluate_mac_filter(session: Session):
    create_rule(
        session,
        name="MAC filter",
        webhook_url="https://example.com/hook",
        trigger_type="arrive",
        mac_address="AA:BB:CC:DD:EE:FF",
    )
    matched = evaluate_presence_change(
        session, mac_address="AA:BB:CC:DD:EE:FF", event_type="arrive"
    )
    assert len(matched) == 1

    not_matched = evaluate_presence_change(
        session, mac_address="11:22:33:44:55:66", event_type="arrive"
    )
    assert len(not_matched) == 0


def test_evaluate_person_filter(session: Session):
    person = Person(name="Alice")
    session.add(person)
    session.commit()
    session.refresh(person)

    session.add(Device(mac_address="AA:BB:CC:DD:EE:FF"))
    session.commit()
    session.add(PersonDevice(person_id=person.id, mac_address="AA:BB:CC:DD:EE:FF"))
    session.commit()

    create_rule(
        session,
        name="Person filter",
        webhook_url="https://example.com/hook",
        trigger_type="arrive",
        person_id=person.id,
    )
    matched = evaluate_presence_change(
        session, mac_address="AA:BB:CC:DD:EE:FF", event_type="arrive"
    )
    assert len(matched) == 1
    assert matched[0]["person"]["name"] == "Alice"

    # Different device not assigned to person
    session.add(Device(mac_address="11:22:33:44:55:66"))
    session.commit()
    not_matched = evaluate_presence_change(
        session, mac_address="11:22:33:44:55:66", event_type="arrive"
    )
    assert len(not_matched) == 0


def test_evaluate_wildcard_rule(session: Session):
    create_rule(
        session,
        name="Catch all",
        webhook_url="https://example.com/hook",
        trigger_type="arrive",
    )
    p1 = evaluate_presence_change(
        session, mac_address="AA:BB:CC:DD:EE:FF", event_type="arrive"
    )
    p2 = evaluate_presence_change(
        session, mac_address="11:22:33:44:55:66", event_type="arrive"
    )
    assert len(p1) == 1
    assert len(p2) == 1


def test_dispatch_webhooks_success():
    payloads = [
        {
            "event": "arrive",
            "timestamp": "2024-01-15T10:30:00Z",
            "device": {"mac_address": "AA:BB:CC:DD:EE:FF", "name": "iPhone"},
            "person": None,
            "rule": {"id": 1, "name": "Test"},
            "_webhook_url": "https://example.com/hook",
        }
    ]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True

    with patch("efferve.alerts.manager.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        results = dispatch_webhooks(payloads)
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["status_code"] == 200
        mock_client.post.assert_called_once()


def test_dispatch_webhooks_failure():
    payloads = [
        {
            "event": "arrive",
            "timestamp": "2024-01-15T10:30:00Z",
            "device": {"mac_address": "AA:BB:CC:DD:EE:FF", "name": "iPhone"},
            "person": None,
            "rule": {"id": 1, "name": "Test"},
            "_webhook_url": "https://example.com/hook",
        }
    ]

    with patch("efferve.alerts.manager.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("Connection failed")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        results = dispatch_webhooks(payloads)
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "Connection failed" in results[0]["error"]
