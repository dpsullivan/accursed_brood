"""Class assignment modes for Accursed Brood (Vanilla Role Swap & Premade Archetypes)."""

from __future__ import annotations

import random as stdlib_random
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .growth_compiler import (
    CompiledClass,
    LevelRow,
    NormalizedStart,
    compile_class,
    grade_totals_lv40,
    normalize_for_join_level,
)
from .schema import (
    MAX_SPELLS_PER_CATEGORY,
    PLAYABLE_CHARACTERS,
    SKILL_CATEGORIES,
    STATS,
    VANILLA_JOIN_LEVELS,
    ClassDefinition,
    EquipmentCatalog,
)

CLASS_MODES: Tuple[str, ...] = ("vanilla_swap", "archetypes")


@dataclass(frozen=True)
class VanillaCharacterSnapshot:
    """Captured vanilla character kit for intact Vanilla Role Swap."""

    char_key: str  # e.g. "ryu", "nina", ...
    join_level: int
    base_lv1: Dict[str, int]
    rows: Tuple[LevelRow, ...]  # length 99
    resistances: Tuple[int, ...]  # length 9
    combat_rates: Dict[str, int]  # surprise/reprisal/critical/evasion/accuracy
    spell_categories: Dict[int, str]  # ability_id -> category name

    def totals_at(self, level: int) -> Dict[str, int]:
        return {
            stat: self.base_lv1[stat]
            + sum(self.rows[k].stat(stat) for k in range(1, level))
            for stat in STATS
        }


@dataclass(frozen=True)
class ArchetypeAssignment:
    """Compiled assignment of a curated ``ClassDefinition`` to a party member."""

    char_key: str
    join_level: int
    compiled: CompiledClass
    normalized_start: NormalizedStart
    allowed_weapon_ids: Tuple[int, ...]
    allowed_armor_ids: Tuple[int, ...]
    allowed_accessory_ids: Tuple[int, ...]


@dataclass(frozen=True)
class VanillaSwapAssignment:
    """Assignment of a vanilla donor kit to a recipient party member."""

    char_key: str
    donor_key: str
    join_level: int
    rows: Tuple[LevelRow, ...]
    normalized_start: NormalizedStart
    resistances: Tuple[int, ...]
    combat_rates: Dict[str, int]
    totals_lv1: Dict[str, int]
    totals_lv40: Dict[str, int]
    totals_lv99: Dict[str, int]
    grades_lv40: Dict[str, str]


def _deranged_permutation(
    items: Sequence[str],
    rng: stdlib_random.Random,
    *,
    allow_identity: bool = False,
) -> List[str]:
    """Return a deterministic permutation of ``items`` (derangement by default)."""
    pool = list(items)
    if len(pool) <= 1 or allow_identity:
        rng.shuffle(pool)
        return pool

    for _ in range(1000):
        rng.shuffle(pool)
        if all(a != b for a, b in zip(items, pool)):
            return pool

    # Fallback guaranteed cyclic shift
    return pool[1:] + pool[:1]


def assign_vanilla_role_swap(
    snapshots: Mapping[str, VanillaCharacterSnapshot],
    rng: stdlib_random.Random,
    *,
    allow_identity: bool = False,
) -> Dict[str, VanillaSwapAssignment]:
    """Shuffle intact vanilla kits among the 6 permanent party members.

    Each recipient's starting stats and starting spells are normalized to the
    recipient's own vanilla join level ``L`` using the donor's 1..99 growth
    table (zero drift).
    """
    missing = [c for c in PLAYABLE_CHARACTERS if c not in snapshots]
    if missing:
        raise ValueError(f"Missing vanilla snapshots for: {missing}")

    donors = _deranged_permutation(
        PLAYABLE_CHARACTERS, rng, allow_identity=allow_identity
    )
    assignments: Dict[str, VanillaSwapAssignment] = {}

    for recipient_key, donor_key in zip(PLAYABLE_CHARACTERS, donors):
        recipient_snap = snapshots[recipient_key]
        donor_snap = snapshots[donor_key]
        join_level = recipient_snap.join_level

        start_stats = donor_snap.totals_at(join_level)
        buckets: Dict[str, List[int]] = {cat: [] for cat in SKILL_CATEGORIES}
        for row in donor_snap.rows[:join_level]:
            if row.ability > 0:
                cat = donor_snap.spell_categories.get(row.ability, "attack")
                if row.ability not in buckets[cat]:
                    if len(buckets[cat]) >= MAX_SPELLS_PER_CATEGORY:
                        raise ValueError(
                            f"Donor {donor_key!r} exceeds {MAX_SPELLS_PER_CATEGORY} spells "
                            f"in bucket {cat!r} by Lv {join_level}."
                        )
                    buckets[cat].append(row.ability)

        normalized = NormalizedStart(
            join_level=join_level,
            stats=start_stats,
            starting_spells={cat: tuple(ids) for cat, ids in buckets.items()},
        )
        t1 = donor_snap.totals_at(1)
        t40 = donor_snap.totals_at(40)
        t99 = donor_snap.totals_at(99)

        assignments[recipient_key] = VanillaSwapAssignment(
            char_key=recipient_key,
            donor_key=donor_key,
            join_level=join_level,
            rows=donor_snap.rows,
            normalized_start=normalized,
            resistances=donor_snap.resistances,
            combat_rates=dict(donor_snap.combat_rates),
            totals_lv1=t1,
            totals_lv40=t40,
            totals_lv99=t99,
            grades_lv40=grade_totals_lv40(t40),
        )

    return assignments


