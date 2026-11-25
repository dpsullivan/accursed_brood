# Accursed Brood

**Accursed Brood** is a structured randomizer and Companion Wiki suite for **Breath of Fire III** (US PlayStation 1), forked from abyssonym's *The Vast and the Violent* (`vast_violence`).

It pairs classic full-game randomization with curated class archetypes, coherent Master Kits, progression-tiered Dragon Genes, anti-softlock guardrails, named presets with copyable share strings, and a zero-server **Companion Wiki** (`wiki.html`) for browsing every change against the unmodified game.

---

## Highlights

- **Named Presets & Share Strings** — Jump straight into `standard`, `fiesta`, or `chaos` runs, or customize every knob and share a single reproducible CLI string.
- **Curated Class Modes** — Assign 12 handcrafted **Archetypes** (`archetypes`) or shuffle intact vanilla party kits (**Vanilla Role Swap**, `roleswap`) with properly normalized join-level stats, spells, and equipment permissions.
- **Curated Master Kits** — Replaces scattershot Master stat/skill rolls with thematically coherent kits that fit PS1 menu byte budgets cleanly, guarantee `Backhand` access, and avoid level-up skill collisions.
- **Progression-Tiered Dragon Genes** — Keep Early/Mid/Late gene pacing intact (`tiered`), allow controlled cross-tier surprises (`tiered_bleed`), or shuffle all 17 locations freely (`flat`).
- **Anti-Softlock Guardrails** — Three data-driven safety pillars enabled by default:
  - **Crash Blacklist** (`--crash-guard`): blocks crash-prone, dragon-only, and incompatible-animation skills from enemy AI pools.
  - **Encounter Tier Clamping** (`--tier-clamp`): bounds Early/Mid/Late monster stat and resistance variance while protecting scripted encounters.
  - **Weapon Accessibility** (`--weapon-guard`): guarantees affordable early- and mid-tier weapons for every active party member in accessible shops.
- **Zero-Server Companion Wiki (`wiki.html`)** — Every run automatically emits a structured Seed Manifest and updates the local wiki registry so you can inspect diffs, search across 10 compendium categories, and track progress in a per-run Checklist directly in your browser over `file://`.
- **PS1 ROM & Upstream Fixes** — Fixes upstream `LevelObject` stat-growth packing, join-level stat normalization, `BaseStatsObject` cleanup, prologue character protection, and sibling Redump Track 2 `.cue` generation.

---

## Requirements & Supported ROMs

- **Python 3.8+** (standard library only — no third-party packages or Node.js required).
- If cloning from git, initialize the `randomtools` submodule:
  ```bash
  git clone --recurse-submodules https://github.com/dpsullivan/accursed_brood.git
  ```
  *(Or run `git submodule update --init --recursive` inside an existing clone.)*

Compatible with the following US PlayStation 1 Track 1 `.bin` ROM images:

| Label | Codename | Track 1 `.bin` MD5 |
| --- | --- | --- |
| `BOF3_1.0` | Vodka Shot | `226771993e29ca5c8e6e2c094c40e8d2` |
| `BOF3_1.1` | Ginseng | `9dd9a7c934b8b59d0ce76b0f25d18176` |

---

## Quick Start

### Recommended: Run with a Preset

```bash
# Standard curated run (Archetypes, Master Kits, Tiered Genes, Guardrails ON)
python randomizer.py "Breath of Fire III (USA) (Track 1).bin" --preset standard

# Fiesta run (Archetypes, Master Kits, Tiered Bleed Genes, 2x EXP & Zenny) and open the Companion Wiki
python randomizer.py "Breath of Fire III (USA) (Track 1).bin" --preset fiesta --seed 424242 --open-wiki

# Chaos run (High-variance legacy shuffle, relaxed tier/weapon guardrails, crash guard ON)
python randomizer.py "Breath of Fire III (USA) (Track 1).bin" --preset chaos
```

### Interactive or Positional CLI Mode

Running `python randomizer.py` with no arguments (or only a ROM path) launches interactive prompts for ROM path, flags/codes, seed, randomness, and difficulty. You can also pass positional arguments directly:

```bash
python randomizer.py <rom.bin> [flags] [seed] [randomness] [difficulty] [options...]
```

- **`randomness`** (`0.0`–`1.0`, default `0.5`): Controls randomization variance. `0` changes almost nothing, `0.5` is the recommended balanced default, and `1.0` is extreme variance (e.g., endgame stats on early enemies).
- **`difficulty`** (`> 0`, default `1.0`): Custom enemy stat multiplier that scales with enemy level so later enemies feel the boost more strongly. `1.0` applies no boost; `2.0` allows the highest-level enemies to scale up to roughly double stats.

---

## Named Presets

Presets are defined in [data/presets.json](data/presets.json) and selected via `--preset <id>` (or their flag-string code equivalents). Any explicit CLI flag overrides the preset default.

