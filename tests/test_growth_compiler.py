"""Unit tests for the deterministic Growth Compiler and Lv 40 S-F grader."""

from __future__ import annotations

import math
import unittest

from genepool.growth_compiler import (
    NUM_LEVEL_ROWS,
    NUM_LEVEL_UPS,
    compile_class,
    compile_stat_gains,
    curve_weights,
    grade_stat_lv40,
    grade_totals_lv40,
)
from genepool.schema import (
    CURVE_SHAPES,
    STAT_MAX_GAIN,
    STATS,
    ClassDefinition,
    SpellLearn,
)


def _sample_class(curve: str = "linear", growth: dict | None = None) -> ClassDefinition:
    return ClassDefinition(
        id=f"test_{curve}",
        name="Test Class",
        role="Tester",
        description="Unit test fixture",
        base_lv1={"hp": 20, "ap": 10, "pwr": 12, "def": 10, "agl": 8, "int": 10},
        growth_per_level=growth
        or {"hp": 4.5, "ap": 2.25, "pwr": 2.5, "def": 1.75, "agl": 1.1, "int": 2.0},
        curve=curve,
        weapons=("swords",),
        equipment=("heavy_armor", "all_accessories"),
        spells=(
            SpellLearn(level=1, skill="Heal", ability_id=0x46, category="healing"),
            SpellLearn(level=5, skill="Protect", ability_id=0x52, category="assist"),
            SpellLearn(level=10, skill="Flare", ability_id=0x5B, category="attack"),
        ),
    )


class TestGrowthCompiler(unittest.TestCase):
    def test_curve_weights_conserve_total_mass(self) -> None:
        for curve in CURVE_SHAPES:
            weights = curve_weights(curve, steps=NUM_LEVEL_UPS)
            self.assertEqual(len(weights), NUM_LEVEL_UPS)
            self.assertAlmostEqual(sum(weights), float(NUM_LEVEL_UPS), places=9)

    def test_zero_rounding_drift_across_all_curves(self) -> None:
        test_rates = [0.0, 0.25, 0.5, 0.7, 1.0, 1.333, 2.5, 3.75, 5.6, 12.4]
        for curve in CURVE_SHAPES:
            for rate in test_rates:
                max_g = 255 if rate > 10 else 15
                gains = compile_stat_gains(rate, curve, max_gain=max_g)
                self.assertEqual(len(gains), NUM_LEVEL_ROWS)
                self.assertEqual(gains[0], 0, "Row 0 (Lv 1) must always have 0 stat gain.")
                expected_total = int(math.floor(NUM_LEVEL_UPS * rate + 0.5 + 1e-12))
                self.assertEqual(
                    sum(gains[1:]),
                    expected_total,
                    f"Drift detected for curve={curve}, rate={rate}",
                )
                for g in gains:
                    self.assertGreaterEqual(g, 0)
                    self.assertLessEqual(g, max_g)

    def test_nibble_ceiling_enforced_strictly(self) -> None:
        # 14.5 on a frontloaded curve peaks above 15 before clamping; compiler must
        # clamp every per-level gain to <= 15 (4-bit nibble hardware limit).
        gains = compile_stat_gains(14.5, "frontloaded", max_gain=STAT_MAX_GAIN["pwr"])
        self.assertTrue(all(0 <= g <= 15 for g in gains))
        self.assertEqual(gains[0], 0)

    def test_out_of_range_growth_raises(self) -> None:
        with self.assertRaises(ValueError):
            compile_stat_gains(15.1, "linear", max_gain=15)
        with self.assertRaises(ValueError):
            compile_stat_gains(-0.1, "linear", max_gain=15)

    def test_curve_ordering_at_lv40_with_equal_lv99_totals(self) -> None:
        front = compile_class(_sample_class("frontloaded"))
        lin = compile_class(_sample_class("linear"))
        late = compile_class(_sample_class("late_bloomer"))

        for stat in STATS:
            # All three reach identical Lv 99 totals (exact conservation)
            self.assertEqual(front.totals_lv99[stat], lin.totals_lv99[stat])
            self.assertEqual(lin.totals_lv99[stat], late.totals_lv99[stat])
            # Frontloaded > Linear > Late Bloomer at Lv 40 Myria benchmark
            self.assertGreater(front.totals_lv40[stat], lin.totals_lv40[stat])
            self.assertGreater(lin.totals_lv40[stat], late.totals_lv40[stat])

    def test_deterministic_compilation(self) -> None:
        cls = _sample_class("frontloaded")
        a = compile_class(cls)
        b = compile_class(cls)
        self.assertEqual(a.rows, b.rows)
        self.assertEqual(a.totals_lv40, b.totals_lv40)
        self.assertEqual(a.totals_lv99, b.totals_lv99)

    def test_spell_placement_in_rows(self) -> None:
        compiled = compile_class(_sample_class("linear"))
        self.assertEqual(compiled.rows[0].ability, 0x46)  # Lv 1 Heal
        self.assertEqual(compiled.rows[4].ability, 0x52)  # Lv 5 Protect
        self.assertEqual(compiled.rows[9].ability, 0x5B)  # Lv 10 Flare
        self.assertEqual(compiled.rows[1].ability, 0)

    def test_lv40_grading_matches_vanilla_benchmarks(self) -> None:
        # Vanilla Ryu Lv 40: HP 227, AP 154, PWR 144, DEF 100, AGL 49, INT 127
        ryu_grades = grade_totals_lv40(
            {"hp": 227, "ap": 154, "pwr": 144, "def": 100, "agl": 49, "int": 127}
        )
        self.assertEqual(ryu_grades, {"hp": "B", "ap": "B", "pwr": "B", "def": "B", "agl": "B", "int": "B"})
        # Vanilla Peco Lv 40 HP (333 -> S), AGL (25 -> F)
        self.assertEqual(grade_stat_lv40("hp", 333), "S")
        self.assertEqual(grade_stat_lv40("agl", 25), "F")
        # Vanilla Garr Lv 40 PWR (174 -> S), AP (29 -> F)
        self.assertEqual(grade_stat_lv40("pwr", 174), "S")
        self.assertEqual(grade_stat_lv40("ap", 29), "F")


if __name__ == "__main__":
    unittest.main()
