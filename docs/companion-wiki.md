# Companion Wiki — Standards & Architecture Guide

This document records the durable architecture, data contracts, UI standards, and verification workflow for the Accursed Brood **Companion Wiki**.

All terminology follows [GLOSSARY.md](../GLOSSARY.md). Foundational architectural decisions are recorded in:
- [ADR 0001: Seed Manifest and Local Vanilla Baseline](adr/0001-seed-manifest-and-vanilla-baseline.md)
- [ADR 0002: Zero-Server Static SPA for the Companion Wiki](adr/0002-static-file-spa-companion-wiki.md)

---

## 1. Zero-Server `file://` Constraints

The Companion Wiki is a zero-build, zero-server static single-page application designed to open directly in any desktop browser over `file://` (per ADR 0002):

- **Entry point & directory layout**:
  - `wiki.html` lives at the repository root so `output/` remains a strict child path. Chrome, Edge, and Firefox allow classic `<script>` loading of relative child paths under `file://`.
  - Static frontend assets live under `wiki/` (`styles.css`, `data.js`, `render.js`, `app.js`).
  - Local generated data lives under gitignored `output/` (`output/vanilla_baseline_<rom_version>.{json,js}`, `output/seeds/<run_id>.{json,js}`, `output/seeds/registry.js`).
- **Strict zero-dependency frontend rules**:
  - Use classic `<script>` tags only. Never use `<script type="module">` or ES `import`/`export` syntax (blocked by browser CORS rules over `file://`).
  - Never use `fetch()` or `XMLHttpRequest` for local files. Auto-discovery uses classic `<script>` wrappers calling `window.__ACCURSED_BROOD_WIKI__`.
  - No Node.js, npm, bundler, framework runtime, or external CDN fonts/scripts.
  - All in-app navigation uses `#/` hash routes (`#/overview`, `#/monsters/<id>`, `#/checklist`, etc.) so browser back/forward and reloads work over `file://`.
- **Fallback & resilience**:
  - When `output/seeds/registry.js` is missing or empty, the Companion Wiki renders the **Empty State** with CLI usage instructions and drag-and-drop / file-picker loading for any `.json` **Seed Manifest**.
  - Missing or unreadable per-Run script files are skipped gracefully without crashing the UI.
  - Loading an external Seed Manifest whose `rom_version` has no locally cached **Vanilla Baseline** enters **Seed-Only Mode**: an informative warning banner is displayed, all active Run values remain inspectable, and Vanilla Baseline diff columns/tags degrade cleanly.
- **CLI integration**:
  - Every Run prints the absolute paths to both the emitted Seed Manifest and `wiki.html` after generating the legacy plain-text **Spoiler Log**.
  - `--open-wiki` (disabled by default; override with `--no-open-wiki`) opens `wiki.html` in the system default browser upon completion.

---

## 2. Seed Manifest & Vanilla Baseline Contract

Backend export is owned by `genepool/companion_wiki.py` (single top-level entry point `export_companion_wiki_run`), invoked automatically from `randomizer.py` after `write_spoiler(...)` without modifying legacy Spoiler Log output.

### Versioning & Deterministic Run Identity
- Both **Seed Manifest** and **Vanilla Baseline** documents carry `"schema_version": 1` and `"rom_version"` (`"BOF3_1.0"` or `"BOF3_1.1"`).
- Each Run's deterministic `run_id` has the form `run_<seed>_<preset>_v<version>_<opt_hash>`, where `<opt_hash>` is an 8-character SHA-256 digest of the canonical option set (ROM revision, randomizer version, preset, normalized flags, randomness, difficulty, class mode, master kits, gene mode, EXP/Zenny/Drop multipliers, guardrail flags, and activated codes).
- Re-running the exact same Seed and option set overwrites that Run's Seed Manifest in place without duplicating registry entries or invalidating **Checklist** progress stored under `run_id`. Changing any option, preset, or ROM revision produces a distinct `run_id`.

### Per-ROM-Revision Vanilla Baseline Caching
- Per ADR 0001, unmodified ROM values are extracted from each `TableObject`'s retained `old_data` during a local Run and cached per ROM revision under `output/vanilla_baseline_<rom_version>.json` (+ `.js` classic script wrapper).
- Never parse plain-text Spoiler Logs and never commit ROM-derived Vanilla Baseline tables into git.

### Auto-Healing Local Script Registry
- On every Run, `rebuild_seed_registry()` scans `output/seeds/*.json`, sorts valid Runs newest-first, removes orphaned `.js` wrappers whose `.json` was manually deleted, discovers cached Vanilla Baselines, and regenerates `output/seeds/registry.js`.

