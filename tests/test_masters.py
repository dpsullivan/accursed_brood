"""Zero-ROM unit tests for Curated Master Kits (data/masters.json & genepool/masters.py)."""

from __future__ import annotations

import random
import unittest
from dataclasses import dataclass, field
from typing import Dict, List

from genepool.guardrails import load_crash_blacklist
from genepool.masters import (
    BACKHAND_SKILL_ID,
    MASTER_STAT_ORDER,
    RESTRICTED_MASTER_NAMES,
    apply_master_kit_assignments,
    assign_master_kits,
    collect_character_levelup_skill_ids,
    format_master_kits_spoiler,
    from_twos_complement_byte,
    load_master_kits,
    measure_master_message_bytes,
    stats_fit_master_message,
    to_twos_complement_byte,
)
from genepool.schema import load_classes


@dataclass
class _StubAbility:
    index: int
    name: str


@dataclass
class _StubMasterStats:
    index: int
    hp: int = 0
    ap: int = 0
    pwr: int = 0
    dfn: int = 0
    agi: int = 0
    int: int = 0


@dataclass
class _StubMasterSkills:
    index: int
    skills: List[_StubAbility] = field(default_factory=list)
    levels: List[int] = field(default_factory=list)

    def set_skills(self, skills: List[_StubAbility], levels: List[int]) -> None:
        self.skills = list(skills)
        self.levels = list(levels)


