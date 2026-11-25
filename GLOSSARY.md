# Accursed Brood

A Breath of Fire III randomizer and companion reference suite that transforms vanilla game data into randomized runs and presents per-seed changes to players.

## Language

### Randomizer Runs

**Seed**:
The numeric value that initializes the randomizer's pseudo-random generator for a run.

**Run**:
A specific invocation of the randomizer uniquely identified by its Seed, randomizer version, ROM revision, and option set.
_Avoid_: Seed file, build

### Companion Wiki

**Companion Wiki**:
The local web application players use to inspect a randomized run and compare it against the unmodified game.
_Avoid_: Internal wiki, user wiki

**Vanilla Baseline**:
The unmodified Breath of Fire III game dataset used as the reference point when displaying what a seed changed.
_Avoid_: Base model, base game

**Seed Manifest**:
The structured per-seed record emitted by a randomizer run and consumed by the Companion Wiki.
_Avoid_: Debug log, audit log, randomizer log

**Spoiler Log**:
The human-readable plain-text summary produced for a seed alongside the Seed Manifest.

**Spoiler Overview**:
The high-level landing view in the Companion Wiki summarizing all differences in a selected seed at a glance.

**Checklist**:
A dedicated Companion Wiki view, separate from the Spoiler Overview, where players track per-seed completion across relevant categories.
