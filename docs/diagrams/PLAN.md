# Plan: Architecture and use-case diagrams

Use [Excalidraw](https://excalidraw.com) to create the diagrams below. Save source as `.excalidraw` and optionally export PNG/SVG into this folder.

---

## 1. System architecture (high level)

**File:** `efferve-architecture.excalidraw`

**Goal:** One-page view of how Efferve is structured and how data flows.

**Suggested content:**

- **Left:** Data sources
  - Ruckus Unleashed (API polling)
  - OPNsense (DHCP lease API)
  - GL.iNet (SSH + tcpdump)
  - Monitor mode (scapy, raw WiFi)
  - Mock (testing)
- **Center:** Core app
  - “Sniffers” → emit **BeaconEvent**
  - “Registry” (devices, classification, presence log)
  - “Persona” (persons, device assignment)
  - “Alerts” (rules, webhook dispatch)
- **Right:** Outputs
  - SQLite (devices, persons, rules, presence log)
  - UI (Jinja2 + HTMX): dashboard, devices, people, alerts, setup
  - REST API (`/api/*`)
  - Webhooks (HTTP POST on presence change)
- **Flow:** Sniffers → BeaconEvent → Registry (upsert + reclassify) → presence change detection → Alerts (evaluate rules → dispatch webhooks).

Keep it block-and-arrow style; no need for class names.

---

## 2. Data flow: beacon to alert

**File:** `efferve-beacon-to-alert.excalidraw`

**Goal:** Sequence from “device seen” to “webhook fired”.

**Suggested steps (left to right or top to bottom):**

1. Sniffer observes device (probe / client list).
2. Sniffer emits **BeaconEvent** (MAC, RSSI, SSID, hostname, vendor, etc.).
3. **main.\_handle_beacon_event**: session → `upsert_device`, `reclassify_device`.
4. **detect_presence_changes** (grace period): compare current vs previous → list of (MAC, arrive|leave).
5. For each change: **evaluate_presence_change** (match rules by person/device, trigger type).
6. **dispatch_webhooks**: HTTP POST payloads to rule webhook URLs (SSRF-safe).

Optional: one swimlane “Sniffer”, one “App”, one “External (webhook)”.

---

## 3. Use cases / actors

**File:** `efferve-use-cases.excalidraw`

**Goal:** Who does what with the system.

**Suggested content:**

- **Actors:** User (admin), External system (webhook consumer), Sniffer backends (Ruckus, OPNsense, GL.iNet, monitor).
- **Use cases (User):**
  - Configure sniffers (setup wizard: test + save to .env).
  - View devices and presence (dashboard, device list, classification).
  - Manage people and assign devices (people page).
  - Define alert rules (webhook URL, trigger: arrive / leave / both, scope: person or device).
  - Toggle/delete rules.
- **Use cases (External system):**
  - Receive webhook on presence change (payload: event type, device, person if any).
- **Use cases (Sniffer backends):**
  - Report device observations (BeaconEvent) to the app.

Simple stick-figures + ovals for use cases and lines to actors.

---

## 4. Setup and configuration workflow

**File:** `efferve-setup-workflow.excalidraw`

**Goal:** How configuration is loaded and how the setup wizard fits in.

**Suggested content:**

- **Config sources:** `.env` file (EFFERVE\_\*), process environment (overrides .env).
- **Setup wizard (UI):** User fills Ruckus/OPNsense/GL.iNet (and optional poll/grace). Test buttons → test_connection (no persist). Save → **save_config** writes/merges into `.env` → **restart_sniffer**.
- **On startup:** **load_config** (env + .env) → **get_active_sniffer_modes** → \_create_sniffer per mode → sniffers started in lifespan.

One flow for “first-time setup”, one for “restart after save”.

---

## 5. Device classification (household filtering)

**File:** `efferve-classification.excalidraw`

**Goal:** How devices get classified and how that affects the UI.

**Suggested content:**

- **Inputs:** BeaconEvent stream (RSSI, frequency of sightings over time).
- **Classification:** Resident / Frequent visitor / Passerby (from registry/store logic).
- **UI:** Default filters show Resident + Frequent visitor; Passerby hidden or optional.
- Optional: short note on MAC randomization (OUI, behavior) if you want to document future handling.

---

## Checklist

- [x] **efferve-architecture.excalidraw** — high-level boxes and data flow.
- [x] **efferve-beacon-to-alert.excalidraw** — sequence from beacon to webhook.
- [x] **efferve-use-cases.excalidraw** — actors and use cases.
- [x] **efferve-setup-workflow.excalidraw** — config and setup wizard flow.
- [x] **efferve-classification.excalidraw** — device classification and UI.

After drawing, export PNG or SVG for README/handoffs if needed; keep `.excalidraw` as the editable source.