| Preset | Flag Code | Flags | Randomness | Difficulty | Class Mode | Master Kits | Gene Mode | Crash / Tier / Weapon Guardrails | EXP / Zenny / Drop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `standard` | `standardrun` | `acegmnqst` | `0.5` | `1.0` | `archetypes` | On | `tiered` | On / On / On | `1x` / `1x` / `1x` |
| `fiesta` | `fiestarun` | `acegmnqst` | `0.5` | `1.0` | `archetypes` | On | `tiered_bleed` | On / On / On | `2x` / `2x` / `1x` |
| `chaos` | `wildrun` | `acegmnqst` | `0.85` | `1.0` | `legacy` | Off | `flat` | On / Off / Off | `1x` / `1x` / `1x` |

---

## Flags & CLI Reference

### Standard Randomizer Flags

Combine any subset of single-letter flags in the positional `flags` argument or via `--flags <letters>` (all flags: `acegmnqst`):

| Flag | Description |
| --- | --- |
| `a` | Randomize abilities |
| `c` | Randomize characters (replaced by curated classes when `--class-mode` is active) |
| `e` | Randomize enemies |
| `g` | Randomize dragon gene locations |
| `m` | Randomize masters (replaced by curated kits when `--master-kits` is active) |
| `n` | Randomize enemy abilities |
| `q` | Randomize equippable items |
| `s` | Randomize shops and trades |
| `t` | Randomize treasure |

### CLI Options

Options are merged in precedence order: **built-in defaults < `--preset` < flag-string codes < explicit CLI flags**.

| Option | Values / Aliases | Default | Description |
| --- | --- | --- | --- |
| `--preset` | `standard`, `fiesta`, `chaos` | *(none)* | Apply a named preset configuration. |
| `--flags` | Subset of `acegmnqst` + codes | `acegmnqst` | Override the positional flags string. |
| `--seed` | Integer `>= 0` | Random | Set a deterministic RNG seed. |
| `--randomness` | `0.0`–`1.0` (`--random-degree`) | `0.5` | Override randomization degree. |
| `--difficulty` | Float `> 0` | `1.0` | Override level-scaled enemy stat multiplier. |
| `--class-mode` | `archetypes`, `roleswap`, `legacy` | `legacy` | Select curated 12-Archetype assignment, intact Vanilla Role Swap, or legacy randomizer character mutation. |
| `--master-kits` / `--no-master-kits` | Boolean | Off | Toggle curated thematic Master Kits (`data/masters.json`). |
| `--gene-mode` | `flat`, `tiered`, `tiered_bleed` | `flat` | Dragon Gene shuffle mode: unrestricted (`flat`), strict Early/Mid/Late tiers (`tiered`), or tiers with light cross-tier bleed (`tiered_bleed`). |
| `--exp-mult` | Float `> 0` (`--exp`, `--xp`) | `1.0` | Multiply battle EXP rewards (clamped safely to uint16 max `65000`). |
| `--zenny-mult` | Float `> 0` (`--zenny`) | `1.0` | Multiply battle Zenny rewards (clamped safely to `65000`). |
| `--drop-mult` | Float `> 0` (`--drop`) | `1.0` | Scale enemy item drop rate exponents (up to 100%). |
| `--crash-guard` / `--no-crash-guard` | Boolean | On | Toggle the crash/animation skill blacklist guardrail. |
| `--tier-clamp` / `--no-tier-clamp` | Boolean | On | Toggle Early/Mid/Late monster stat & resistance clamping. |
| `--weapon-guard` / `--no-weapon-guard` | Boolean | On | Toggle shop weapon accessibility guarantees. |
| `--no-guardrails` | `--chaos`, `--true-chaos` | — | Disable both `--tier-clamp` and `--weapon-guard` (keeps `--crash-guard` enabled unless `--no-crash-guard` is also passed). |
| `--open-wiki` / `--no-open-wiki` | Boolean | Off | Automatically open `wiki.html` in your default browser after randomization completes. |

### Secret & Flag-String Codes

Codes can be embedded directly inside the `flags` string (or entered at the interactive flags prompt), e.g. `acegmnqstbluemagicianthinkwell`.

#### Classic Codes (from *The Vast and the Violent*)

| Code | Alias(es) | Effect |
| --- | --- | --- |
| `bluemagician` | `bluemage` | Make all skills (except level-up skills) examinable. |
| `equipanything` | — | Allow all characters to equip any weapon or armor. |
| `thinkwell` | — | Place a Fountain Pen in the chest near Rei's and Teepo's house. |
| `feyday` | `faeday` | Custom rename the 60 Faeries in your village via a text file (1 name per line, 5-character limit). |
| `abilonym` | — | Custom rename abilities via a text file based on [ability_names.txt](ability_names.txt) (12-character limit). |
| `easymodo` | — | Enable debug mode. |

#### Accursed Brood Feature, Preset, Reward & Guardrail Codes