### ROM Normalization Guarantees (Data Layer)
All raw PS1 ROM cleanup happens in `genepool/companion_wiki.py` so frontend rendering remains deterministic and simple:
1. **Dummy-slot filtering**: Blank/dummy ROM slots (`000 LV 0` monsters, `Nothing` / `Noting` / empty abilities and items) are stripped during export.
2. **Multi-slot monster grouping**: Same-name canonical monster slots (e.g., `Ammonite`, `ToxicMan`, `Nue`) are grouped into a single logical Monster record with an ordered `variants` list preserving each ROM slot's hex code, level, stats, resistances, loot, and abilities.
3. **Duplicate ability merging**: Level-up and examine/Master ROM slots sharing a canonical ability name are merged into one canonical Ability record listing its `merged_slots` and `merged_slot_ids`.
4. **Elemental & status resistance decoding**: Raw `0–7` resistance values (Fire, Frost, Thunder, Earth, Wind, Holy, Psionic, Status, Death) are decoded into structured objects:
   - `0`: `Very Weak` (`200%`), `1`: `Weak` (`150%`), `2`: `Normal` (`100%`), `3`: `Resist` (`50%`), `4`: `Strong Resist` (`25%`), `5`: `Null` (`0%`), `6`: `Absorb` (`ABS`), `7`: `Immune` (`IMM`).
5. **Progression tier & area enrichment**: Every Monster and Chest carries its progression tier (`Early`, `Mid`, `Late`, or `Protected`) and EMI area names from `data/encounter_tiers.json` and `tables/names_areas.txt`.
6. **Class catalog reuse**: The Classes catalog reuses `genepool.wiki_export.build_wiki_payload` so archetype totals and Lv40 grades remain synchronized with `data/classes.json`.
7. **Mutable-only diff policy**: Immutable combat properties (e.g., Equipment ATK/DEF/WT) render cleanly without diff clutter, while mutable fields (character stats/spells, Master mods/skills, monster stats/resistances/loot/abilities, equipment equipability bitmasks & prices, Dragon Gene pedestals, Shops, Manillos, Chests) diff against the Vanilla Baseline.

---

## 3. UI Design Standards (`Brood Chronicle`)

The Companion Wiki implements the approved **Brood Chronicle** layout (selected from Variant D in `prototype/wiki-ui@2e5c91d`):

### Layout & Interaction Conventions
- **Sticky Two-Tier Top Command Header**:
  - Row 1: Brand crest, Run switcher, `Load JSON` button, global `Ctrl+K` Command Palette trigger, `☀ Ryu | ☾ Teepo` segmented theme switch, and live Checklist gauge pill.
  - Row 2: Horizontal Breath of Fire III–framed category command tabs (`Overview` + all 10 compendium categories) with a luminous active top-edge beam. No heavy left sidebar.
- **BoF3 Menu Framing**: Double-bordered windows (`2px` outer bevel + `1px` inset highlight), serif plaque headers with `❖` filigree markers, tabular monospace numerics, and zero horizontal overflow.
- **Spoiler Overview**: Dense 12-column responsive bento layout featuring the Run Telemetry Strip (with one-click copyable Share String), Party & Assigned Classes matrix (numbered BoF3 party slot badges + inline `+Δ / v###` diffs + Lv40 S–F rank medallions), Guardrails Highlights (KPI counts, Weapon Accessibility adjustments, expandable encounter clamp feed), 3-column tiered Dragon Genes panel, and Curated Masters summary.
- **Slide-Over Inspector Drawer + `Full Page ↗` Dossier**: Clicking rows in Overview or compendium lists opens a persistent right-side Inspector Drawer (preserving scroll and filters) featuring dual-layer stat bars (active Run fill + Vanilla Baseline ghost tick), color-coded resistance matrices, reverse cross-links, and inline Checklist checkboxes. Clicking `Full Page ↗` expands any entry into a full-width editorial dossier with side-by-side Vanilla vs. Active Run split tables.
- **Dedicated Per-Run Checklist (`#/checklist`)**: Separate from Spoiler Overview, structured as a sticky left Progress Ledger + 4 collapsible sections (Dragon Genes, Masters & Master Skills, Learnable Monster Skills, Chests). Completion state persists in `localStorage` under `accursed_brood_wiki_checklist_v1:<run_id>` with JSON Export/Import backup.

### Semantic Color Token Palettes

