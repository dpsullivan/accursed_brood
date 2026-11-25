# 0001: Seed Manifest and Local Vanilla Baseline

## Status
accepted

## Context & Decision
The plain-text Spoiler Log (`bof3r_spoiler_<seed>.txt`) omits unmodified vanilla values for most entities and lacks structured cross-reference fields (such as abilities and equipment). Instead of parsing Spoiler Logs, every randomizer run will emit a structured Seed Manifest under `output/seeds/` alongside the legacy Spoiler Log, and will automatically extract and cache a local Vanilla Baseline from `old_data` per ROM revision (`BOF3_1.0` / `BOF3_1.1`) under `output/`.

## Considered Options
- **Parse existing `.txt` Spoiler Logs**: Rejected because it is brittle, lacks vanilla baselines for diffs, and omits fields not printed in the text spoiler.
- **Commit a pre-extracted Vanilla Baseline into git**: Rejected to keep ROM-derived game tables out of version control and ensure an exact match against whichever ROM revision (1.0 or 1.1) the player runs.

## Consequences
- Previously generated runs must be re-run (same seed + share string) to appear in the Companion Wiki.
- The Companion Wiki requires at least one randomizer run on the local machine to populate the cached Vanilla Baseline for that ROM revision.