| Category | Codes (and Aliases) | Effect |
| --- | --- | --- |
| **Presets** | `standardrun`, `fiestarun`, `wildrun` | Activate the `standard`, `fiesta`, or `chaos` preset via flags. |
| **Classes** | `archetypes` (`classes`), `roleswap` (`vanillaswap`) | Enable Archetypes or Vanilla Role Swap class mode. |
| **Masters** | `masterkits`, `legacymasters` | Enable or disable Curated Master Kits. |
| **Dragon Genes** | `tieredgenes`, `bleedgenes`, `flatgenes` | Select `tiered`, `tiered_bleed`, or `flat` Dragon Gene mode. |
| **Rewards** | `exp2x`/`xp2x`, `exp3x`/`xp3x`, `exp5x`/`xp5x`, `exp10x`/`xp10x`, `zenny2x`/`z2x`, `zenny3x`/`z3x`, `zenny5x`/`z5x`, `zenny10x`/`z10x`, `turbo10x`/`fast10x` | Apply EXP/Zenny multipliers (`turbo10x` sets both EXP and Zenny to 10×). |
| **Guardrails** | `notierclamp` (`noclamp`), `noweaponguard` (`noweapguard`), `chaos` (`truechaos`, `noguardrails`) | Relax tier clamping, weapon accessibility, or both. |

---

## Companion Wiki

Every randomizer run automatically generates a structured **Seed Manifest** under `output/seeds/` and updates `output/seeds/registry.js` (alongside a locally cached per-ROM **Vanilla Baseline** under `output/`).

To browse your runs, open **[wiki.html](wiki.html)** directly in any modern desktop browser (Chrome, Edge, or Firefox) — or pass `--open-wiki` on the command line. No local web server or build step is required.

Key Companion Wiki features:

- **Auto-Discovery & Multi-Run Switching** — Switch between all locally generated runs in a single tab, or drag-and-drop / load any external `.json` Seed Manifest (runs without a local Vanilla Baseline open cleanly in Seed-Only Mode).
- **Spoiler Overview** — At-a-glance Run Telemetry (with one-click copyable Share String), Party & Assigned Classes matrix with Lv40 grades and vanilla stat diffs, Guardrail Highlights, tiered Dragon Genes, and Curated Masters.
- **10 Compendium Categories** — Masters, Characters & Classes (Active Party + full Classes Catalog), Dragon Genes, Monsters (multi-slot grouping, tier filters, dual-layer stat bars, decoded elemental/status resistances), Abilities (merged ROM slots + reverse cross-links), Equipment & Items, Shops, Manillos, Chests, and Guardrails.
- **Slide-Over Inspector & Full-Page Dossiers** — Inspect any entry without losing scroll/filter state, or expand to a full side-by-side Vanilla vs. Active Run dossier.
- **Global Command Palette (`Ctrl+K`)** — Instant search across all categories.
- **Per-Run Checklist (`#/checklist`)** — Track Dragon Genes, Masters & Master Skills, Learnable Monster Skills, and Chests with `localStorage` persistence isolated per run plus JSON export/import backup.
- **Themes** — Switch between **Ryu** (parchment light mode) and **Teepo** (dark mode).

For architecture details, data contracts, and UI standards, see [docs/companion-wiki.md](docs/companion-wiki.md).

---

## Generated Outputs

Each run produces:

1. **Randomized ROM & `.cue` sheet** — Written alongside the input ROM (automatically preserving sibling Redump `(Track 2).bin` audio tracks when present).
2. **Legacy Plain-Text Spoiler Log** — `bof3r_spoiler_<seed>.txt` in the working directory.
3. **Companion Wiki Seed Manifest** — `output/seeds/run_<seed>_<preset>_v<version>_<hash>.json` (+ `.js` loader wrapper) and updated `output/seeds/registry.js`.
4. **Share String** — Printed to the terminal and displayed in the Companion Wiki; append it after `python randomizer.py "<rom.bin>" ` to reproduce the exact run.

---

## Development & Documentation

Run the zero-ROM unit test suite using standard library Python:

```bash
python -m unittest discover -s tests
```

Additional repository documentation:

- [GLOSSARY.md](GLOSSARY.md) — Canonical domain terminology.
- [docs/companion-wiki.md](docs/companion-wiki.md) — Companion Wiki architecture, data contract, and verification workflow.
- [docs/rom-tables.md](docs/rom-tables.md) — Verified US PS1 ROM table layouts, offsets, bitmasks, and upstream bug fixes.
- [docs/adr/](docs/adr/) — Architecture Decision Records.

---

## Credits & Acknowledgments

- **[abyssonym](https://github.com/abyssonym)** — Creator of **[Breath of Fire 3 "The Vast and the Violent" Randomizer](https://github.com/abyssonym/vast_violence)**, the original project **Accursed Brood** is forked from, and **[randomtools](https://github.com/abyssonym/randomtools)**, the table/ROM patching framework powering this project.
  - Website: <https://www.abyssonym.com/>
  - GitHub: <https://github.com/abyssonym>
  - Twitter/X: <https://twitter.com/abyssonym>
- **secondadvent** *(retained from the original Vast and the Violent README)* — Did much of the early reverse engineering on Breath of Fire III and graciously provided his documentation to abyssonym.
- **[raulcorreia7](https://github.com/raulcorreia7)** — Referenced for US `SLUS-00422` file format documentation, EMI archive specifications, and Breath of Fire III decompilation notes via **[bof3-wiki](https://raulcorreia7.github.io/bof3-wiki/)** and **[bof3-tools / bof3-decomp](https://github.com/raulcorreia7/bof3-tools)**.