#### Light Mode — Ryu (Default, `body.brood-chronicle`)
| Role | Hex / Value | Usage |
| --- | --- | --- |
| Parchment Canvas | `#f3efe4` | Page background |
| Alabaster Window | `#fcfbf7` | BoF3 framed cards & drawers |
| Olive-Brass Frame | `#8f8b70` / `#a8a287` | Outer borders & tab frames |
| Plaque Header | `#eee9d8` → `#e1dbc4` | Window title bars |
| Leather Umber Ink | `#2a1f18` / `#655849` | Primary / muted copy |
| Ryu Dragon Cerulean | `#1589c2` / `#32bde8` | Active controls, links, stat bar fills |
| Scarf Vermilion / Crimson | `#d9583b` / `#9e2a2b` | Brand title, S-rank, boss badges, vanilla ticks |
| Tunic Lavender | `#efebf8` / `#4f3d7a` | Flags, ability category tags, Protected tier |
| Steel Mist | `#e5eef2` / `#36505e` | Version/ROM badges, neutral metadata |
| Olive Moss | `#256435` / `#e4f4e8` | Positive stat deltas, Early tier, learnable skills |
| Brass Hilt | `#9e8624` / `#f8efd2` | Filigree markers, Guardrail badges, Mid tier |

#### Dark Mode — Teepo / Dragon Lord (`body.brood-chronicle.theme-teepo`)
| Role | Hex / Value | Usage |
| --- | --- | --- |
| Abyssal Indigo Canvas | `#100c1a` | Page background (`color-scheme: dark`) |
| Window / Recessed | `#1a1429` / `#140f21` | Framed windows, drawers, recessed cards |
| Horn-Silver Bevel | `#6b6887` / `#c7cde0` | Outer borders & specular inner highlights |
| Moon-Pearl Ink | `#ece8f6` / `#a59dc0` | Primary / muted copy |
| Teepo Lilac / Amethyst | `#c594f5` / `#9e5ce6` | Links, active pills, stat bar start |
| Dragon Lord Wing Magenta | `#d94bb5` | Brand crest, stat bar end, active beam |
| Coral Underbelly | `#e87863` / `#f0a48f` | Brand title warmth, negative deltas, Checklist gauge |
| Emerald Eye | `#47c97c` / `#6be09a` | Positive deltas, Early tier, learnable skills |
| Golden Claws | `#e5b842` | Filigree, Mid tier, Guardrails, Vanilla ghost ticks |

Theme preference persists in `localStorage` under `accursed_brood_wiki_theme_v1`.

---

## 4. Testing & `file://` Verification Workflow

### When to Run
Run the Companion Wiki verification checks **on demand**:
- Whenever modifying `genepool/companion_wiki.py`, `genepool/options.py` (`--open-wiki`), `wiki.html`, or `wiki/*`.
- Before opening a PR or cutting a release.
- Unrelated randomizer core edits do not require re-running browser checks.

### Seam 1 — Zero-ROM Backend Exporter & CLI Unit Tests
Run with standard library Python (no ROM or third-party dependencies required):

```bash
python -m unittest tests/test_companion_wiki.py tests/test_options.py -v
```

For full regression verification before a PR/release:

```bash
python -m unittest discover -s tests
```

### Seam 2 — Zero-Dependency `file://` Browser Verification Checklist
Open `wiki.html` directly over `file://` in a desktop browser and confirm zero console/page errors across:
1. **Empty State**: With no `output/seeds/registry.js`, Empty State renders cleanly with dropzone and CLI instructions.
2. **Auto-Discovery & Run Switching**: After running `randomizer.py` at least twice, both Runs appear in the header selector and switch cleanly in one tab.
3. **Spoiler Overview**: Run Telemetry strip + Copy Share String, Party & Assigned Classes, Guardrails Highlights (`Show more`), 3-column Dragon Genes, Curated Masters, and zero horizontal overflow on desktop & ~1024px viewports.
4. **All 10 Categories & Normalization**: Masters, Characters & Classes (`Active Party` + `Classes Catalog`), Dragon Genes (`Changed only`), Monsters (tier pills, `Changed only`, grouped multi-slot variants, dual-layer stat bars, decoded resistances), Abilities (merged ROM slots + reverse cross-links), Equipment & Items (static stats + mutable diffs + reverse cross-links), Shops, Manillos, Chests (`Changed only`), and Guardrails.
5. **Inspector Drawer & `Full Page ↗`**: Clicking rows opens the sticky right drawer without losing scroll; `Full Page ↗` renders side-by-side Vanilla vs. Active Run split tables.
6. **`Ctrl+K` Command Palette**: Searches across all 10 categories, jumps directly to hits, and closes cleanly on `Escape`.
7. **Theme Toggle**: `☀ Ryu` / `☾ Teepo` switches cleanly and persists across reload.
8. **Checklist & Backup**: Checking items updates section bars, Progress Ledger, and header pill; inline checkboxes sync; `Hide completed` filters cleanly; state persists in `localStorage` isolated per `run_id`; JSON Export/Import validates malformed JSON and restores valid backups.
9. **Seed-Only Mode**: Dropping an external `.json` Seed Manifest for an uncached `rom_version` opens cleanly with the Seed-Only Mode banner and hides Vanilla diff columns without errors.
