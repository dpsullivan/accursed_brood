"""Schema validation and wiki-export determinism tests for data/classes.json."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genepool.growth_compiler import compile_class
from genepool.schema import (
    DEFAULT_CLASSES_PATH,
    DEFAULT_EQUIPMENT_PATH,
    LEVELUP_SPELL_CATALOG,
    MAX_SPELLS_PER_CATEGORY,
    SKILL_CATEGORIES,
    STAT_MAX_GAIN,
    STATS,
    load_classes,
    load_equipment_categories,
    parse_class_definition,
)
from genepool.wiki_export import build_wiki_payload, write_wiki_json


class TestClassDataAndWikiExport(unittest.TestCase):
    def setUp(self) -> None:
        self.equip = load_equipment_categories(DEFAULT_EQUIPMENT_PATH)
        self.classes = load_classes(DEFAULT_CLASSES_PATH, equipment_catalog=self.equip)

    def test_curated_pool_size_and_curve_diversity(self) -> None:
        self.assertGreaterEqual(len(self.classes), 10)
        self.assertLessEqual(len(self.classes), 15)
        curves = {c.curve for c in self.classes}
        self.assertEqual(curves, {"linear", "frontloaded", "late_bloomer"})

    def test_every_class_compiles_within_ps1_hardware_limits(self) -> None:
        for cls_def in self.classes:
            compiled = compile_class(cls_def)
            self.assertEqual(len(compiled.rows), 99)
            for row in compiled.rows:
                for stat in STATS:
                    val = row.stat(stat)
                    self.assertGreaterEqual(val, 0)
                    self.assertLessEqual(val, STAT_MAX_GAIN[stat])
            # Category cap <= 10 and all spell IDs verified non-examinable
            counts = {cat: 0 for cat in SKILL_CATEGORIES}
            for sp in cls_def.spells:
                self.assertIn(sp.skill, LEVELUP_SPELL_CATALOG)
                counts[sp.category] += 1
            for cat, count in counts.items():
                self.assertLessEqual(
                    count,
                    MAX_SPELLS_PER_CATEGORY,
                    f"{cls_def.id} exceeds 10 spells in {cat}",
                )

    def test_schema_rejects_duplicate_spell_levels_and_unknown_skills(self) -> None:
        bad_raw = {
            "id": "broken",
            "name": "Broken",
            "curve": "linear",
            "base_lv1": {"hp": 20, "ap": 10, "pwr": 10, "def": 10, "agl": 10, "int": 10},
            "growth_per_level": {"hp": 3.0, "ap": 2.0, "pwr": 2.0, "def": 2.0, "agl": 1.0, "int": 2.0},
            "weapons": ["swords"],
            "equipment": ["heavy_armor"],
            "spells": [
                {"level": 5, "skill": "Heal"},
                {"level": 5, "skill": "Flare"},
            ],
        }
        with self.assertRaises(ValueError):
            parse_class_definition(bad_raw, self.equip)

        bad_skill = dict(bad_raw, spells=[{"level": 5, "skill": "Nue Stomp"}])
        with self.assertRaises(ValueError):
            parse_class_definition(bad_skill, self.equip)

    def test_wiki_export_is_deterministic_and_complete(self) -> None:
        p1 = build_wiki_payload(self.classes)
        p2 = build_wiki_payload(self.classes)
        self.assertEqual(p1, p2)
        self.assertEqual(p1["project"], "Accursed Brood")
        self.assertEqual(p1["grading_level"], 40)
        self.assertEqual(p1["class_count"], len(self.classes))

        for entry in p1["classes"]:
            self.assertEqual(set(entry["totals"].keys()), {"lv1", "lv40", "lv99"})
            self.assertEqual(set(entry["grades_lv40"].keys()), set(STATS))
            self.assertEqual(
                set(entry["join_previews"].keys()),
                {"ryu", "nina", "garr", "rei", "momo", "peco"},
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "classes_wiki.json"
            write_wiki_json(output_path=out)
            reloaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(reloaded, p1)


if __name__ == "__main__":
    unittest.main()