def assign_archetypes(
    classes: Sequence[ClassDefinition],
    equipment_catalog: EquipmentCatalog,
    rng: stdlib_random.Random,
    *,
    join_levels: Optional[Mapping[str, int]] = None,
    fixed_assignments: Optional[Mapping[str, str]] = None,
) -> Dict[str, ArchetypeAssignment]:
    """Assign 6 distinct curated archetypes to the 6 permanent party members."""
    if len(classes) < len(PLAYABLE_CHARACTERS):
        raise ValueError(
            f"Need at least {len(PLAYABLE_CHARACTERS)} curated classes, got {len(classes)}."
        )

    levels_map = dict(VANILLA_JOIN_LEVELS)
    if join_levels:
        levels_map.update(join_levels)

    by_id = {c.id: c for c in classes}
    chosen_by_char: Dict[str, ClassDefinition] = {}
    used_ids = set()

    if fixed_assignments:
        for char_key, class_id in fixed_assignments.items():
            if char_key not in PLAYABLE_CHARACTERS:
                raise ValueError(f"Unknown playable character: {char_key!r}")
            if class_id not in by_id:
                raise ValueError(f"Unknown class id: {class_id!r}")
            chosen_by_char[char_key] = by_id[class_id]
            used_ids.add(class_id)

    remaining_chars = [c for c in PLAYABLE_CHARACTERS if c not in chosen_by_char]
    available_classes = [c for c in classes if c.id not in used_ids]
    if len(available_classes) < len(remaining_chars):
        raise ValueError("Not enough distinct classes left to assign all characters.")

    sampled = rng.sample(available_classes, len(remaining_chars))
    for char_key, cls_def in zip(remaining_chars, sampled):
        chosen_by_char[char_key] = cls_def

    assignments: Dict[str, ArchetypeAssignment] = {}
    for char_key in PLAYABLE_CHARACTERS:
        cls_def = chosen_by_char[char_key]
        compiled = compile_class(cls_def)
        join_level = levels_map[char_key]
        normalized = normalize_for_join_level(compiled, join_level)
        assignments[char_key] = ArchetypeAssignment(
            char_key=char_key,
            join_level=join_level,
            compiled=compiled,
            normalized_start=normalized,
            allowed_weapon_ids=tuple(equipment_catalog.weapon_ids_for(cls_def.weapons)),
            allowed_armor_ids=tuple(equipment_catalog.armor_ids_for(cls_def.equipment)),
            allowed_accessory_ids=tuple(
                equipment_catalog.accessory_ids_for(cls_def.equipment)
            ),
        )

    return assignments


def format_archetype_spoiler(
    assignments: Mapping[str, ArchetypeAssignment]
) -> str:
    """Format a clean human-readable spoiler block for Premade Archetypes mode."""
    lines = ["CLASS MODE: PREMADE ARCHETYPES", ""]
    for char_key in PLAYABLE_CHARACTERS:
        a = assignments[char_key]
        defn = a.compiled.definition
        grades = " ".join(
            f"{s.upper()}:{a.compiled.grades_lv40[s]}" for s in STATS
        )
        start_s = " | ".join(
            f"{s.upper()}:{a.normalized_start.stats[s]:>3}" for s in STATS
        )
        lv40_s = " | ".join(
            f"{s.upper()}:{a.compiled.totals_lv40[s]:>3}" for s in STATS
        )
        lines.append(
            f"{char_key.title():5} -> {defn.name} ({defn.role}, curve={defn.curve})"
        )
        lines.append(
            f"  Weapons: {', '.join(defn.weapons)} | Gear: {', '.join(defn.equipment)}"
        )
        lines.append(f"  Join Lv{a.join_level:02d}: {start_s}")
        lines.append(f"  Lv40 Est : {lv40_s}")
        lines.append(f"  Lv40 Rank: {grades}")
        if defn.spells:
            spell_str = ", ".join(f"Lv{sp.level:02d} {sp.skill}" for sp in defn.spells)
            lines.append(f"  Spells   : {spell_str}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_vanilla_swap_spoiler(
    assignments: Mapping[str, VanillaSwapAssignment]
) -> str:
    """Format a clean human-readable spoiler block for Vanilla Role Swap mode."""
    lines = ["CLASS MODE: VANILLA ROLE SWAP", ""]
    for char_key in PLAYABLE_CHARACTERS:
        a = assignments[char_key]
        grades = " ".join(f"{s.upper()}:{a.grades_lv40[s]}" for s in STATS)
        start_s = " | ".join(
            f"{s.upper()}:{a.normalized_start.stats[s]:>3}" for s in STATS
        )
        lv40_s = " | ".join(f"{s.upper()}:{a.totals_lv40[s]:>3}" for s in STATS)
        lines.append(f"{char_key.title():5} <- Vanilla {a.donor_key.title()} kit")
        lines.append(f"  Join Lv{a.join_level:02d}: {start_s}")
        lines.append(f"  Lv40 Est : {lv40_s}")
        lines.append(f"  Lv40 Rank: {grades}")
        lines.append("")
    return "\n".join(lines).rstrip()
