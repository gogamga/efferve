# Efferve ASCII Diagrams

These are plain ASCII versions of the current architecture/workflow diagrams.
They are GitHub-friendly and render in markdown code fences.

## 1) System Architecture (High Level)

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

Flow:
  Sniffers -> BeaconEvent -> upsert/reclassify -> presence change detect -> evaluate rules -> dispatch webhooks
```

## 2) Data Flow: Beacon -> Alert

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

## 3) Use Cases / Actors

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

## 4) Setup + Configuration Workflow

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

## 5) Device Classification (Household Filtering)

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
