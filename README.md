# Efferve

WiFi presence detection and home automation system.

Efferve ingests device observations from multiple WiFi/network backends, classifies devices by household relevance, associates devices to people, and triggers webhook alerts on presence changes.

## What It Does

- Detects devices from:
  - Ruckus Unleashed API
  - OPNsense DHCP lease API
  - GL.iNet remote monitor (SSH + tcpdump)
  - Monitor mode via scapy
  - Mock source for development/testing
- Builds a device registry with presence history.
- Classifies devices as resident, frequent visitor, or passerby.
- Lets you assign devices to people.
- Triggers webhook alerts on arrive/leave events with SSRF-safe URL validation.

## Current Status

Implemented and working:

- Multi-sniffer runtime and lifecycle management.
- Device registry and presence history.
- Persona management (people + device assignment).
- Alerts engine (rules + webhook dispatch).
- Setup wizard for backend connection testing and config save.
- Security hardening for webhook validation and request handling.
- Config/secrets moved to `.env`-only flow (`EFFERVE_*`).

## Stack

- Python 3.11+
- FastAPI
- SQLModel + SQLite (designed for Postgres migration later)
- Jinja2 + HTMX UI (no JS build system)
- Docker-first deployment

## Quick Start

```bash
cp .env.example .env
# edit .env with your settings
uv run pytest
uv run uvicorn efferve.main:app --reload
```

Open: `http://localhost:8000`

## Architecture & Workflow Charts

Editable source diagrams:

- `docs/diagrams/efferve-architecture.excalidraw`
- `docs/diagrams/efferve-beacon-to-alert.excalidraw`
- `docs/diagrams/efferve-use-cases.excalidraw`
- `docs/diagrams/efferve-setup-workflow.excalidraw`
- `docs/diagrams/efferve-classification.excalidraw`

GitHub-friendly ASCII charts: `docs/diagrams/ASCII_DIAGRAMS.md`

### 1) System Architecture

```text
+------------------------+      +----------------------------------+      +----------------------------+
|      DATA SOURCES      | ---> |             CORE APP             | ---> |          OUTPUTS           |
|------------------------|      |----------------------------------|      |----------------------------|
| - Ruckus (API polling) |      | - Sniffers -> BeaconEvent        |      | - SQLite (devices/persons/ |
| - OPNsense (DHCP API)  |      | - Registry (devices, class, log) |      |   rules/presence)          |
| - GL.iNet (SSH/tcpdump)|      | - Persona (person <-> devices)   |      | - UI (Jinja2 + HTMX)       |
| - Monitor mode (scapy) |      | - Alerts (rules + webhooks)      |      | - REST API (/api/*)        |
| - Mock                 |      |                                  |      | - Webhooks (HTTP POST)     |
+------------------------+      +----------------------------------+      +----------------------------+
```

### 2) Data Flow: Beacon -> Alert

```text
[1] Sniffer observes device
            |
            v
[2] Emit BeaconEvent (MAC, RSSI, SSID, hostname, vendor...)
            |
            v
[3] main._handle_beacon_event
    - upsert_device()
    - reclassify_device()
            |
            v
[4] detect_presence_changes(grace_period)
    -> [(mac, arrive|leave), ...]
            |
            v
[5] evaluate_presence_change()
    - match rules by person/device
    - match trigger type (arrive|leave|both)
            |
            v
[6] dispatch_webhooks()
    - HTTP POST payloads (SSRF-safe URL validation)
```

### 3) Use Cases / Actors

```text
Actors:
  (A) User/Admin
  (B) External System (webhook consumer)
  (C) Sniffer Backends (Ruckus / OPNsense / GL.iNet / Monitor / Mock)

                     +-------------------------------------+
 (A) User/Admin ---->| Configure sniffers (setup wizard)  |
                     +-------------------------------------+
 (A) User/Admin ---->| View devices and presence          |
                     +-------------------------------------+
 (A) User/Admin ---->| Manage people + assign devices     |
                     +-------------------------------------+
 (A) User/Admin ---->| Define alert rules                 |
                     +-------------------------------------+
 (A) User/Admin ---->| Toggle/delete alert rules          |
                     +-------------------------------------+

 (C) Sniffer --------> Report device observations (BeaconEvent)
 (B) External <------- Receive webhook on presence change
```

### 4) Setup + Configuration Workflow

```text
CONFIG SOURCES
  .env (EFFERVE_*)
  process env (overrides .env)
        |
        v
+-------------------------------+
| Setup Wizard (UI)            |
|------------------------------ |
| - Fill Ruckus/OPNsense/GL.iNet|
| - Test -> test_connection()   |
| - Save -> save_config(.env)   |
| - Restart -> restart_sniffer()|
+-------------------------------+
        |
        v
APP STARTUP / RESTART PATH
  load_config()
      -> get_active_sniffer_modes()
      -> _create_sniffer(mode,...)
      -> lifespan starts sniffers
```

### 5) Device Classification

```text
BeaconEvent Stream (RSSI + sightings over time)
                    |
                    v
          +-------------------------+
          | Classification Engine   |
          |-------------------------|
          | - Resident              |
          | - Frequent visitor      |
          | - Passerby              |
          +-------------------------+
                    |
                    v
          +-------------------------+
          | UI Default Visibility   |
          |-------------------------|
          | Show: Resident          |
          | Show: Frequent visitor  |
          | Hide/optional: Passerby |
          +-------------------------+
```
