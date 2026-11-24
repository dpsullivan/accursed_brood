"""Zero-ROM unit tests for Phase 2 Anti-Softlock Guardrails."""

from __future__ import annotations

import math
import random
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List

from genepool.guardrails import (
    GuardrailReport,
    apply_monster_tier_clamps,
    choose_safe_fallback_skill,
    clamp_stat_value,
    collect_canonical_area_codes,
    enforce_weapon_accessibility,
    filter_enemy_skill_candidates,
    format_guardrails_spoiler,
    load_crash_blacklist,
    load_encounter_tiers,
    load_weapon_accessibility_config,
    sanitize_monster_skills,
)
from genepool.schema import CHARACTER_INDEX, PLAYABLE_CHARACTERS


# ---------------------------------------------------------------------------
# Lightweight ROM-independent stubs
# ---------------------------------------------------------------------------


@dataclass
class FakeAbility:
    index: int
    name: str
    is_offense: bool = True
    is_utility: bool = False
    skill_type: int = 2


class FakeMonster:
    def __init__(
        self,
        *,
        index: int,
        name: str,
        filename: str,
        is_boss: bool,
        hp: int,
        ap: int,
        pwr: int,
        dfn: int,
        agi: int,
        intel: int,
        resistances: List[int],
        initial_skills: List[int] | None = None,
        phases: List[tuple[int, List[int]]] | None = None,
        canonical_relative: FakeMonster | None = None,
    ) -> None:
        self.index = index
        self.name = name
        self.filename = filename
        self.is_boss = is_boss
        self.hp = hp
        self.ap = ap
        self.pwr = pwr
        self.dfn = dfn
        self.agi = agi
        self.int = intel
        self.resistances = list(resistances)
        self.initial_skills = list(initial_skills or [0] * 8)
        phases = phases or [(99, [0] * 8)] * 4
        for i in range(1, 5):
            cond, sks = phases[i - 1]
            setattr(self, f"condition{i}", cond)
            setattr(self, f"skills{i}", list(sks))
        self.old_data: Dict[str, Any] = {
            "hp": hp,
            "ap": ap,
            "pwr": pwr,
            "dfn": dfn,
            "agi": agi,
            "int": intel,
            "resistances": list(resistances),
            "initial_skills": list(self.initial_skills),
        }
        for i in range(1, 5):
            self.old_data[f"condition{i}"] = getattr(self, f"condition{i}")
            self.old_data[f"skills{i}"] = list(getattr(self, f"skills{i}"))
        self.canonical_relative = canonical_relative if canonical_relative is not None else self

    @property
    def is_canonical(self) -> bool:
        return self.canonical_relative is self

    def propagate_from_canonical(self) -> None:
        if not self.is_canonical:
            for attr in self.old_data:
                val = getattr(self.canonical_relative, attr)
                setattr(self, attr, list(val) if isinstance(val, list) else val)


class FakeItem:
    def __init__(
        self,
        *,
        index: int,
        name: str,
        item_type: int,
        price: int,
        power: int = 0,
        equipability: int = 0,
    ) -> None:
        self.index = index
        self.name = name
        self.item_type = item_type
        self.price = price
        self.power = power
        self.equipability = equipability
        self.old_data = {
            "price": price,
            "power": power,
            "equipability": equipability,
        }

    def get_bit(self, char_key: str) -> bool:
        return bool(self.equipability & (1 << CHARACTER_INDEX[char_key]))

    def set_bit(self, char_key: str, truth: bool) -> None:
        bit = 1 << CHARACTER_INDEX[char_key]
        if truth:
            self.equipability |= bit
        else:
            self.equipability &= ~bit


class FakeShop:
    def __init__(self, index: int, name: str, items: List[FakeItem]) -> None:
        self.index = index
        self.name = name
        self._items = list(items)

    @property
    def items(self) -> List[FakeItem]:
        return list(self._items)

    def set_items(self, items: List[FakeItem]) -> None:
        self._items = list(items)


