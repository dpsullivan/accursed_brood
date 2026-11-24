"""Unit tests for Join-Level Normalization and Class Assignment modes."""

from __future__ import annotations

import random
import unittest

from genepool.class_assigner import (
    VanillaCharacterSnapshot,
    assign_archetypes,
    assign_vanilla_role_swap,
    format_archetype_spoiler,
    format_vanilla_swap_spoiler,
)
from genepool.growth_compiler import (
    LevelRow,
    compile_class,
    normalize_for_join_level,
)
from genepool.schema import (
    PLAYABLE_CHARACTERS,
    STATS,
    VANILLA_JOIN_LEVELS,
    load_classes,
    load_equipment_categories,
)


class TestJoinNormalizationAndAssignment(unittest.TestCase):
    def setUp(self) -> None:
        self.equip = load_equipment_categories()
        self.classes = load_classes(equipment_catalog=self.equip)

    def test_join_normalization_exact_endgame_invariance(self) -> None:
        # Regardless of whether a class is assigned to Ryu (Lv 1), Nina/Rei (Lv 5),
        # Momo (Lv 10), or Garr (Lv 13), leveling from join level L to 40 or 99
        # must produce the exact same Lv 40 and Lv 99 stat totals!
        for cls_def in self.classes:
            compiled = compile_class(cls_def)
            for char_key, join_level in VANILLA_JOIN_LEVELS.items():
                norm = normalize_for_join_level(compiled, join_level)
                for target_lvl, expected_totals in (
                    (40, compiled.totals_lv40),
                    (99, compiled.totals_lv99),
                ):
                    simulated = {
                        stat: norm.stats[stat]
                        + sum(compiled.rows[k].stat(stat) for k in range(join_level, target_lvl))
                        for stat in STATS
                    }
                    self.assertEqual(
                        simulated,
                        expected_totals,
                        f"{cls_def.id} on {char_key} (Lv{join_level}) drifted at Lv{target_lvl}",
                    )

    def test_starting_spells_include_exact_prefix_up_to_join_level(self) -> None:
        artificer = next(c for c in self.classes if c.id == "artificer")
        compiled = compile_class(artificer)

        lv1 = normalize_for_join_level(compiled, 1)
        self.assertEqual(lv1.starting_spells["assist"], (0x3C,))  # Identify
        self.assertEqual(lv1.starting_spells["healing"], ())

        lv10 = normalize_for_join_level(compiled, 10)
        # Artificer spells <= Lv 10: Lv1 Identify, Lv2 Foretell, Lv4 Heal, Lv7 Protect, Lv10 Silence
        self.assertEqual(lv10.starting_spells["healing"], (0x46,))
        self.assertEqual(lv10.starting_spells["assist"], (0x3C, 0x44, 0x52, 0x57))
        self.assertEqual(lv10.starting_spells["attack"], ())

    def test_assign_archetypes_is_unique_and_deterministic(self) -> None:
        a1 = assign_archetypes(self.classes, self.equip, random.Random(42))
        a2 = assign_archetypes(self.classes, self.equip, random.Random(42))

        self.assertEqual(set(a1.keys()), set(PLAYABLE_CHARACTERS))
        assigned_ids = [a1[c].compiled.definition.id for c in PLAYABLE_CHARACTERS]
        self.assertEqual(len(set(assigned_ids)), len(PLAYABLE_CHARACTERS))
        self.assertEqual(
            assigned_ids, [a2[c].compiled.definition.id for c in PLAYABLE_CHARACTERS]
        )
        for c in PLAYABLE_CHARACTERS:
            self.assertTrue(a1[c].allowed_weapon_ids)
            self.assertTrue(a1[c].allowed_armor_ids)
            self.assertTrue(a1[c].allowed_accessory_ids)

        spoiler = format_archetype_spoiler(a1)
        self.assertIn("CLASS MODE: PREMADE ARCHETYPES", spoiler)
        self.assertIn("Ryu", spoiler)

    def test_assign_vanilla_role_swap_derangement_and_join_normalization(self) -> None:
        snapshots = {}
        for idx, char_key in enumerate(PLAYABLE_CHARACTERS):
            join_lvl = VANILLA_JOIN_LEVELS[char_key]
            rows = [LevelRow(level=1, hp=0, ap=0, pwr=0, dfn=0, agi=0, intel=0, ability=0x46)]
            for lvl in range(2, 100):
                rows.append(
                    LevelRow(
                        level=lvl,
                        hp=3 + idx,
                        ap=1 + idx,
                        pwr=2,
                        dfn=1,
                        agi=1,
                        intel=2,
                        ability=0x5B if lvl == 6 else 0,
                    )
                )
            snapshots[char_key] = VanillaCharacterSnapshot(
                char_key=char_key,
                join_level=join_lvl,
                base_lv1={"hp": 20 + idx, "ap": 10, "pwr": 10, "def": 10, "agl": 10, "int": 10},
                rows=tuple(rows),
                resistances=(3, 3, 3, 3, 3, 5, 3, 3, 3),
                combat_rates={
                    "surprise_chance": 5,
                    "reprisal_chance": 5,
                    "critical_chance": 5,
                    "evasion": 5,
                    "accuracy": 90,
                },
                spell_categories={0x46: "healing", 0x5B: "attack"},
            )

        swapped = assign_vanilla_role_swap(snapshots, random.Random(1337))
        for char_key, assignment in swapped.items():
            # Derangement: nobody keeps their own vanilla kit
            self.assertNotEqual(char_key, assignment.donor_key)
            # Starting stats equal donor's Lv L totals
            donor = snapshots[assignment.donor_key]
            expected_start = donor.totals_at(VANILLA_JOIN_LEVELS[char_key])
            self.assertEqual(assignment.normalized_start.stats, expected_start)
            # Garr (Lv 13) and Momo (Lv 10) must receive Lv 6 Flare in starting attack spells;
            # Ryu/Peco (Lv 1) and Nina/Rei (Lv 5) must NOT.
            if VANILLA_JOIN_LEVELS[char_key] >= 6:
                self.assertIn(0x5B, assignment.normalized_start.starting_spells["attack"])
            else:
                self.assertNotIn(0x5B, assignment.normalized_start.starting_spells["attack"])

        spoiler = format_vanilla_swap_spoiler(swapped)
        self.assertIn("CLASS MODE: VANILLA ROLE SWAP", spoiler)


if __name__ == "__main__":
    unittest.main()
