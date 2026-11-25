# Genealogy - Versions

## Current Version: Whelp

**Version:** Whelp (`v1.0`)  
**Baseline:** Forked from abyssonym's *Breath of Fire 3 "The Vast and the Violent"* (`v3.0`)

### Functionality

- **Structured Randomness & Named Presets:** Added curated `standard`, `fiesta`, and `chaos` presets (`data/presets.json`), a full `--flag` CLI option layer (with clean defaults < preset < code < CLI precedence), and copyable Share Strings for reproducing exact runs.
- **Curated Class Modes & Growth Compiler:** Built the `genepool` class engine supporting 12 handcrafted **Archetypes** (`--class-mode archetypes`) and intact **Vanilla Role Swap** (`--class-mode roleswap`), complete with Lv 1–99 stat/spell compilation, join-level stat normalization, and aligned equipment permissions.
- **Curated Master Kits:** Replaced scattershot Master rolls with thematically coherent Master Kits (`--master-kits`, `data/masters.json`) that respect PS1 menu text byte budgets (no `???` truncation), guarantee `Backhand` access, and prevent collisions with character level-up skills.
- **Progression-Tiered Dragon Genes:** Added Early/Mid/Late tiered gene shuffling (`tiered`), controlled cross-tier surprises (`tiered_bleed`, guaranteeing early core elements and keeping `Failure` out of Early), and unrestricted shuffling (`flat`).
- **Anti-Softlock Guardrails:** Introduced three toggleable, data-driven safety pillars enabled by default — **Crash Blacklist** (filters unsafe/crash-prone enemy AI skills), **Encounter Tier Clamping** (bounds Early/Mid/Late enemy stat and resistance variance while protecting scripted fights), and **Weapon Accessibility** (ensures affordable early/mid weapons for every active party member in accessible shops) — with full intervention reporting in spoiler logs.
- **Pacing & Reward Multipliers:** Added safe battle EXP (`--exp-mult`), Zenny (`--zenny-mult`), and item drop rate (`--drop-mult`) scaling (plus flag-string shortcuts like `exp2x`, `zenny2x`, `turbo10x`).
- **Zero-Server Companion Wiki (`wiki.html`):** Added automatic per-run **Seed Manifest** export and per-ROM **Vanilla Baseline** caching powering a zero-dependency `file://` SPA with multi-run switching, Spoiler Overview, 10 compendium categories with vanilla diffs, slide-over Inspector Drawer & Full-Page dossiers, `Ctrl+K` Command Palette, per-run Checklist (`localStorage` + JSON backup), Ryu/Teepo themes, and `--open-wiki`.
- **Upstream PS1 Bug Fixes & Engineering Foundation:** Fixed upstream `LevelObject` stat-growth nibble packing, join-level `relevel_stats()` off-by-two math, `BaseStatsObject` cleanup bugs, prologue character (`Teepo`/`Whelp`) protection, and Redump Track 2 `.cue` preservation; added verified ROM table references (`docs/rom-tables.md`), domain docs/ADRs, modernized `README.md`, and a zero-ROM unit test suite.
