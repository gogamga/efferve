# Diagrams (Excalidraw)

Architecture and workflow diagrams for Efferve are kept here as [Excalidraw](https://github.com/excalidraw/excalidraw) files and exports.

## How to use

**No install inside this repo.** The Efferve app stays JS-free (Jinja2 + HTMX). Use Excalidraw externally:

1. **Web:** Open [excalidraw.com](https://excalidraw.com), create or edit a diagram, then **File → Save to disk** (`.excalidraw`) or **Export → PNG/SVG** and save into this folder.
2. **Desktop (optional):** Use the [Excalidraw desktop app](https://github.com/excalidraw/excalidraw/releases) if you prefer; same workflow — save or export into `docs/diagrams/`.

## Conventions

- **Source:** Prefer saving as `.excalidraw` (JSON) so others can open and edit in Excalidraw.
- **Exports:** Commit PNG or SVG when you need a stable image (e.g. for README or handoffs).
- **Naming:** e.g. `efferve-architecture.excalidraw`, `efferve-presence-flow.excalidraw`, `use-cases-alerts.excalidraw`.

## Generated diagrams

The following files were generated and can be opened in [excalidraw.com](https://excalidraw.com) (File → Open) for viewing or editing:

| File                                 | Content                                                                                                           |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `efferve-architecture.excalidraw`    | Data sources → Core app → Outputs (blocks + arrows)                                                               |
| `efferve-beacon-to-alert.excalidraw` | Six-step flow: Sniffer → BeaconEvent → upsert/reclassify → detect_presence_changes → evaluate → dispatch_webhooks |
| `efferve-use-cases.excalidraw`       | Actors (User, External system, Sniffer backends) and use-case boxes                                               |
| `efferve-setup-workflow.excalidraw`  | Config sources, Setup wizard (test/save/restart), On startup                                                      |
| `efferve-classification.excalidraw`  | BeaconEvent stream → Classification (Resident / Frequent visitor / Passerby) → UI default filter                  |

To regenerate: `python3 docs/diagrams/generate_diagrams.py` (from repo root).

## Plan

See [PLAN.md](./PLAN.md) for the diagram plan and checklist.

## ASCII versions

For GitHub-rendered plain text diagrams, see [ASCII_DIAGRAMS.md](./ASCII_DIAGRAMS.md).
