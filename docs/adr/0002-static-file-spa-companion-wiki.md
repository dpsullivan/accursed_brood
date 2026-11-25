# 0002: Zero-Server Static SPA for the Companion Wiki

## Status
accepted

## Context & Decision
To avoid running and maintaining a local HTTP server (port conflicts, process lifecycle, platform quirks), the Companion Wiki will be delivered as a single reusable static HTML/CSS/JS SPA opened directly via `file://` with `#/` hash routing. Because browsers block `fetch()` across `file://` origins, `randomizer.py` will maintain a lightweight local `<script>` seed registry in `output/seeds/` so the app auto-discovers all local Seed Manifests in one tab, supplemented by a drag-and-drop / file-picker fallback for loading external manifests.

## Considered Options
- **Local Python web server**: Rejected as unnecessary operational surface area and a vector for local environment issues.
- **Per-seed multi-page static HTML folder**: Rejected due to file sprawl across seeds, lack of a unified seed switcher, and Firefox `file://` per-path `localStorage` isolation breaking a shared Checklist.
- **Per-seed single-file HTML bundle**: Deferred; because it shares the same static SPA core, a standalone shareable HTML export can be added later without architectural rework.

## Consequences
- Frontend code must run cleanly under `file://` (classic `<script>` loading or a single bundled asset, no raw ES module `import` over `file://`).
- Upgrading the Companion Wiki UI automatically improves the view for all previously generated Seed Manifests without regenerating them.
- Checklist state lives in browser `localStorage` under the single `file://` page, keyed by unique run ID, with JSON export/import for backup.