def _build_ability_table() -> Dict[int, FakeAbility]:
    entries = [
        # Globally banned / dragon / boss / species-locked
        FakeAbility(0x01, "Nue Stomp", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0x0E, "Flying Kick", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0x11, "Astral Warp", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0x12, "Giant Growth", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0x1C, "Devour", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0x34, "Ovum", is_offense=True, is_utility=True, skill_type=3),
        FakeAbility(0x40, "Weretiger", is_offense=False, is_utility=False, skill_type=2),
        FakeAbility(0x78, "Whelp Breath", is_offense=True, is_utility=False, skill_type=2),
        FakeAbility(0x80, "Head Cracker", is_offense=True, is_utility=False, skill_type=2),
        FakeAbility(0x81, "Holocaust", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0x83, "KaiserBreath", is_offense=True, is_utility=False, skill_type=2),
        FakeAbility(0x8A, "Main Cannon", is_offense=False, is_utility=False, skill_type=0),
        FakeAbility(0x96, "Eye Beam", is_offense=True, is_utility=False, skill_type=2),
        FakeAbility(0xA0, "Jump", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0xD9, "Restore Form", is_offense=False, is_utility=False, skill_type=3),
        # Safe fallbacks (attack, assist, healing)
        FakeAbility(0x08, "Blind", is_offense=True, is_utility=True, skill_type=3),
        FakeAbility(0x75, "Rest", is_offense=False, is_utility=False, skill_type=3),
        FakeAbility(0x76, "Burn", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0x77, "Double Blow", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0x98, "Snooze", is_offense=False, is_utility=False, skill_type=3),
        FakeAbility(0x9F, "Gloom", is_offense=True, is_utility=True, skill_type=3),
        FakeAbility(0xAE, "Heal", is_offense=False, is_utility=False, skill_type=3),
        FakeAbility(0xAF, "Rejuvenate", is_offense=False, is_utility=False, skill_type=3),
        FakeAbility(0xBD, "Silence", is_offense=True, is_utility=True, skill_type=3),
        FakeAbility(0xC1, "Flare", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0xC4, "Frost", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0xC7, "Jolt", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0xCA, "Cyclone", is_offense=True, is_utility=False, skill_type=3),
        FakeAbility(0xD1, "Sleep", is_offense=True, is_utility=True, skill_type=3),
        FakeAbility(0xD2, "Confuse", is_offense=True, is_utility=True, skill_type=3),
    ]
    return {a.index: a for a in entries}


def _build_full_weapon_roster(equip_map: Dict[str, List[str]]) -> List[FakeItem]:
    """Build representative weapons covering all 6 categories with realistic vanilla prices/powers."""
    # (id, name, category, power, price)
    catalog = [
        # daggers
        (1, "Dagger", "daggers", 4, 50),
        (2, "BallockKnife", "daggers", 6, 100),
        (5, "Silver Knife", "daggers", 12, 1400),
        (6, "Scramasax", "daggers", 23, 1200),
        (11, "Royal Dagger", "daggers", 54, 6200),
        (12, "Baselard", "daggers", 59, 6500),
        (65, "ThievesKnife", "daggers", 36, 3200),
        # swords
        (3, "Bronze Sword", "swords", 8, 240),
        (4, "Broad Sword", "swords", 15, 600),
        (7, "Moon Sword", "swords", 32, 2000),
        (8, "Claymore", "swords", 43, 2500),
        (9, "Flare Sword", "swords", 38, 3200),
        (10, "FeatherSword", "swords", 48, 5200),
        (28, "Bent Sword", "swords", 2, 20),
        # staves
        (29, "PointedStick", "staves", 1, 10),
        (30, "Oaken Staff", "staves", 6, 50),
        (31, "Mace", "staves", 12, 400),
        (32, "Magician Rod", "staves", 20, 780),
        (33, "QuarterStaff", "staves", 28, 1100),
        (34, "WindCutter", "staves", 34, 2200),
        (35, "Ruby Scepter", "staves", 43, 3200),
        # spears
        (41, "Spear", "spears", 16, 750),
        (42, "Long Spear", "spears", 24, 1000),
        (43, "Halberd", "spears", 33, 2100),
        (44, "Rood Spear", "spears", 41, 2900),
        (45, "Flame Spear", "spears", 42, 3800),
        (46, "Flying Spear", "spears", 50, 5000),
        # claws
        (55, "Claws", "claws", 6, 200),
        (56, "Rippers", "claws", 10, 600),
        (57, "Spiked Claws", "claws", 18, 1300),
        (58, "Flame Talons", "claws", 25, 3300),
        (59, "Tiger Claws", "claws", 34, 3800),
        (60, "Raptor Claws", "claws", 46, 5800),
        # cannons
        (70, "Ammo", "cannons", 58, 500),
        (71, "Flame Chrysm", "cannons", 50, 500),
        (72, "Ice Chrysm", "cannons", 50, 500),
        (73, "ShotgunShell", "cannons", 78, 2200),
        (74, "Sleep Shells", "cannons", 80, 2500),
        (75, "HE Shells", "cannons", 166, 4200),
        (76, "Flash Shells", "cannons", 96, 5300),
    ]
    weapons: List[FakeItem] = [FakeItem(index=0, name="Nothing", item_type=1, price=0)]
    for wid, name, cat, pwr, price in catalog:
        mask = 0
        for char_key, cats in equip_map.items():
            if cat in cats:
                mask |= 1 << CHARACTER_INDEX[char_key]
        if wid == 75:  # Momo HE Shells story guard
            mask |= 1 << CHARACTER_INDEX["momo"]
        weapons.append(
            FakeItem(
                index=wid,
                name=name,
                item_type=1,
                price=price,
                power=pwr,
                equipability=mask,
            )
        )
    return weapons


