#!/usr/bin/env python3
"""Generate .excalidraw JSON files for Efferve architecture and workflow diagrams."""

import json
import random
from pathlib import Path

# Excalidraw schema: https://docs.excalidraw.com/docs/codebase/json-schema
EXCALIDRAW_VERSION = 2
SOURCE = "https://excalidraw.com"


def _id() -> str:
    return "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=21))


def _seed() -> int:
    return random.randint(1, 2**31 - 1)


def rect(
    x: float,
    y: float,
    width: float,
    height: float,
    label: str,
    fill: str = "#e7f5ff",
    stroke: str = "#1971c2",
) -> dict:
    return {
        "id": _id(),
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3, "value": 16},
        "seed": _seed(),
        "version": 1,
        "versionNonce": _seed(),
        "isDeleted": False,
        "boundElements": None,
        "locked": False,
        "updated": 1,
    }


def text_el(x: float, y: float, content: str, fontSize: int = 16) -> dict:
    return {
        "id": _id(),
        "type": "text",
        "x": x,
        "y": y,
        "width": max(20, len(content) * 8),
        "height": fontSize + 8,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": _seed(),
        "version": 1,
        "versionNonce": _seed(),
        "isDeleted": False,
        "boundElements": None,
        "text": content,
        "fontSize": fontSize,
        "fontFamily": 1,
        "textAlign": "left",
        "verticalAlign": "top",
        "containerId": None,
        "originalText": content,
        "lineHeight": 1.25,
        "locked": False,
        "updated": 1,
    }


def arrow(x: float, y: float, dx: float, dy: float) -> dict:
    return {
        "id": _id(),
        "type": "arrow",
        "x": x,
        "y": y,
        "width": abs(dx),
        "height": abs(dy),
        "angle": 0,
        "strokeColor": "#495057",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 2},
        "seed": _seed(),
        "version": 1,
        "versionNonce": _seed(),
        "isDeleted": False,
        "boundElements": None,
        "points": [[0, 0], [dx, dy]],
        "lastCommittedPoint": None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "startBinding": None,
        "endBinding": None,
        "locked": False,
        "updated": 1,
    }


def build_architecture() -> list[dict]:
    els: list[dict] = []
    bx, by = 20, 80
    # Left column: data sources
    r1 = rect(bx, by, 160, 180, "Data sources", "#fff3bf", "#f59f00")
    els.append(r1)
    els.append(text_el(bx + 10, by + 8, "Data sources", 14))
    els.append(text_el(bx + 12, by + 40, "Ruckus (API)"))
    els.append(text_el(bx + 12, by + 62, "OPNsense (DHCP)"))
    els.append(text_el(bx + 12, by + 84, "GL.iNet (SSH+tcpdump)"))
    els.append(text_el(bx + 12, by + 106, "Monitor (scapy)"))
    els.append(text_el(bx + 12, by + 128, "Mock"))
    # Center: core app
    cx, cy = 220, 60
    r2 = rect(cx, cy, 200, 220, "Core app", "#d3f9d8", "#2f9e44")
    els.append(r2)
    els.append(text_el(cx + 10, cy + 8, "Core app", 14))
    els.append(text_el(cx + 12, cy + 40, "Sniffers → BeaconEvent"))
    els.append(text_el(cx + 12, cy + 72, "Registry (devices,"))
    els.append(text_el(cx + 12, cy + 92, "classification, presence)"))
    els.append(text_el(cx + 12, cy + 120, "Persona (persons,"))
    els.append(text_el(cx + 12, cy + 140, "device assignment)"))
    els.append(text_el(cx + 12, cy + 168, "Alerts (rules,"))
    els.append(text_el(cx + 12, cy + 188, "webhook dispatch)"))
    # Right: outputs
    rx, ry = 460, 80
    r3 = rect(rx, ry, 180, 180, "Outputs", "#f3d9fa", "#9c36b5")
    els.append(r3)
    els.append(text_el(rx + 10, ry + 8, "Outputs", 14))
    els.append(text_el(rx + 12, ry + 40, "SQLite (DB)"))
    els.append(text_el(rx + 12, ry + 68, "UI (Jinja2+HTMX)"))
    els.append(text_el(rx + 12, ry + 96, "REST API /api/*"))
    els.append(text_el(rx + 12, ry + 124, "Webhooks (HTTP POST)"))
    # Arrows
    els.append(arrow(180, 170, 40, 0))
    els.append(arrow(420, 170, 40, 0))
    return els


