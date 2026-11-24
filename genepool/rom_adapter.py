"""Thin adapter applying compiled ``genepool`` class payloads to ``randomtools`` objects."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, Tuple

from .class_assigner import (
    ArchetypeAssignment,
    VanillaCharacterSnapshot,
    VanillaSwapAssignment,
)
from .growth_compiler import LevelRow
from .schema import (
    CHARACTER_INDEX,
    PLAYABLE_CHARACTERS,
    SKILL_CATEGORIES,
    SKILL_TYPE_TO_CATEGORY,
    STAT_TO_ROM_ATTR,
    STATS,
)

COMBAT_RATE_ATTRS: Tuple[str, ...] = (
    "surprise_chance",
    "reprisal_chance",
    "critical_chance",
    "evasion",
    "accuracy",
)

# Vanilla Garr row[0] holds 0x05 Flame Strike (examinable=1, type=3), whereas
# START.EMI gives him 0x9B Pyrokinesis (examinable=0, type=2). Normalizing this
# prevents skill-type conflicts during Vanilla Role Swap.
GARR_FLAME_STRIKE_ID = 0x05
GARR_PYROKINESIS_ID = 0x9B
MOMO_HE_SHELLS_ID = 0x4B


def capture_vanilla_snapshots(
    base_stats_cls: Any, ability_cls: Any
) -> Dict[str, VanillaCharacterSnapshot]:
    """Read intact vanilla character progression snapshots from loaded ``TableObject``s."""
    snapshots: Dict[str, VanillaCharacterSnapshot] = {}

    for char_key in PLAYABLE_CHARACTERS:
        bso = base_stats_cls.get(CHARACTER_INDEX[char_key])
        join_level = int(bso.old_data["level"])

        rows: list[LevelRow] = []
        spell_categories: Dict[int, str] = {}
        for row_idx, lvl_obj in enumerate(bso.levels):
            ability_id = int(lvl_obj.old_data["ability"])
            if char_key == "garr" and row_idx == 0 and ability_id == GARR_FLAME_STRIKE_ID:
                ability_id = GARR_PYROKINESIS_ID
            if ability_id > 0:
                ab = ability_cls.get(ability_id)
                st = int(ab.old_data["skill_type"]) & 0x03
                spell_categories[ability_id] = SKILL_TYPE_TO_CATEGORY[st]

            rows.append(
                LevelRow(
                    level=row_idx + 1,
                    hp=int(lvl_obj.get_old_stat("hp")),
                    ap=int(lvl_obj.get_old_stat("ap")),
                    pwr=int(lvl_obj.get_old_stat("pwr")),
                    dfn=int(lvl_obj.get_old_stat("dfn")),
                    agi=int(lvl_obj.get_old_stat("agi")),
                    intel=int(lvl_obj.get_old_stat("int")),
                    ability=ability_id,
                )
            )

        # De-level from START.EMI join stats using rows[1 .. join_level - 1]
        base_lv1 = {}
        for stat in STATS:
            rom_attr = STAT_TO_ROM_ATTR[stat]
            start_val = int(bso.old_data[rom_attr])
            prior_gains = sum(rows[k].stat(stat) for k in range(1, join_level))
            base_lv1[stat] = max(0, start_val - prior_gains)

        combat_rates = {
            attr: int(bso.old_data[attr]) for attr in COMBAT_RATE_ATTRS
        }
        snapshots[char_key] = VanillaCharacterSnapshot(
            char_key=char_key,
            join_level=join_level,
            base_lv1=base_lv1,
            rows=tuple(rows),
            resistances=tuple(int(r) for r in bso.old_data["resistances"]),
            combat_rates=combat_rates,
            spell_categories=spell_categories,
        )

    return snapshots


def _write_level_rows(bso: Any, rows: Sequence[LevelRow]) -> None:
    if len(bso.levels) != len(rows):
        raise ValueError(
            f"{bso.name}: expected {len(bso.levels)} LevelObject rows, got {len(rows)}."
        )
    for lvl_obj, row in zip(bso.levels, rows):
        lvl_obj.set_stat("hp", row.hp)
        lvl_obj.set_stat("ap", row.ap)
        lvl_obj.set_stat("pwr", row.pwr)
        lvl_obj.set_stat("dfn", row.dfn)
        lvl_obj.set_stat("agi", row.agi)
        lvl_obj.set_stat("int", row.intel)
        lvl_obj.ability = row.ability


def _write_starting_stats_and_spells(
    bso: Any,
    stats: Mapping[str, int],
    starting_spells: Mapping[str, Tuple[int, ...]],
) -> None:
    for stat in STATS:
        rom_attr = STAT_TO_ROM_ATTR[stat]
        val = int(stats[stat])
        setattr(bso, rom_attr, val)
        setattr(bso, f"base_{rom_attr}", val)
        if rom_attr in ("hp", "ap"):
            setattr(bso, f"current_{rom_attr}", val)

    for category in SKILL_CATEGORIES:
        attr = f"{category}_abilities"
        slot_count = len(bso.old_data[attr])
        ids = list(starting_spells.get(category, ()))
        if len(ids) > slot_count:
            raise ValueError(
                f"{bso.name}: {len(ids)} spells exceed {slot_count} slots in {attr}."
            )
        ids.extend([0] * (slot_count - len(ids)))
        setattr(bso, attr, ids)


def _reconcile_starting_gear(
    bso: Any,
    char_key: str,
    weapon_cls: Any,
    armor_cls: Any,
    accessory_cls: Any,
) -> None:
    """Ensure the character starts with gear they can legally equip."""
    weapon = weapon_cls.get(bso.weapon)
    if bso.weapon != 0 and not weapon.get_bit(char_key):
        candidates = [
            w
            for w in weapon_cls.every
            if w.index > 0 and w.old_data["price"] > 0 and w.get_bit(char_key)
        ]
        # Prefer real starter weapons over joke items (Bent Sword 20Z, PointedStick 10Z)
        real_starters = [
            w for w in candidates if w.old_data["price"] >= 50 and w.old_data["power"] >= 4
        ]
        if real_starters:
            candidates = real_starters
        if candidates:
            candidates.sort(key=lambda w: (w.old_data["price"], w.index))
            bso.weapon = candidates[0].index
        else:
            bso.weapon = 0

    for attr, expected_equip_type in (("shield", 2), ("helmet", 3), ("armor", 4)):
        cur_id = getattr(bso, attr)
        if cur_id == 0:
            continue
        cur_armor = armor_cls.get(cur_id)
        if not cur_armor.get_bit(char_key):
            if attr == "armor":
                candidates = [
                    a
                    for a in armor_cls.every
                    if a.index > 0
                    and a.equip_type == expected_equip_type
                    and a.old_data["price"] > 0
                    and a.get_bit(char_key)
                ]
                candidates.sort(key=lambda a: (a.old_data["price"], a.index))
                setattr(bso, attr, candidates[0].index if candidates else 0)
            else:
                setattr(bso, attr, 0)

    valid_acc = [
        aid
        for aid in bso.accessories
        if aid != 0 and accessory_cls.get(aid).get_bit(char_key)
    ]
    while len(valid_acc) < len(bso.old_data["accessories"]):
        valid_acc.append(0)
    bso.accessories = valid_acc


def apply_archetype_assignments(
    assignments: Mapping[str, ArchetypeAssignment],
    *,
    base_stats_cls: Any,
    weapon_cls: Any,
    armor_cls: Any,
    accessory_cls: Any,
    apply_equipment_permissions: bool = True,
) -> None:
    """Write compiled Premade Archetype payloads into ``randomtools`` TableObjects."""
    if apply_equipment_permissions:
        allowed_weapons = {
            char: set(a.allowed_weapon_ids) for char, a in assignments.items()
        }
        allowed_armors = {
            char: set(a.allowed_armor_ids) for char, a in assignments.items()
        }
        allowed_accessories = {
            char: set(a.allowed_accessory_ids) for char, a in assignments.items()
        }

        for w in weapon_cls.every:
            if w.index == 0 or w.old_data["equipability"] == 0:
                continue
            for char in PLAYABLE_CHARACTERS:
                w.set_bit(char, w.index in allowed_weapons[char])
            if w.index == MOMO_HE_SHELLS_ID:
                w.set_bit("momo", True)

        for a in armor_cls.every:
            if a.index == 0 or a.old_data["equipability"] == 0:
                continue
            for char in PLAYABLE_CHARACTERS:
                a.set_bit(char, a.index in allowed_armors[char])

        for acc in accessory_cls.every:
            if acc.index == 0 or acc.old_data["equipability"] == 0:
                continue
            for char in PLAYABLE_CHARACTERS:
                acc.set_bit(char, acc.index in allowed_accessories[char])

    for char_key in PLAYABLE_CHARACTERS:
        assignment = assignments[char_key]
        bso = base_stats_cls.get(CHARACTER_INDEX[char_key])
        _write_level_rows(bso, assignment.compiled.rows)
        _write_starting_stats_and_spells(
            bso,
            assignment.normalized_start.stats,
            assignment.normalized_start.starting_spells,
        )
        _reconcile_starting_gear(bso, char_key, weapon_cls, armor_cls, accessory_cls)


def apply_vanilla_swap_assignments(
    assignments: Mapping[str, VanillaSwapAssignment],
    *,
    base_stats_cls: Any,
    weapon_cls: Any,
    armor_cls: Any,
    accessory_cls: Any,
    apply_equipment_permissions: bool = True,
) -> None:
    """Write Vanilla Role Swap payloads into ``randomtools`` TableObjects."""
    if apply_equipment_permissions:
        donor_bit_index = {c: CHARACTER_INDEX[c] for c in PLAYABLE_CHARACTERS}
        for equip_cls in (weapon_cls, armor_cls, accessory_cls):
            for item in equip_cls.every:
                if item.index == 0 or item.old_data["equipability"] == 0:
                    continue
                old_mask = int(item.old_data["equipability"])
                for char_key in PLAYABLE_CHARACTERS:
                    donor_key = assignments[char_key].donor_key
                    donor_allowed = bool(old_mask & (1 << donor_bit_index[donor_key]))
                    item.set_bit(char_key, donor_allowed)
                if equip_cls is weapon_cls and item.index == MOMO_HE_SHELLS_ID:
                    item.set_bit("momo", True)

    for char_key in PLAYABLE_CHARACTERS:
        assignment = assignments[char_key]
        bso = base_stats_cls.get(CHARACTER_INDEX[char_key])
        _write_level_rows(bso, assignment.rows)
        _write_starting_stats_and_spells(
            bso,
            assignment.normalized_start.stats,
            assignment.normalized_start.starting_spells,
        )
        bso.resistances = list(assignment.resistances)
        bso.base_resistances = list(assignment.resistances)
        for attr, val in assignment.combat_rates.items():
            setattr(bso, attr, val)
            setattr(bso, f"base_{attr}", val)
        _reconcile_starting_gear(bso, char_key, weapon_cls, armor_cls, accessory_cls)