class TestGuardrailConfigs(unittest.TestCase):
    def test_json_configs_load_and_cross_validate(self) -> None:
        bl = load_crash_blacklist()
        self.assertIn(0x01, bl.globally_banned_ids)
        self.assertIn(0x80, bl.globally_banned_ids)
        self.assertIn("Nue Stomp", bl.globally_banned_names)
        self.assertIn("Head Cracker", bl.globally_banned_names)
        self.assertIn("Backhand", bl.levelup_banned_names)
        self.assertIn(0x78, bl.dragon_form_banned_ids)
        self.assertIn(0x8A, bl.boss_only_ids)
        self.assertIn("Scorpion", bl.enemy_specific_bans)
        self.assertIn("Codger", bl.enemy_specific_bans)

        # Every safe fallback must itself be legal for regular enemies
        for cat, ids in bl.safe_fallbacks.items():
            self.assertTrue(ids, f"Empty safe_fallbacks for {cat}")
            for sid in ids:
                self.assertTrue(
                    bl.is_candidate_allowed(sid, monster_name="Scorpion", is_boss=False),
                    f"Fallback 0x{sid:02X} in {cat} is banned!",
                )

        tiers = load_encounter_tiers()
        self.assertEqual(tiers.tier_order, ("early", "mid", "late"))
        self.assertTrue(tiers.protect_max_hp_sentinels)
        for tname in ("early", "mid", "late"):
            self.assertIn(tname, tiers.tiers)

        wcfg = load_weapon_accessibility_config()
        self.assertEqual(wcfg.max_items_per_shop, 11)
        self.assertIn((1, 0x47), wcfg.protected_shop_items[0x0D])
        self.assertFalse(set(wcfg.early_shops) & set(wcfg.faerie_shop_ids))
        self.assertFalse(set(wcfg.mid_shops) & set(wcfg.faerie_shop_ids))
        for cat, cat_ids in wcfg.weapons_by_category.items():
            for tier in ("early", "mid"):
                t_ids = wcfg.weapon_tiers[cat][tier]
                self.assertTrue(t_ids, f"Missing {tier} weapons for {cat}")
                for wid in t_ids:
                    self.assertIn(wid, cat_ids)
                    self.assertNotIn(wid, wcfg.excluded_weapon_ids)