class TestCuratedMasterKits(unittest.TestCase):
    def test_catalog_integrity_and_disjoint_from_blacklist_and_archetypes(self) -> None:
        config = load_master_kits()
        blacklist = load_crash_blacklist()
        classes = load_classes()

        self.assertEqual(len(config.masters), 17)
        self.assertEqual(len(config.non_restricted_masters), 13)
        self.assertGreaterEqual(len(config.kits), 13)

        archetype_skill_ids = {
            sp.ability_id for cls in classes for sp in cls.spells
        }
        banned_enemy_or_dragon = (
            blacklist.globally_banned_ids | blacklist.dragon_form_banned_ids
        )

        seen_kit_skill_ids = set()
        for kit in config.kits:
            for entry in kit.skills:
                self.assertNotIn(
                    entry.skill_id,
                    banned_enemy_or_dragon,
                    f"Kit {kit.id} uses blacklisted skill {entry.name}",
                )
                self.assertNotIn(
                    entry.skill_id,
                    archetype_skill_ids,
                    f"Kit {kit.id} skill {entry.name} collides with archetype level-up table",
                )
                self.assertNotIn(
                    entry.skill_id,
                    seen_kit_skill_ids,
                    f"Duplicate skill {entry.name} across curated Master Kits",
                )
                seen_kit_skill_ids.add(entry.skill_id)

        for fb_id, fb_name in config.safe_fallback_skills:
            self.assertNotIn(fb_id, banned_enemy_or_dragon, f"Fallback {fb_name} is blacklisted")
            self.assertNotIn(fb_id, archetype_skill_ids, f"Fallback {fb_name} collides with archetypes")

    def test_twos_complement_roundtrip_and_bounds(self) -> None:
        for val in (-128, -6, -3, -1, 0, 1, 4, 127):
            packed = to_twos_complement_byte(val)
            self.assertGreaterEqual(packed, 0)
            self.assertLessEqual(packed, 255)
            self.assertEqual(from_twos_complement_byte(packed), val)

        with self.assertRaises(ValueError):
            to_twos_complement_byte(-129)
        with self.assertRaises(ValueError):
            to_twos_complement_byte(128)

    def test_assignments_respect_message_budgets_backhand_and_restricted_masters(self) -> None:
        config = load_master_kits()
        for seed in range(1, 51):
            rng = random.Random(seed)
            assignments = assign_master_kits(config, rng)
            self.assertEqual(len(assignments), 17)

            assigned_kit_ids = set()
            backhand_holders = []

            for a in assignments:
                # Message length must ALWAYS fit without falling back to '???'
                self.assertTrue(
                    stats_fit_master_message(a.stats, a.master.max_msg_bytes),
                    f"Seed {seed}: {a.master.name} stats {a.stats} overflow "
                    f"{a.master.max_msg_bytes}B ({measure_master_message_bytes(a.stats)})",
                )
                # All stat deltas must fit signed int8
                for attr in MASTER_STAT_ORDER:
                    val = a.stats[attr]
                    self.assertGreaterEqual(val, -128)
                    self.assertLessEqual(val, 127)

                if a.master.name in RESTRICTED_MASTER_NAMES:
                    self.assertIsNone(a.kit)
                    self.assertEqual(a.stats, a.master.vanilla_stats)
                    self.assertEqual(a.skills, ())
                else:
                    self.assertIsNotNone(a.kit)
                    assert a.kit is not None
                    self.assertNotIn(a.kit.id, assigned_kit_ids)
                    assigned_kit_ids.add(a.kit.id)
                    if any(s.skill_id == BACKHAND_SKILL_ID for s in a.skills):
                        backhand_holders.append(a.master.name)

            self.assertEqual(len(assigned_kit_ids), 13)
            self.assertTrue(backhand_holders, f"Seed {seed}: Backhand missing!")
            for holder in backhand_holders:
                self.assertNotEqual(holder, "Hondara")
                self.assertNotIn(holder, RESTRICTED_MASTER_NAMES)

    def test_collision_safety_with_character_levelup_skills(self) -> None:
        config = load_master_kits()
        # Simulate legacy random character level-up tables colliding with several Master skills
        colliding = {39, 3, 171, 163, 195, BACKHAND_SKILL_ID}
        assignments = assign_master_kits(
            config, random.Random(424242), banned_skill_ids=colliding
        )
        non_bh_banned = colliding - {BACKHAND_SKILL_ID}
        found_backhand = False
        for a in assignments:
            if a.master.restricted:
                continue
            for entry in a.skills:
                self.assertNotIn(entry.skill_id, non_bh_banned)
                if entry.skill_id == BACKHAND_SKILL_ID:
                    found_backhand = True
        self.assertTrue(found_backhand)

    def test_apply_adapter_and_spoiler_formatting(self) -> None:
        config = load_master_kits()
        assignments = assign_master_kits(config, random.Random(777))

        stats_store: Dict[int, _StubMasterStats] = {
            i: _StubMasterStats(index=i) for i in range(17)
        }
        skills_store: Dict[int, _StubMasterSkills] = {
            i: _StubMasterSkills(index=i) for i in range(17)
        }
        abilities_store: Dict[int, _StubAbility] = {
            i: _StubAbility(index=i, name=f"Skill_{i}") for i in range(228)
        }

        class _StatsCls:
            @classmethod
            def get(cls, idx: int) -> _StubMasterStats:
                return stats_store[idx]

        class _SkillsCls:
            @classmethod
            def get(cls, idx: int) -> _StubMasterSkills:
                return skills_store[idx]

        class _AbilityCls:
            @classmethod
            def get(cls, idx: int) -> _StubAbility:
                return abilities_store[idx]

        apply_master_kit_assignments(
            assignments,
            master_stats_cls=_StatsCls,
            master_skills_cls=_SkillsCls,
            ability_cls=_AbilityCls,
        )

        # Restricted masters must not have their skills overwritten
        for restricted_idx in (11, 12, 13, 14):
            self.assertEqual(skills_store[restricted_idx].skills, [])

        # Non-restricted masters received skills with strictly ascending levels
        for a in assignments:
            if a.master.restricted:
                continue
            sk = skills_store[a.master.index]
            self.assertEqual([s.index for s in sk.skills], [e.skill_id for e in a.skills])
            self.assertEqual(sk.levels, sorted(sk.levels))

        spoiler = format_master_kits_spoiler(assignments)
        self.assertIn("CURATED MASTER KITS", spoiler)
        self.assertIn("Bunyan", spoiler)
        self.assertNotIn("Bais", spoiler)

        # Level-object collector skips restricted prologue characters
        class _Lvl:
            def __init__(self, charname: str, ability: int) -> None:
                self.charname = charname
                self.ability = ability

        collected = collect_character_levelup_skill_ids(
            [_Lvl("Ryu", 0x46), _Lvl("Teepo", 0x5B), _Lvl("Whelp", 0x78), _Lvl("Nina", 0)]
        )
        self.assertEqual(collected, frozenset({0x46}))


if __name__ == "__main__":
    unittest.main()
