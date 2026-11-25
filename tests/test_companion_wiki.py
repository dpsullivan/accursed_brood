"""Zero-ROM on-demand unit tests for the Companion Wiki exporter, normalization, and registry.

Run on demand:
    python -m unittest tests/test_companion_wiki.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import random
import tempfile
import unittest
from typing import Any, Dict, List

from genepool.class_assigner import assign_archetypes
from genepool.companion_wiki import (
    SCHEMA_VERSION,
    compute_run_id,
    decode_resistance,
    export_companion_wiki_run,
    rebuild_seed_registry,
)
from genepool.genes import load_dragon_genes_config
from genepool.guardrails import GuardrailReport
from genepool.masters import assign_master_kits, load_master_kits
from genepool.options import RunOptions
from genepool.schema import CHARACTER_INDEX, PLAYABLE_CHARACTERS, load_classes, load_equipment_categories


@dataclass
class _StubAbility:
    index: int
    name: str
    old_name: str
    cost: int = 4
    power: int = 30
    skill_type: int = 2
    element: int = 0
    misc: int = 0x20
    examinable: bool = False
    old_data: Dict[str, Any] = field(default_factory=dict)

    def get_bit(self, bit: str) -> bool:
        if bit == "examinable":
            return self.examinable
        return False


@dataclass
class _StubLevel:
    index: int
    hp: int = 4
    ap: int = 2
    pwr: int = 3
    dfn: int = 2
    agi: int = 1
    int: int = 2
    ability: int = 0
    old_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def level(self) -> int:
        return (self.index % 99) + 1

    def get_old_stat(self, attr: str) -> int:
        return int(self.old_data.get(attr, getattr(self, attr)))


@dataclass
class _StubBaseStats:
    index: int
    name: str
    old_name: str
    level: int
    hp: int
    ap: int
    pwr: int
    dfn: int
    agi: int
    int: int
    old_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubMasterStats:
    index: int
    name: str
    hp: int = 0
    ap: int = 0
    pwr: int = 0
    dfn: int = 0
    agi: int = 0
    int: int = 0
    old_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubMasterSkills:
    index: int
    skill_levels: List[int] = field(default_factory=list)
    old_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubGene:
    index: int
    gene_index: int
    old_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubItem:
    index: int
    name: str
    old_name: str
    price: int = 100
    power: int = 0
    weight: int = 1
    equip_type: int = 4
    equipability: int = 0
    element: int = 0
    old_data: Dict[str, Any] = field(default_factory=dict)

    def get_bit(self, char_key: str) -> bool:
        if char_key in CHARACTER_INDEX:
            return bool(self.equipability & (1 << CHARACTER_INDEX[char_key]))
        return False


@dataclass
class _StubShop:
    index: int
    name: str
    item_type_item_indexes: List[int] = field(default_factory=list)
    old_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubManilloStock:
    index: int
    trade_indexes: List[int] = field(default_factory=list)
    old_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubManilloItem:
    index: int
    item_type: int
    item_index: int
    fish_indexes: List[int] = field(default_factory=list)
    fish_quantities: List[int] = field(default_factory=list)
    old_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubChest:
    index: int
    filename: str
    memory: int
    item_type: int
    item_index: int
    old_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubMonster:
    index: int
    name: str
    old_name: str
    filename: str
    level: int
    hp: int
    ap: int
    pwr: int
    dfn: int
    agi: int
    int: int
    exp: int
    zenny: int
    resistances: List[int]
    steal_item_type: int = 0
    steal_item_index: int = 0
    steal_rate: int = 0
    drop_item_type: int = 0
    drop_item_index: int = 0
    drop_rate: int = 0
    initial_skills: List[int] = field(default_factory=list)
    condition1: int = 99
    skills1: List[int] = field(default_factory=list)
    is_boss: bool = False
    is_canonical: bool = True
    canonical_relative: Any = None
    old_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.canonical_relative is None:
            self.canonical_relative = self


def _build_stub_world() -> Dict[str, Any]:
    """Assemble lightweight TableObject stubs exercising every Companion Wiki category."""
    # Abilities including dummy slots & duplicate level-up vs examine/Master slots
    abilities = [
        _StubAbility(0, "", "", cost=0, old_data={"cost": 0, "power": 0, "skill_type": 0, "unknown2": 0, "misc": 0}),
        _StubAbility(1, "Nothing", "Nothing", cost=0, old_data={"cost": 0, "power": 0, "skill_type": 0, "unknown2": 0, "misc": 0}),
        _StubAbility(2, "Noting", "Noting", cost=0, old_data={"cost": 0, "power": 0, "skill_type": 0, "unknown2": 0, "misc": 0}),
        _StubAbility(0x0B, "Multistrike", "Multistrike", cost=4, power=55, skill_type=3, examinable=True, old_data={"cost": 4, "power": 55, "skill_type": 3, "unknown2": 0x02, "misc": 0x20}),
        _StubAbility(0x5B, "Flare", "Flare", cost=3, power=40, skill_type=2, element=0x01, examinable=False, old_data={"cost": 3, "power": 40, "skill_type": 2, "element": 0x01, "unknown2": 0x00, "misc": 0x20}),
        _StubAbility(0xC1, "Flare", "Flare", cost=3, power=40, skill_type=3, element=0x01, examinable=True, old_data={"cost": 3, "power": 40, "skill_type": 3, "element": 0x01, "unknown2": 0x02, "misc": 0x20}),
        _StubAbility(0xA5, "Backhand", "Backhand", cost=0, power=30, skill_type=3, examinable=True, old_data={"cost": 0, "power": 30, "skill_type": 3, "unknown2": 0x02, "misc": 0x20}),
    ]

    # Characters & 99 level rows for each playable character
    base_stats = []
    levels = []
    for char_key in PLAYABLE_CHARACTERS:
        cidx = CHARACTER_INDEX[char_key]
        base_stats.append(
            _StubBaseStats(
                index=cidx,
                name=char_key.title(),
                old_name=char_key.title(),
                level=1 if char_key in ("ryu", "peco") else 5,
                hp=60 + cidx * 4,
                ap=25 + cidx * 2,
                pwr=20,
                dfn=16,
                agi=12,
                int=18,
                old_data={"level": 1 if char_key in ("ryu", "peco") else 5, "hp": 45, "ap": 15, "pwr": 14, "dfn": 12, "agi": 10, "int": 11},
            )
        )
        for row in range(99):
            ab = 0x5B if (row == 3 and char_key == "ryu") else 0
            old_ab = 0x5B if (row == 5 and char_key == "nina") else 0
            levels.append(
                _StubLevel(
                    index=cidx * 99 + row,
                    hp=5 if row > 0 else 0,
                    ap=3 if row > 0 else 0,
                    pwr=3 if row > 0 else 0,
                    dfn=2 if row > 0 else 0,
                    agi=1 if row > 0 else 0,
                    int=3 if row > 0 else 0,
                    ability=ab,
                    old_data={"hp": 4 if row > 0 else 0, "ap": 2 if row > 0 else 0, "pwr": 2 if row > 0 else 0, "dfn": 2 if row > 0 else 0, "agi": 1 if row > 0 else 0, "int": 2 if row > 0 else 0, "ability": old_ab},
                )
            )

    # Masters (testing unsigned two's-complement negative bytes after cleanup!)
    master_stats = [
        _StubMasterStats(
            index=0,
            name="Bunyan",
            hp=2,
            ap=0xFE,  # -2 as uint8 after cleanup
            pwr=3,
            dfn=1,
            agi=0,
            int=0xFD,  # -3 as uint8 after cleanup
            old_data={"hp": 2, "ap": -2, "pwr": 2, "dfn": 1, "agi": 0, "int": -3},
        ),
        _StubMasterStats(
            index=11,
            name="Bais",
            hp=0,
            ap=0,
            pwr=1,
            dfn=0,
            agi=0,
            int=0,
            old_data={"hp": 0, "ap": 0, "pwr": 1, "dfn": 0, "agi": 0, "int": 0},
        ),
    ]
    master_skills = [
        _StubMasterSkills(
            index=0,
            skill_levels=[(0xA5 << 8) | 3, (0x0B << 8) | 6, 0xFF63],
            old_data={"skill_levels": [(0x0B << 8) | 2, 0xFF63]},
        ),
        _StubMasterSkills(index=11, skill_levels=[0xFF63], old_data={"skill_levels": [0xFF63]}),
    ]

    # All 17 Dragon Genes (including raw 0x21 Flame vanilla normalization)
    gene_cfg = load_dragon_genes_config()
    genes = []
    for loc in gene_cfg.locations:
        raw_old = 0x21 if loc.index == 0 else loc.vanilla_gene_id
        # Swap indices 0 and 1 in active Run
        active_gid = 1 if loc.index == 0 else (0 if loc.index == 1 else loc.vanilla_gene_id)
        genes.append(_StubGene(index=loc.index, gene_index=active_gid, old_data={"gene_index": raw_old}))

    # Equipment & Items
    weapons = [
        _StubItem(0, "Nothing", "Nothing", price=0, old_data={"price": 0, "equipability": 0}),
        _StubItem(41, "Halberd", "Halberd", price=2350, power=48, weight=3, equipability=0x15, old_data={"price": 1800, "equipability": 0x04}),
    ]
    armors = [
        _StubItem(0, "Nothing", "Nothing", price=0, old_data={"price": 0, "equipability": 0}),
        _StubItem(7, "Chain Mail", "Chain Mail", price=900, power=22, weight=4, equip_type=4, equipability=0x05, old_data={"price": 900, "equipability": 0x05}),
    ]
    accessories = [
        _StubItem(1, "Ring of Ice", "Ring of Ice", price=1200, weight=1, equipability=0x77, old_data={"price": 1200, "equipability": 0x77}),
    ]
    items = [
        _StubItem(1, "Herb", "Herb", price=20, old_data={"price": 20}),
        _StubItem(0x38, "Piranha", "Piranha", price=40, old_data={"price": 40}),
    ]

    # Shops, Manillos, Chests
    shops = [
        _StubShop(
            index=2,
            name="Wyndia Weapon",
            item_type_item_indexes=[(41 << 8) | 1, (1 << 8) | 0],
            old_data={"item_type_item_indexes": [(1 << 8) | 0]},
        )
    ]
    manillo_stocks = [
        _StubManilloStock(index=0, trade_indexes=[0, 0xFF], old_data={"trade_indexes": [0, 0xFF]}),
    ]
    manillo_items = [
        _StubManilloItem(
            index=0,
            item_type=1,
            item_index=41,
            fish_indexes=[0, 0xFF, 0xFF],
            fish_quantities=[3, 0, 0],
            old_data={"item_type": 3, "item_index": 1, "fish_indexes": [0, 0xFF, 0xFF], "fish_quantities": [2, 0, 0]},
        )
    ]
    chests = [
        _StubChest(index=1, filename="BIN/WORLD01/AREA022.EMI", memory=1, item_type=1, item_index=41, old_data={"item_type": 0, "item_index": 1, "memory": 1}),
        _StubChest(index=2, filename="BIN/WORLD01/AREA022.EMI", memory=2, item_type=0xFF, item_index=10, old_data={"item_type": 0xFF, "item_index": 10, "memory": 2}),
    ]

    # Monsters: 1 blank dummy (000 LV 0), 2 grouped canonical Ammonite slots + 1 non-canonical dupe carrying another EMI area
    amm_a = _StubMonster(
        index=0x3A8,
        name="Ammonite",
        old_name="Ammonite",
        filename="BIN/WORLD03/AREA134.EMI",
        level=75,
        hp=2142,
        ap=100,
        pwr=202,
        dfn=75,
        agi=28,
        int=75,
        exp=5000,
        zenny=4000,
        resistances=[0, 1, 2, 3, 4, 5, 6, 7, 5],
        steal_item_type=1,
        steal_item_index=41,
        steal_rate=5,
        drop_item_type=0,
        drop_item_index=1,
        drop_rate=3,
        initial_skills=[0x0B, 0x01],
        is_boss=True,
        old_data={
            "level": 75, "hp": 1800, "ap": 100, "pwr": 180, "dfn": 75, "agi": 28, "int": 75,
            "exp": 500, "zenny": 400, "resistances": [2, 1, 2, 3, 4, 5, 6, 7, 5],
            "steal_item_type": 0, "steal_item_index": 1, "steal_rate": 3,
            "drop_item_type": 0, "drop_item_index": 1, "drop_rate": 3,
            "initial_skills": [0x0B],
        },
    )
    amm_b = _StubMonster(
        index=0x3A9,
        name="Ammonite",
        old_name="Ammonite",
        filename="BIN/WORLD03/AREA135.EMI",
        level=75,
        hp=2508,
        ap=100,
        pwr=170,
        dfn=86,
        agi=33,
        int=84,
        exp=5000,
        zenny=4000,
        resistances=[2, 2, 2, 4, 2, 4, 5, 5, 7],
        initial_skills=[0xC1],
        is_boss=True,
        old_data={
            "level": 75, "hp": 2508, "ap": 100, "pwr": 170, "dfn": 86, "agi": 33, "int": 84,
            "exp": 5000, "zenny": 4000, "resistances": [2, 2, 2, 4, 2, 4, 5, 5, 7],
            "initial_skills": [0xC1],
        },
    )
    amm_dupe = _StubMonster(
        index=0x3AA,
        name="Ammonite",
        old_name="Ammonite",
        filename="BIN/WORLD03/AREA136.EMI",
        level=75,
        hp=2142,
        ap=100,
        pwr=202,
        dfn=75,
        agi=28,
        int=75,
        exp=5000,
        zenny=4000,
        resistances=[0, 1, 2, 3, 4, 5, 6, 7, 5],
        is_canonical=False,
        canonical_relative=amm_a,
    )
    dummy_monster = _StubMonster(
        index=0x000,
        name="",
        old_name="",
        filename="BIN/WORLD01/AREA000.EMI",
        level=0,
        hp=0,
        ap=0,
        pwr=0,
        dfn=0,
        agi=0,
        int=0,
        exp=0,
        zenny=0,
        resistances=[0] * 9,
        old_data={"level": 0, "hp": 0, "ap": 0, "pwr": 0, "dfn": 0, "agi": 0, "int": 0, "resistances": [0] * 9},
    )

    equip_catalog = load_equipment_categories()
    classes = load_classes(equipment_catalog=equip_catalog)
    class_assignments = assign_archetypes(classes, equip_catalog, random.Random(42))
    master_assignments = assign_master_kits(load_master_kits(), random.Random(42))

    report = GuardrailReport()
    report.add("crash_blacklist", "Ammonite", "Replaced BadSkill (0x10, globally_banned) -> Flare (0xC1)")
    report.add("encounter_tier", "Ammonite", "[mid boss] HP 3900->2142 (van 1800)")
    report.add("weapon_access", "Shop 0x02 (Wyndia Weapon)", "[early] Added Halberd (0x29, 2350Z) for spears")

    return {
        "tables": {
            "base_stats": base_stats,
            "levels": levels,
            "master_stats": master_stats,
            "master_skills": master_skills,
            "genes": genes,
            "monsters": [dummy_monster, amm_a, amm_b, amm_dupe],
            "abilities": abilities,
            "weapons": weapons,
            "armors": armors,
            "accessories": accessories,
            "items": items,
            "key_items": [],
            "shops": shops,
            "manillo_stocks": manillo_stocks,
            "manillo_items": manillo_items,
            "chests": chests,
        },
        "configs": {
            "equipment_catalog": equip_catalog,
            "classes": classes,
        },
        "assignments": {
            "classes": class_assignments,
            "masters": master_assignments,
        },
        "guardrail_report": report,
    }


class TestCompanionWikiExporter(unittest.TestCase):
    def test_end_to_end_export_normalization_baseline_and_registry(self) -> None:
        world = _build_stub_world()
        opts = RunOptions(
            preset="standard",
            class_mode="archetypes",
            master_kits=True,
            gene_mode="tiered",
            exp_mult=10.0,
            zenny_mult=10.0,
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            res = export_companion_wiki_run(
                seed=424242,
                version="3.2-ab3",
                rom_version="BOF3_1.1",
                flags="acegmnqst",
                share_string="--preset standard --seed 424242 --exp-mult 10 --zenny-mult 10",
                options=opts,
                preset_name="Standard",
                tables=world["tables"],
                configs=world["configs"],
                assignments=world["assignments"],
                guardrail_report=world["guardrail_report"],
                output_dir=out_dir,
            )

            self.assertTrue(res.manifest_json_path.exists())
            self.assertTrue(res.manifest_js_path.exists())
            self.assertTrue(res.baseline_json_path.exists())
            self.assertTrue(res.baseline_js_path.exists())
            self.assertTrue(res.registry_js_path.exists())

            manifest = json.loads(res.manifest_json_path.read_text(encoding="utf-8"))
            baseline = json.loads(res.baseline_json_path.read_text(encoding="utf-8"))

            self.assertEqual(manifest["schema_version"], SCHEMA_VERSION)
            self.assertEqual(manifest["rom_version"], "BOF3_1.1")
            self.assertEqual(baseline["schema_version"], SCHEMA_VERSION)
            self.assertEqual(baseline["rom_version"], "BOF3_1.1")

            cats = manifest["categories"]
            bcats = baseline["categories"]

            # Characters & Classes catalog
            self.assertEqual(len(cats["characters"]), 6)
            self.assertEqual(len(bcats["characters"]), 6)
            self.assertGreaterEqual(len(cats["classes"]), 12)
            self.assertEqual(cats["characters"][0]["class_mode"], "archetypes")
            self.assertIn("grades_lv40", cats["characters"][0])

            # Masters signed int8 decoding
            bunyan = next(m for m in cats["masters"] if m["name"] == "Bunyan")
            self.assertEqual(bunyan["stats"]["ap"], -2)
            self.assertEqual(bunyan["stats"]["int"], -3)
            self.assertEqual(bcats["masters"]["bunyan"]["stats"]["pwr"], 2)

            # All 17 Dragon Genes with Flame 0x21 normalized in baseline
            self.assertEqual(len(cats["genes"]), 17)
            self.assertEqual(len(bcats["genes"]), 17)
            self.assertEqual(bcats["genes"]["00"]["gene"], "Flame")
            self.assertEqual(cats["genes"][0]["gene"], "Frost")

            # Monsters: dummy 000 stripped, 2 canonical Ammonite slots grouped into 1 logical record,
            # non-canonical dupe's area (AREA136) attached, 0..7 resistances decoded
            self.assertEqual(len(cats["monsters"]), 1)
            ammonite = cats["monsters"][0]
            self.assertEqual(ammonite["name"], "Ammonite")
            self.assertEqual(ammonite["tier"], "Mid")
            self.assertTrue(ammonite["is_boss"])
            self.assertEqual([v["slot"] for v in ammonite["variants"]], ["3A8", "3A9"])
            self.assertGreaterEqual(len(ammonite["areas"]), 3)
            self.assertIn("HP 3900->2142", ammonite["guardrail_note"])

            res_list = ammonite["variants"][0]["resistances"]
            self.assertEqual(len(res_list), 9)
            self.assertEqual(
                [r["label"] for r in res_list[:8]],
                ["Very Weak", "Weak", "Normal", "Resist", "Strong Resist", "Null", "Absorb", "Immune"],
            )
            self.assertEqual(res_list[0]["short"], "200%")
            self.assertEqual(res_list[6]["short"], "ABS")
            self.assertEqual(res_list[7]["short"], "IMM")
            self.assertIn("3A8", bcats["monsters"])
            self.assertNotIn("000", bcats["monsters"])

            # Abilities: Nothing/Noting stripped, duplicate Flare (0x5B + 0xC1) merged into 1 record
            ab_names = [a["name"] for a in cats["abilities"]]
            self.assertNotIn("Nothing", ab_names)
            self.assertNotIn("Noting", ab_names)
            self.assertEqual(ab_names.count("Flare"), 1)
            flare = next(a for a in cats["abilities"] if a["name"] == "Flare")
            self.assertEqual(flare["merged_slot_ids"], [0x5B, 0xC1])
            self.assertTrue(flare["examinable"])

            # Equipment: static combat stats on manifest, mutable-only diff fields on baseline
            halberd = next(e for e in cats["equipment"] if e["name"] == "Halberd")
            self.assertEqual(halberd["stats"]["atk"], 48)
            self.assertEqual(halberd["price"], 2350)
            self.assertTrue(halberd["changed"])
            van_halberd = bcats["equipment"][halberd["id"]]
            self.assertEqual(van_halberd["price"], 1800)
            self.assertEqual(van_halberd["equip"], ["Garr"])
            self.assertNotIn("stats", van_halberd)

            # Shops, Manillos, Chests, Guardrails
            self.assertEqual(len(cats["shops"]), 1)
            self.assertEqual(cats["shops"][0]["stock"][0]["guardrail"], "Early Guardrail")
            self.assertEqual(len(cats["manillos"]), 1)
            self.assertEqual(cats["manillos"][0]["trades"][0]["cost"], "Piranha x3")
            self.assertEqual(len(cats["chests"]), 2)
            self.assertEqual(cats["chests"][1]["item"], "400Z")
            self.assertEqual(cats["guardrails"]["crash_count"], 1)
            self.assertEqual(cats["guardrails"]["clamp_count"], 1)
            self.assertEqual(cats["guardrails"]["weapon_count"], 1)

    def test_deterministic_run_id_idempotent_update_and_auto_healing_registry(self) -> None:
        opts_a = RunOptions(preset="standard", class_mode="archetypes", exp_mult=10.0)
        opts_b = RunOptions(preset="fiesta", class_mode="roleswap", exp_mult=5.0)

        id_a1 = compute_run_id(seed=424242, version="3.2-ab3", rom_version="BOF3_1.1", flags="acegmnqst", options=opts_a)
        id_a2 = compute_run_id(seed="424242", version="3.2-ab3", rom_version="BOF3_1.1", flags="tsqnmgcea", options=opts_a)
        id_b = compute_run_id(seed=424242, version="3.2-ab3", rom_version="BOF3_1.1", flags="acegmnqst", options=opts_b)
        id_rev10 = compute_run_id(seed=424242, version="3.2-ab3", rom_version="BOF3_1.0", flags="acegmnqst", options=opts_a)

        self.assertEqual(id_a1, id_a2)
        self.assertNotEqual(id_a1, id_b)
        self.assertNotEqual(id_a1, id_rev10)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            # Export Run A twice -> idempotent overwrite, single registry entry
            r1 = export_companion_wiki_run(
                seed=424242, version="3.2-ab3", rom_version="BOF3_1.1",
                flags="acegmnqst", share_string="s1", options=opts_a, output_dir=out_dir,
            )
            r2 = export_companion_wiki_run(
                seed=424242, version="3.2-ab3", rom_version="BOF3_1.1",
                flags="acegmnqst", share_string="s1", options=opts_a, output_dir=out_dir,
            )
            self.assertEqual(r1.run_id, r2.run_id)

            # Export Run B -> 2 runs in registry
            r3 = export_companion_wiki_run(
                seed=999111, version="3.2-ab3", rom_version="BOF3_1.0",
                flags="acegmnqst", share_string="s2", options=opts_b, output_dir=out_dir,
            )
            reg_text = r3.registry_js_path.read_text(encoding="utf-8")
            self.assertIn(r1.run_id, reg_text)
            self.assertIn(r3.run_id, reg_text)
            self.assertIn("BOF3_1.1", reg_text)
            self.assertIn("BOF3_1.0", reg_text)

            # Manually delete Run A's .json -> rebuild_seed_registry heals & cleans orphan .js
            r1.manifest_json_path.unlink()
            rebuild_seed_registry(out_dir)
            self.assertFalse(r1.manifest_js_path.exists())
            healed = r3.registry_js_path.read_text(encoding="utf-8")
            self.assertNotIn(r1.run_id, healed)
            self.assertIn(r3.run_id, healed)

    def test_decode_resistance_clamps_bounds(self) -> None:
        self.assertEqual(decode_resistance(-5)["label"], "Very Weak")
        self.assertEqual(decode_resistance(99)["label"], "Immune")
        self.assertEqual(decode_resistance(2, element="Fire")["element"], "Fire")


if __name__ == "__main__":
    unittest.main()