class TestCrashBlacklistGuardrail(unittest.TestCase):
    def setUp(self) -> None:
        self.bl = load_crash_blacklist()
        self.abilities = _build_ability_table()

    def test_strips_globally_banned_boss_only_and_dragon_skills_from_regular_enemies(self) -> None:
        scorpion = FakeMonster(
            index=10,
            name="Scorpion",
            filename="BIN/WORLD03/AREA125.EMI",
            is_boss=False,
            hp=100, ap=20, pwr=40, dfn=20, agi=20, intel=10,
            resistances=[3] * 9,
            initial_skills=[0x01, 0x80, 0x78, 0x8A, 0x0E, 0x34, 0x76, 0x77],
            phases=[
                (16, [0x11, 0x81, 0x83, 0x08, 0, 0, 0, 0]),
                # Inactive phase (condition == 99) has Capcom template Nue Stomp; should be untouched
                (99, [0x01, 0x01, 0, 0, 0, 0, 0, 0]),
                (99, [0] * 8),
                (99, [0] * 8),
            ],
        )

        ivs = sanitize_monster_skills(
            scorpion,
            abilities_by_id=self.abilities,
            blacklist=self.bl,
            rng=random.Random(123),
        )
        self.assertGreaterEqual(len(ivs), 8)

        # No forbidden skill remains in active slots
        active = scorpion.initial_skills + scorpion.skills1
        for sid in active:
            if sid > 0:
                self.assertIsNone(
                    self.bl.is_skill_forbidden(sid, monster_name="Scorpion", is_boss=False),
                    f"Forbidden skill 0x{sid:02X} survived on Scorpion!",
                )

        # Category preservation: Ovum (0x34, utility) -> assist fallback; Main Cannon (0x8A, healing) -> healing fallback
        self.assertIn(scorpion.initial_skills[5], self.bl.safe_fallbacks["assist"])
        self.assertIn(scorpion.initial_skills[3], self.bl.safe_fallbacks["healing"])
        # Safe skills kept untouched
        self.assertEqual(scorpion.initial_skills[6], 0x76)
        self.assertEqual(scorpion.initial_skills[7], 0x77)
        # Inactive condition == 99 slot untouched by default
        self.assertEqual(scorpion.skills2[0], 0x01)

    def test_native_boss_and_species_owners_are_preserved(self) -> None:
        nue = FakeMonster(
            index=155,
            name="Nue",
            filename="BIN/WORLD00/AREA022.EMI",
            is_boss=True,
            hp=290, ap=3, pwr=23, dfn=11, agi=12, intel=2,
            resistances=[3] * 9,
            initial_skills=[0x01, 0x01, 0x76, 0, 0, 0, 0, 0],
        )
        ivs = sanitize_monster_skills(nue, abilities_by_id=self.abilities, blacklist=self.bl)
        self.assertEqual(ivs, [])
        self.assertEqual(nue.initial_skills[0], 0x01)

        # Even a boss may NOT receive dragon-form skills or another boss's globally banned skill
        nue.initial_skills = [0x01, 0x80, 0x78, 0xD9, 0, 0, 0, 0]
        ivs2 = sanitize_monster_skills(nue, abilities_by_id=self.abilities, blacklist=self.bl)
        self.assertEqual(len(ivs2), 3)
        self.assertEqual(nue.initial_skills[0], 0x01)
        self.assertNotIn(0x80, nue.initial_skills)
        self.assertNotIn(0x78, nue.initial_skills)
        self.assertNotIn(0xD9, nue.initial_skills)

        # Native owner Gonghead keeps Giant Growth (0x12), while Codger cannot receive it
        self.assertTrue(self.bl.is_candidate_allowed(0x12, monster_name="Gonghead", is_boss=False))
        self.assertFalse(self.bl.is_candidate_allowed(0x12, monster_name="Codger", is_boss=False))

    def test_filter_enemy_skill_candidates_excludes_unsafe_pool(self) -> None:
        all_abs = list(self.abilities.values())
        filtered = filter_enemy_skill_candidates(
            all_abs, monster_name="Codger", is_boss=False, blacklist=self.bl
        )
        filtered_ids = {a.index for a in filtered}
        for bad in (0x01, 0x80, 0x11, 0x12, 0x1C, 0x34, 0x40, 0x78, 0x81, 0x83, 0x8A, 0x96, 0xA0, 0xD9):
            self.assertNotIn(bad, filtered_ids)
        # Codger natively owns Flying Kick (0x0E)
        self.assertIn(0x0E, filtered_ids)
        self.assertIn(0x76, filtered_ids)


