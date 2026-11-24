"""Zero-ROM unit tests for Tiered Dragon Genes (data/dragon_genes.json & genepool/genes.py)."""

from __future__ import annotations

import random
import unittest
from dataclasses import dataclass

from genepool.genes import (
    FLAME_VANILLA_RAW_BYTE,
    GENE_COUNT,
    apply_gene_assignments,
    assign_dragon_genes,
    assignments_from_gene_objects,
    format_genes_spoiler,
    load_dragon_genes_config,
    normalize_gene_index,
)


@dataclass
class _StubGeneObject:
    index: int
    gene_index: int


class TestTieredDragonGenes(unittest.TestCase):
    def test_config_loads_and_normalizes_flame_byte(self) -> None:
        config = load_dragon_genes_config()
        self.assertEqual(len(config.genes), GENE_COUNT)
        self.assertEqual(len(config.locations), GENE_COUNT)
        self.assertEqual(normalize_gene_index(FLAME_VANILLA_RAW_BYTE), 0)
        self.assertEqual(normalize_gene_index(0), 0)
        self.assertEqual(normalize_gene_index(16), 16)
        with self.assertRaises(ValueError):
            normalize_gene_index(17)

    def test_strict_tiered_mode_invariants(self) -> None:
        config = load_dragon_genes_config()
        for seed in range(1, 51):
            assignments = assign_dragon_genes(config, random.Random(seed), mode="tiered")
            self.assertEqual(len(assignments), GENE_COUNT)
            assigned_ids = [a.assigned_gene.id for a in assignments]
            self.assertEqual(sorted(assigned_ids), list(range(GENE_COUNT)))

            early_core = 0
            for a in assignments:
                self.assertEqual(
                    a.location.tier,
                    a.assigned_gene.tier,
                    f"Seed {seed}: {a.location.area_name} ({a.location.tier}) "
                    f"received {a.assigned_gene.name} ({a.assigned_gene.tier})",
                )
                if a.location.tier == "early":
                    self.assertFalse(a.assigned_gene.exclude_from_early)
                    if a.assigned_gene.core_element:
                        early_core += 1
            self.assertEqual(early_core, 3)

    def test_tiered_bleed_mode_invariants(self) -> None:
        config = load_dragon_genes_config()
        tier_rank = {t: i for i, t in enumerate(config.tier_order)}
        saw_bleed = False

        for seed in range(1, 51):
            assignments = assign_dragon_genes(
                config, random.Random(seed), mode="tiered_bleed"
            )
            self.assertEqual(len(assignments), GENE_COUNT)
            self.assertEqual(
                sorted(a.assigned_gene.id for a in assignments), list(range(GENE_COUNT))
            )

            early_core = 0
            for a in assignments:
                dist = abs(tier_rank[a.location.tier] - tier_rank[a.assigned_gene.tier])
                self.assertLessEqual(
                    dist,
                    1,
                    f"Seed {seed}: gene {a.assigned_gene.name} jumped 2 tiers!",
                )
                if dist == 1:
                    saw_bleed = True
                if a.location.tier == "early":
                    self.assertFalse(
                        a.assigned_gene.exclude_from_early,
                        f"Seed {seed}: excluded gene {a.assigned_gene.name} bled into Early!",
                    )
                    if a.assigned_gene.core_element:
                        early_core += 1
            self.assertGreaterEqual(early_core, 2)

        self.assertTrue(saw_bleed)

    def test_flat_mode_bijection_and_determinism(self) -> None:
        config = load_dragon_genes_config()
        a1 = assign_dragon_genes(config, random.Random(424242), mode="flat")
        a2 = assign_dragon_genes(config, random.Random(424242), mode="flat")
        self.assertEqual(a1, a2)
        self.assertEqual(sorted(a.assigned_gene.id for a in a1), list(range(GENE_COUNT)))
        self.assertTrue(any(a.is_cross_tier for a in a1))

    def test_apply_reconstruct_and_spoiler_format(self) -> None:
        config = load_dragon_genes_config()
        stubs = [_StubGeneObject(index=i, gene_index=FLAME_VANILLA_RAW_BYTE if i == 0 else i) for i in range(GENE_COUNT)]

        # Reconstructing vanilla objects normalizes 0x21 -> Flame (0)
        vanilla_rec = assignments_from_gene_objects(stubs, config)
        self.assertEqual(vanilla_rec[0].assigned_gene.name, "Flame")

        assignments = assign_dragon_genes(config, random.Random(999), mode="tiered_bleed")
        apply_gene_assignments(assignments, stubs)
        reconstructed = assignments_from_gene_objects(stubs, config)
        self.assertEqual(reconstructed, assignments)

        spoiler = format_genes_spoiler(reconstructed, mode="tiered_bleed", randomized=True)
        self.assertIn("Mode: tiered_bleed", spoiler)
        self.assertIn("EARLY TIER", spoiler)
        self.assertIn("MID TIER", spoiler)
        self.assertIn("LATE TIER", spoiler)
        self.assertIn("Wyndia Catacombs", spoiler)


if __name__ == "__main__":
    unittest.main()
