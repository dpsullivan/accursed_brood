"""Deterministic 1-99 Growth Compiler, join-level normalizer, and Lv 40 grader.

Separates how classes are authored (``base_lv1``, decimal ``growth_per_level``,
and ``curve`` shape) from how the PS1 Breath of Fire III ROM stores them
(99-row integer delta tables in ``GAME.EMI`` + join-level totals in
``START.EMI`` / ``STATUS.EMI``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from .schema import (
    CURVE_SHAPES,
    MAX_SPELLS_PER_CATEGORY,
    SKILL_CATEGORIES,
    STAT_MAX_GAIN,
    STATS,
    ClassDefinition,
    SpellLearn,
)

NUM_LEVEL_ROWS = 99  # row 0 = Lv 1 (zero stat delta), rows 1..98 = Lv 2..99 deltas
NUM_LEVEL_UPS = 98

# Lv 40 (typical Myria endgame) S-F letter grade thresholds calibrated to vanilla BoF3.
# Each tuple is (S, A, B, C, D); values strictly below D receive "F".
LV40_GRADE_THRESHOLDS: Dict[str, Tuple[int, int, int, int, int]] = {
    "hp": (280, 240, 205, 175, 145),
    "ap": (200, 160, 125, 90, 55),
    "pwr": (165, 145, 125, 100, 75),
    "def": (125, 105, 90, 75, 60),
    "agl": (65, 55, 46, 38, 28),
    "int": (165, 140, 115, 85, 55),
}

GRADE_LABELS: Tuple[str, ...] = ("S", "A", "B", "C", "D", "F")


@dataclass(frozen=True)
class LevelRow:
    """Single compiled row corresponding to ``LevelObject`` row ``level - 1``."""

    level: int  # 1..99
    hp: int
    ap: int
    pwr: int
    dfn: int
    agi: int
    intel: int
    ability: int = 0

    def stat(self, key: str) -> int:
        if key == "hp":
            return self.hp
        if key == "ap":
            return self.ap
        if key == "pwr":
            return self.pwr
        if key in ("def", "dfn"):
            return self.dfn
        if key in ("agl", "agi"):
            return self.agi
        if key in ("int", "intel"):
            return self.intel
        raise KeyError(f"Unknown stat key: {key!r}")


@dataclass(frozen=True)
class NormalizedStart:
    """Starting stats and starting spells for a character joining at level ``L``."""

    join_level: int
    stats: Dict[str, int]
    starting_spells: Dict[str, Tuple[int, ...]]


@dataclass(frozen=True)
class CompiledClass:
    """Complete compiled output for a ``ClassDefinition``."""

    definition: ClassDefinition
    rows: Tuple[LevelRow, ...]  # length 99; rows[0] has 0 stat gains
    totals_lv1: Dict[str, int]
    totals_lv40: Dict[str, int]
    totals_lv99: Dict[str, int]
    grades_lv40: Dict[str, str]

    def totals_at(self, level: int) -> Dict[str, int]:
        """Exact stat totals at ``level`` (1..99) without Masters."""
        if not (1 <= level <= NUM_LEVEL_ROWS):
            raise ValueError(f"Level must be in 1..99, got {level}.")
        return {
            stat: self.totals_lv1[stat]
            + sum(self.rows[k].stat(stat) for k in range(1, level))
            for stat in STATS
        }


def curve_weights(curve: str, steps: int = NUM_LEVEL_UPS) -> List[float]:
    """Return normalized per-step curve weights whose mean is strictly ``1.0``.

    - ``linear``: constant 1.0 across Lv 2..99.
    - ``frontloaded``: 1.45 at Lv 2 tapering linearly to 0.55 at Lv 99 (higher
      Lv 40 Myria power while preserving exact 1..99 total growth).
    - ``late_bloomer``: 0.55 at Lv 2 rising linearly to 1.45 at Lv 99 (leaner
      early game, explosive late-game scaling).
    """
    if curve not in CURVE_SHAPES:
        raise ValueError(f"Unknown curve {curve!r}; expected one of {CURVE_SHAPES}.")
    if steps <= 0:
        raise ValueError("steps must be positive.")
    if steps == 1 or curve == "linear":
        return [1.0] * steps

    raw: List[float] = []
    for i in range(steps):
        t = i / (steps - 1)  # 0.0 -> 1.0
        if curve == "frontloaded":
            raw.append(1.45 - 0.90 * t)
        elif curve == "late_bloomer":
            raw.append(0.55 + 0.90 * t)
    # Normalize so sum(weights) == steps (exact conservation over 98 level-ups).
    scale = steps / sum(raw)
    return [w * scale for w in raw]


def compile_stat_gains(
    growth_per_level: float,
    curve: str,
    max_gain: int,
    steps: int = NUM_LEVEL_UPS,
) -> List[int]:
    """Compile a decimal per-level growth rate into ``steps + 1`` integer deltas.

    Index ``0`` (Level 1) is always ``0`` to match ``GAME.EMI``'s ``LevelObject``
    format. Indices ``1..steps`` (Levels 2..99) are produced via deterministic
    error-accumulator math so there is zero rounding drift across 98 level-ups
    and every integer obeys ``0 <= gain <= max_gain``.
    """
    if growth_per_level < 0.0 or growth_per_level > max_gain:
        raise ValueError(
            f"growth_per_level={growth_per_level} out of bounds [0, {max_gain}]."
        )

    weights = curve_weights(curve, steps=steps)
    gains = [0]
    accumulator = 0.0
    eps = 1e-12

    for w in weights:
        accumulator += growth_per_level * w
        gain = int(math.floor(accumulator + 0.5 + eps))
        if gain < 0:
            gain = 0
        elif gain > max_gain:
            gain = max_gain
        accumulator -= gain
        gains.append(gain)

    return gains


def grade_stat_lv40(stat: str, value: int) -> str:
    """Return an ``S``-``F`` letter grade for a stat total at Level 40."""
    thresholds = LV40_GRADE_THRESHOLDS[stat]
    for label, cutoff in zip(GRADE_LABELS, thresholds):
        if value >= cutoff:
            return label
    return "F"


def grade_totals_lv40(totals_lv40: Mapping[str, int]) -> Dict[str, str]:
    """Grade all 6 stats at Level 40."""
    return {stat: grade_stat_lv40(stat, int(totals_lv40[stat])) for stat in STATS}


def compile_class(definition: ClassDefinition) -> CompiledClass:
    """Compile a ``ClassDefinition`` into an exact 99-row PS1 growth table."""
    per_stat: Dict[str, List[int]] = {
        stat: compile_stat_gains(
            definition.growth_per_level[stat],
            definition.curve,
            max_gain=STAT_MAX_GAIN[stat],
        )
        for stat in STATS
    }

    spell_by_level: Dict[int, int] = {
        sp.level: sp.ability_id for sp in definition.spells
    }

    rows: List[LevelRow] = []
    for idx in range(NUM_LEVEL_ROWS):
        lvl = idx + 1
        rows.append(
            LevelRow(
                level=lvl,
                hp=per_stat["hp"][idx],
                ap=per_stat["ap"][idx],
                pwr=per_stat["pwr"][idx],
                dfn=per_stat["def"][idx],
                agi=per_stat["agl"][idx],
                intel=per_stat["int"][idx],
                ability=spell_by_level.get(lvl, 0),
            )
        )

    totals_lv1 = {stat: int(definition.base_lv1[stat]) for stat in STATS}
    totals_lv40 = {
        stat: totals_lv1[stat] + sum(per_stat[stat][1:40]) for stat in STATS
    }
    totals_lv99 = {
        stat: totals_lv1[stat] + sum(per_stat[stat][1:99]) for stat in STATS
    }

    return CompiledClass(
        definition=definition,
        rows=tuple(rows),
        totals_lv1=totals_lv1,
        totals_lv40=totals_lv40,
        totals_lv99=totals_lv99,
        grades_lv40=grade_totals_lv40(totals_lv40),
    )


def normalize_for_join_level(
    compiled: CompiledClass, join_level: int
) -> NormalizedStart:
    """Simulate leveling ``compiled`` from Lv 1 to ``join_level`` without Masters.

    Returns the exact starting stat totals and starting spell buckets to write
    into ``START.EMI`` and ``STATUS.EMI`` for a character joining at level ``L``.
    """
    if not (1 <= join_level <= NUM_LEVEL_ROWS):
        raise ValueError(f"join_level must be in 1..99, got {join_level}.")

    stats = compiled.totals_at(join_level)

    buckets: Dict[str, List[int]] = {cat: [] for cat in SKILL_CATEGORIES}
    for sp in compiled.definition.spells:
        if sp.level <= join_level:
            buckets[sp.category].append(sp.ability_id)
            if len(buckets[sp.category]) > MAX_SPELLS_PER_CATEGORY:
                raise ValueError(
                    f"Class {compiled.definition.id!r} exceeds {MAX_SPELLS_PER_CATEGORY} "
                    f"starting spells in bucket {sp.category!r} by Lv {join_level}."
                )

    return NormalizedStart(
        join_level=join_level,
        stats=stats,
        starting_spells={cat: tuple(ids) for cat, ids in buckets.items()},
    )