class TestEncounterTierGuardrail(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = load_encounter_tiers()

    def test_early_boss_and_enemy_stat_clamps_under_extreme_mutation(self) -> None:
        nue = FakeMonster(
            index=155,
            name="Nue",
            filename="BIN/WORLD00/AREA022.EMI",
            is_boss=True,
            hp=290, ap=3, pwr=23, dfn=11, agi=12, intel=2,
            resistances=[2, 2, 2, 2, 2, 2, 3, 3, 7],
        )
        # Simulate extreme stat randomization + high difficulty multiplier
        nue.hp = 4500
        nue.pwr = 120
        nue.dfn = 150
        nue.agi = 90
        nue.int = 80
        nue.resistances = [7, 7, 7, 7, 7, 7, 7, 7, 7]

        iv = apply_monster_tier_clamps(nue, area_codes=[22], config=self.cfg)
        self.assertIsNotNone(iv)
        self.assertEqual(nue.hp, math.ceil(290 * 1.30))
        self.assertEqual(nue.pwr, math.ceil(23 * 1.25))
        self.assertEqual(nue.dfn, math.ceil(11 * 1.25))
        self.assertEqual(nue.agi, math.ceil(12 * 1.25))
        # Tiny vanilla INT=2 gets early_boss small_stat_headroom (+2 -> 4)
        self.assertEqual(nue.int, max(2 + self.cfg.tiers["early"].boss_clamps.small_stat_headroom, math.ceil(2 * 1.25)))
        # Vanilla 2 -> max 3; vanilla 7 (death immunity) preserved at 7
        self.assertEqual(nue.resistances, [3, 3, 3, 3, 3, 3, 4, 4, 7])

    def test_small_stat_headroom_allows_gentle_variance_on_tiny_stats(self) -> None:
        self.assertEqual(self.cfg.tiers["early"].boss_clamps.small_stat_headroom, 2)
        self.assertEqual(self.cfg.tiers["early"].enemy_clamps.small_stat_headroom, 3)
        self.assertEqual(self.cfg.tiers["mid"].enemy_clamps.small_stat_headroom, 4)
        self.assertEqual(self.cfg.tiers["late"].enemy_clamps.small_stat_headroom, 5)

        # Tiny positive stat (vanilla=3) gets headroom (+3 -> 6) instead of ceil(3 * 1.30) = 4
        self.assertEqual(clamp_stat_value(20, 3, 0.75, 1.30, small_stat_headroom=3), 6)
        # Larger stat (vanilla=100) still uses multiplier bound (130), not headroom (103)
        self.assertEqual(clamp_stat_value(200, 100, 0.75, 1.30, small_stat_headroom=3), 130)
        # Zero vanilla stat remains 0 regardless of headroom
        self.assertEqual(clamp_stat_value(50, 0, 0.75, 1.30, small_stat_headroom=3), 0)

    def test_multi_area_enemy_uses_earliest_tier_and_propagates_to_dupes(self) -> None:
        # Eye Goo appears in AREA003 (Cedar Woods, early) and AREA172 (Eden, late)
        canon = FakeMonster(
            index=24,
            name="Eye Goo",
            filename="BIN/WORLD00/AREA003.EMI",
            is_boss=False,
            hp=12, ap=0, pwr=14, dfn=7, agi=4, intel=1,
            resistances=[2] * 9,
        )
        late_copy = FakeMonster(
            index=1190,
            name="Eye Goo",
            filename="BIN/WORLD04/AREA172.EMI",
            is_boss=False,
            hp=12, ap=0, pwr=14, dfn=7, agi=4, intel=1,
            resistances=[2] * 9,
            canonical_relative=canon,
        )
        area_map = collect_canonical_area_codes([canon, late_copy])
        self.assertEqual(area_map[24], frozenset({3, 172}))

        # Tar Man 150 DEF + 200 HP leaks onto Eye Goo
        canon.hp = 200
        canon.ap = 50  # vanilla AP=0 must remain 0
        canon.dfn = 150
        iv = apply_monster_tier_clamps(canon, area_codes=area_map[24], config=self.cfg)
        self.assertIsNotNone(iv)
        self.assertIn("[early enemy]", iv.detail)
        self.assertEqual(canon.hp, math.ceil(12 * 1.35))
        self.assertEqual(canon.ap, 0)
        self.assertEqual(canon.dfn, math.ceil(7 * 1.30))

        # DupeMixin propagation gives the Eden copy the exact clamped values
        late_copy.propagate_from_canonical()
        self.assertEqual(late_copy.hp, canon.hp)
        self.assertEqual(late_copy.dfn, canon.dfn)
        self.assertEqual(late_copy.ap, 0)

    def test_protected_scripted_encounters_restored_to_vanilla(self) -> None:
        # Prologue Operator (HP=65535), Beyd/Zig duel, and Arena Garr (AREA080 HP=65535)
        zig = FakeMonster(
            index=639,
            name="Zig",
            filename="BIN/WORLD02/AREA092.EMI",
            is_boss=True,
            hp=250, ap=50, pwr=70, dfn=40, agi=12, intel=3,
            resistances=[3] * 9,
        )
        zig.hp = 9999
        zig.pwr = 400
        zig.resistances = [7] * 9
        iv = apply_monster_tier_clamps(zig, area_codes=[92], config=self.cfg)
        self.assertIsNotNone(iv)
        self.assertIn("[protected:", iv.detail)
        self.assertEqual(zig.hp, 250)
        self.assertEqual(zig.pwr, 70)
        self.assertEqual(zig.resistances, [3] * 9)

        # Angel Tower Garr (AREA085, HP=380, PWR=0) is a mid boss, NOT 65535 sentinel
        garr_tower = FakeMonster(
            index=588,
            name="Garr",
            filename="BIN/WORLD02/AREA085.EMI",
            is_boss=True,
            hp=380, ap=30, pwr=0, dfn=50, agi=11, intel=60,
            resistances=[3] * 9,
        )
        garr_tower.hp = 2000
        garr_tower.pwr = 120
        iv_garr = apply_monster_tier_clamps(garr_tower, area_codes=[85], config=self.cfg)
        self.assertIsNotNone(iv_garr)
        self.assertIn("[mid boss]", iv_garr.detail)
        self.assertEqual(garr_tower.hp, math.ceil(380 * 1.55))
        self.assertEqual(garr_tower.pwr, 0)  # zero vanilla stat preserved!


class TestWeaponAccessibilityGuardrail(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = load_weapon_accessibility_config()

    def test_injects_early_and_mid_weapons_for_dead_end_archetype_pools(self) -> None:
        # Party using spears, claws, cannons, staves, daggers, swords
        equip_map = {
            "ryu": ["spears"],
            "nina": ["cannons"],
            "garr": ["claws"],
            "rei": ["staves"],
            "momo": ["daggers"],
            "peco": ["swords"],
        }
        weapons = _build_full_weapon_roster(equip_map)
        w_by_id = {w.index: w for w in weapons}

        herb = FakeItem(index=3, name="Healing Herb", item_type=0, price=10)
        leather = FakeItem(index=2, name="LeatherArmor", item_type=2, price=180)
        flame_chrysm = w_by_id[71]

        # Worst-case shops: early shops have NO weapons at all; mid shops only have Flame Chrysm in 0x0D
        shops = [
            FakeShop(0, "MCNEIL WEAPON", [leather]),
            FakeShop(2, "WYNDIA WEAPON", [herb]),
            FakeShop(6, "GENMEL WEAPON", [leather, herb]),
            FakeShop(10, "ARENA WEAPON", []),
            FakeShop(13, "RHAPALA WEAPON", [flame_chrysm]),
            FakeShop(15, "URKAN TAPA WEAPON", [leather]),
            FakeShop(17, "FAERIE WEAPON SPEED", [herb] * 11),
            FakeShop(23, "SYN CITY WEAPON", [leather]),
            FakeShop(25, "JUNK TOWN WEAPON", []),
            FakeShop(35, "PARCH WEAPON", [leather]),
        ]

        ivs = enforce_weapon_accessibility(shops, weapons, config=self.cfg)
        self.assertGreater(len(ivs), 0)

        shops_by_id = {s.index: s for s in shops}
        # Verify 11-item shop limit and faerie shop untouched
        for s in shops:
            self.assertLessEqual(len(s.items), 11, f"Shop 0x{s.index:02X} overflowed 11 items!")
        self.assertEqual(shops_by_id[17].items, [herb] * 11)
        # Verify Flame Chrysm preserved in 0x0D
        self.assertIn(flame_chrysm, shops_by_id[13].items)

        # Verify every playable character has an affordable early AND mid weapon in accessible shops
        early_wpns = [
            it for sid in self.cfg.early_shops
            for it in shops_by_id[sid].items
            if it.item_type == 1
        ]
        mid_wpns = [
            it for sid in self.cfg.mid_shops
            for it in shops_by_id[sid].items
            if it.item_type == 1
        ]
        for char in PLAYABLE_CHARACTERS:
            char_early = [w for w in early_wpns if w.get_bit(char) and w.price <= self.cfg.early_max_price]
            char_mid = [w for w in mid_wpns if w.get_bit(char) and w.price <= self.cfg.mid_max_price]
            self.assertTrue(char_early, f"{char} has no affordable early shop weapon!")
            self.assertTrue(char_mid, f"{char} has no affordable mid shop weapon!")

    def test_full_shops_and_price_spikes_handled_without_overflow_or_displacing_protected(self) -> None:
        equip_map = {
            "ryu": ["spears"],
            "nina": ["claws"],
            "garr": ["cannons"],
            "rei": ["staves"],
            "momo": ["daggers"],
            "peco": ["swords"],
        }
        weapons = _build_full_weapon_roster(equip_map)
        w_by_id = {w.index: w for w in weapons}
        # Spike all early spear prices to test affordability capping
        w_by_id[41].price = 45000
        w_by_id[42].price = 50000

        fillers = [FakeItem(index=i, name=f"Filler{i}", item_type=0, price=10) for i in range(1, 12)]
        flame_chrysm = w_by_id[71]

        # Every single early & mid shop is 11/11 FULL!
        shops = [
            FakeShop(0, "MCNEIL WEAPON", list(fillers)),
            FakeShop(2, "WYNDIA WEAPON", list(fillers)),
            FakeShop(6, "GENMEL WEAPON", list(fillers)),
            FakeShop(10, "ARENA WEAPON", list(fillers)),
            FakeShop(13, "RHAPALA WEAPON", [flame_chrysm] + list(fillers[:10])),
            FakeShop(15, "URKAN TAPA WEAPON", list(fillers)),
            FakeShop(23, "SYN CITY WEAPON", list(fillers)),
            FakeShop(25, "JUNK TOWN WEAPON", list(fillers)),
            FakeShop(35, "PARCH WEAPON", list(fillers)),
        ]

        ivs = enforce_weapon_accessibility(shops, weapons, config=self.cfg)
        self.assertGreater(len(ivs), 0)

        shops_by_id = {s.index: s for s in shops}
        for s in shops:
            self.assertEqual(len(s.items), 11, f"Shop 0x{s.index:02X} must stay at 11 items!")
        # Protected Flame Chrysm untouched
        self.assertIn(flame_chrysm, shops_by_id[13].items)
        # Early spear made affordable
        early_spears = [
            it for sid in self.cfg.early_shops
            for it in shops_by_id[sid].items
            if it.item_type == 1 and it.index in (41, 42)
        ]
        self.assertTrue(early_spears)
        self.assertLessEqual(early_spears[0].price, self.cfg.early_max_price)

    def test_spoiler_report_formatting(self) -> None:
        report = GuardrailReport(
            crash_guard_enabled=True,
            tier_clamp_enabled=False,
            weapon_guard_enabled=True,
        )
        report.add("crash_blacklist", "Scorpion", "Replaced Nue Stomp (0x01) -> Burn (0x76)")
        report.add("weapon_access", "Shop 0x02 (WYNDIA WEAPON)", "[early] Added Spear (0x29, 750Z)")
        text = format_guardrails_spoiler(report)
        self.assertIn("crash_blacklist=ON", text)
        self.assertIn("encounter_tiers=OFF", text)
        self.assertIn("weapon_access=ON", text)
        self.assertIn("Scorpion", text)
        self.assertIn("Spear", text)


if __name__ == "__main__":
    unittest.main()