def build_beacon_to_alert() -> list[dict]:
    els: list[dict] = []
    x, y = 30, 40
    step = 120
    boxes = [
        "1. Sniffer observes device",
        "2. BeaconEvent (MAC,RSSI,...)",
        "3. upsert_device, reclassify",
        "4. detect_presence_changes",
        "5. evaluate_presence_change",
        "6. dispatch_webhooks",
    ]
    for i, label in enumerate(boxes):
        r = rect(x + i * step, y, 100, 56, label, "#e7f5ff", "#1971c2")
        els.append(r)
        # Wrap text
        words = label.split()
        line1 = " ".join(words[:3]) if len(words) >= 3 else label
        line2 = " ".join(words[3:]) if len(words) > 3 else ""
        els.append(text_el(x + i * step + 6, y + 8, line1, 12))
        if line2:
            els.append(text_el(x + i * step + 6, y + 26, line2, 12))
    for i in range(5):
        els.append(arrow(x + (i + 1) * step - 10, y + 28, 30, 0))
    return els


def build_use_cases() -> list[dict]:
    els: list[dict] = []
    # Actors
    els.append(text_el(20, 20, "User (admin)", 14))
    els.append(text_el(20, 120, "External system", 14))
    els.append(text_el(20, 200, "Sniffer backends", 14))
    # Use case ovals (rectangles as placeholders)
    uc_x = 220
    ucs = [
        "Configure sniffers (setup wizard)",
        "View devices & presence",
        "Manage people, assign devices",
        "Define alert rules",
        "Toggle/delete rules",
        "Receive webhook",
        "Report BeaconEvent to app",
    ]
    for i, uc in enumerate(ucs):
        yy = 30 + i * 42
        r = rect(uc_x, yy, 260, 34, uc, "#fff9db", "#f59f00")
        els.append(r)
        els.append(text_el(uc_x + 8, yy + 6, uc, 12))
    return els


def build_setup_workflow() -> list[dict]:
    els: list[dict] = []
    x, y = 30, 30
    # Config sources
    r1 = rect(x, y, 180, 70, "Config", "#d3f9d8", "#2f9e44")
    els.append(r1)
    els.append(text_el(x + 10, y + 8, "Config sources", 14))
    els.append(text_el(x + 12, y + 36, ".env (EFFERVE_*)"))
    els.append(text_el(x + 12, y + 54, "process env (overrides)"))
    # Setup wizard
    r2 = rect(x, y + 100, 180, 90, "Setup wizard", "#e7f5ff", "#1971c2")
    els.append(r2)
    els.append(text_el(x + 10, y + 108, "Setup wizard (UI)", 14))
    els.append(text_el(x + 12, y + 132, "Test → test_connection"))
    els.append(text_el(x + 12, y + 152, "Save → save_config(.env)"))
    els.append(text_el(x + 12, y + 172, "→ restart_sniffer"))
    # Startup
    r3 = rect(x, y + 220, 180, 80, "Startup", "#f3d9fa", "#9c36b5")
    els.append(r3)
    els.append(text_el(x + 10, y + 228, "On startup", 14))
    els.append(text_el(x + 12, y + 252, "load_config → get_active_sniffer_modes"))
    els.append(text_el(x + 12, y + 272, "→ _create_sniffer → lifespan"))
    els.append(arrow(x + 90, y + 70, 0, 30))
    els.append(arrow(x + 90, y + 190, 0, 30))
    return els


def build_classification() -> list[dict]:
    els: list[dict] = []
    x, y = 30, 40
    r1 = rect(x, y, 140, 70, "Input", "#e7f5ff", "#1971c2")
    els.append(r1)
    els.append(text_el(x + 10, y + 8, "BeaconEvent stream", 14))
    els.append(text_el(x + 12, y + 38, "RSSI, frequency"))
    r2 = rect(x + 180, y, 160, 70, "Classification", "#d3f9d8", "#2f9e44")
    els.append(r2)
    els.append(text_el(x + 190, y + 8, "Classification", 14))
    els.append(text_el(x + 192, y + 36, "Resident"))
    els.append(text_el(x + 192, y + 52, "Frequent visitor / Passerby"))
    r3 = rect(x + 370, y, 140, 70, "UI", "#f3d9fa", "#9c36b5")
    els.append(r3)
    els.append(text_el(x + 380, y + 8, "UI", 14))
    els.append(text_el(x + 382, y + 36, "Default: Resident +"))
    els.append(text_el(x + 382, y + 52, "Frequent visitor"))
    els.append(arrow(x + 140, y + 35, 40, 0))
    els.append(arrow(x + 340, y + 35, 30, 0))
    return els


def write_diagram(filename: str, elements: list[dict]) -> None:
    out = {
        "type": "excalidraw",
        "version": EXCALIDRAW_VERSION,
        "source": SOURCE,
        "elements": elements,
        "appState": {
            "gridSize": 20,
            "viewBackgroundColor": "#ffffff",
        },
        "files": {},
    }
    path = Path(__file__).parent / filename
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def main() -> None:
    random.seed(42)
    write_diagram("efferve-architecture.excalidraw", build_architecture())
    write_diagram("efferve-beacon-to-alert.excalidraw", build_beacon_to_alert())
    write_diagram("efferve-use-cases.excalidraw", build_use_cases())
    write_diagram("efferve-setup-workflow.excalidraw", build_setup_workflow())
    write_diagram("efferve-classification.excalidraw", build_classification())


if __name__ == "__main__":
    main()
