"""Progression-tiered Dragon Gene randomization and spoiler formatting (pure Python).

Loads the 17 randomizable Dragon Genes and their Early/Mid/Late locations from
``data/dragon_genes.json`` and supports three shuffle modes:
  - ``tiered``: strict within-tier shuffle (Early 5, Mid 7, Late 5).
  - ``tiered_bleed``: within-tier shuffle plus controlled adjacent-tier swaps
    while guaranteeing at least 2 core elemental genes in Early and keeping
    ``Failure`` out of Early.
  - ``flat``: unrestricted permutation across all 17 locations (Chaos / legacy).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .schema import DATA_DIR

DEFAULT_DRAGON_GENES_PATH = DATA_DIR / "dragon_genes.json"

GENE_COUNT = 17
FLAME_VANILLA_RAW_BYTE = 0x21
VALID_GENE_MODES: Tuple[str, ...] = ("tiered", "tiered_bleed", "flat")


@dataclass(frozen=True)
class DragonGeneSpec:
    """Metadata for one of the 17 randomizable Dragon Genes."""

    id: int
    name: str
    tier: str
    role: str
    core_element: bool
    exclude_from_early: bool
    description: str


@dataclass(frozen=True)
class GeneLocationSpec:
    """Metadata for one of the 17 ``GeneObject`` pickup locations."""

    index: int
    vanilla_gene_id: int
    vanilla_gene_name: str
    tier: str
    area_name: str
    filename: str
    has_chrysm: bool


@dataclass(frozen=True)
class GeneModeSpec:
    """Configuration parameters for a Dragon Gene shuffle mode."""

    name: str
    description: str
    cross_tier_swaps: int
    min_early_core_elements: int


@dataclass(frozen=True)
class DragonGenesConfig:
    """Validated ``data/dragon_genes.json`` configuration."""

    tier_order: Tuple[str, ...]
    modes: Dict[str, GeneModeSpec]
    genes: Tuple[DragonGeneSpec, ...]
    locations: Tuple[GeneLocationSpec, ...]

    @property
    def genes_by_id(self) -> Dict[int, DragonGeneSpec]:
        return {g.id: g for g in self.genes}

    @property
    def locations_by_index(self) -> Dict[int, GeneLocationSpec]:
        return {loc.index: loc for loc in self.locations}


@dataclass(frozen=True)
class GeneAssignment:
    """Resolved gene placement for one ``GeneObject`` index."""

    location: GeneLocationSpec
    assigned_gene: DragonGeneSpec

    @property
    def is_cross_tier(self) -> bool:
        return self.location.tier != self.assigned_gene.tier


def normalize_gene_index(raw_value: int) -> int:
    """Normalize raw ROM ``gene_index`` (converting vanilla Flame ``0x21`` -> ``0``)."""
    val = int(raw_value)
    if val == FLAME_VANILLA_RAW_BYTE:
        return 0
    if not (0 <= val < GENE_COUNT):
        raise ValueError(f"Dragon gene_index {val} (0x{val:02X}) out of range 0..{GENE_COUNT - 1}.")
    return val


def load_dragon_genes_config(
    path: Path = DEFAULT_DRAGON_GENES_PATH,
) -> DragonGenesConfig:
    """Load and validate ``data/dragon_genes.json``."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    tier_order = tuple(str(t) for t in raw["tier_order"])
    tier_set = set(tier_order)

    modes: Dict[str, GeneModeSpec] = {}
    for mname, mraw in raw["modes"].items():
        modes[str(mname)] = GeneModeSpec(
            name=str(mname),
            description=str(mraw.get("description", "")),
            cross_tier_swaps=int(mraw["cross_tier_swaps"]),
            min_early_core_elements=int(mraw["min_early_core_elements"]),
        )
    for req_mode in VALID_GENE_MODES:
        if req_mode not in modes:
            raise ValueError(f"dragon_genes.json missing required mode {req_mode!r}.")

    genes: List[DragonGeneSpec] = []
    seen_gene_ids: Set[int] = set()
    for graw in raw["genes"]:
        gid = int(graw["id"])
        tier = str(graw["tier"])
        if tier not in tier_set:
            raise ValueError(f"Gene {gid} references unknown tier {tier!r}.")
        if gid in seen_gene_ids:
            raise ValueError(f"Duplicate gene id {gid}.")
        seen_gene_ids.add(gid)
        genes.append(
            DragonGeneSpec(
                id=gid,
                name=str(graw["name"]),
                tier=tier,
                role=str(graw["role"]),
                core_element=bool(graw.get("core_element", False)),
                exclude_from_early=bool(graw.get("exclude_from_early", False)),
                description=str(graw.get("description", "")),
            )
        )

    if len(genes) != GENE_COUNT or seen_gene_ids != set(range(GENE_COUNT)):
        raise ValueError(f"Expected {GENE_COUNT} genes indexed 0..{GENE_COUNT - 1}, got {len(genes)}.")
    genes.sort(key=lambda g: g.id)

    locations: List[GeneLocationSpec] = []
    seen_loc_indices: Set[int] = set()
    for lraw in raw["locations"]:
        idx = int(lraw["index"])
        tier = str(lraw["tier"])
        if tier not in tier_set:
            raise ValueError(f"Location {idx} references unknown tier {tier!r}.")
        if idx in seen_loc_indices:
            raise ValueError(f"Duplicate gene location index {idx}.")
        seen_loc_indices.add(idx)
        locations.append(
            GeneLocationSpec(
                index=idx,
                vanilla_gene_id=int(lraw["vanilla_gene_id"]),
                vanilla_gene_name=str(lraw["vanilla_gene_name"]),
                tier=tier,
                area_name=str(lraw["area_name"]),
                filename=str(lraw["filename"]),
                has_chrysm=bool(lraw.get("has_chrysm", False)),
            )
        )

    if len(locations) != GENE_COUNT or seen_loc_indices != set(range(GENE_COUNT)):
        raise ValueError(
            f"Expected {GENE_COUNT} gene locations indexed 0..{GENE_COUNT - 1}, got {len(locations)}."
        )
    locations.sort(key=lambda loc: loc.index)

    # Verify tier cardinalities match between genes and locations
    for t in tier_order:
        g_cnt = sum(1 for g in genes if g.tier == t)
        l_cnt = sum(1 for loc in locations if loc.tier == t)
        if g_cnt != l_cnt:
            raise ValueError(
                f"Tier {t!r} cardinality mismatch: {g_cnt} genes vs {l_cnt} locations."
            )

    return DragonGenesConfig(
        tier_order=tier_order,
        modes=modes,
        genes=tuple(genes),
        locations=tuple(locations),
    )


def _perform_controlled_bleed(
    pools_by_tier: Dict[str, List[DragonGeneSpec]],
    *,
    tier_order: Tuple[str, ...],
    swaps_per_boundary: int,
    min_early_core_elements: int,
    rng: Any,
) -> None:
    """Swap up to ``swaps_per_boundary`` genes across each adjacent tier boundary."""
    if swaps_per_boundary <= 0:
        return

    early_tier = tier_order[0]
    for idx in range(len(tier_order) - 1):
        lower_tier = tier_order[idx]
        upper_tier = tier_order[idx + 1]
        lower_pool = pools_by_tier[lower_tier]
        upper_pool = pools_by_tier[upper_tier]

        for _ in range(swaps_per_boundary):
            # Candidates leaving lower_tier must preserve min_early_core_elements
            if lower_tier == early_tier:
                early_core_count = sum(1 for g in lower_pool if g.core_element)
                lower_candidates = [
                    g
                    for g in lower_pool
                    if (not g.core_element) or (early_core_count > min_early_core_elements)
                ]
                upper_candidates = [g for g in upper_pool if not g.exclude_from_early]
            else:
                # Only bleed native tier genes so no gene jumps 2 tiers (Early <-> Late)
                lower_candidates = [g for g in lower_pool if g.tier == lower_tier]
                upper_candidates = [g for g in upper_pool if g.tier == upper_tier]

            if not lower_candidates or not upper_candidates:
                break

            g_low = rng.choice(lower_candidates)
            g_up = rng.choice(upper_candidates)
            low_i = lower_pool.index(g_low)
            up_i = upper_pool.index(g_up)
            lower_pool[low_i], upper_pool[up_i] = g_up, g_low


def assign_dragon_genes(
    config: DragonGenesConfig,
    rng: Any,
    *,
    mode: str = "tiered",
) -> List[GeneAssignment]:
    """Assign all 17 Dragon Genes to the 17 locations according to ``mode``."""
    norm_mode = mode.strip().lower().replace("-", "_")
    if norm_mode not in config.modes:
        raise ValueError(
            f"Unknown gene mode {mode!r}; expected one of {VALID_GENE_MODES}."
        )
    mode_spec = config.modes[norm_mode]

    by_loc_idx: Dict[int, DragonGeneSpec] = {}
    if norm_mode == "flat":
        all_genes = list(config.genes)
        rng.shuffle(all_genes)
        for loc, gene in zip(config.locations, all_genes):
            by_loc_idx[loc.index] = gene
    else:
        pools_by_tier: Dict[str, List[DragonGeneSpec]] = {
            t: [g for g in config.genes if g.tier == t] for t in config.tier_order
        }
        _perform_controlled_bleed(
            pools_by_tier,
            tier_order=config.tier_order,
            swaps_per_boundary=mode_spec.cross_tier_swaps,
            min_early_core_elements=mode_spec.min_early_core_elements,
            rng=rng,
        )
        for t in config.tier_order:
            tier_locs = [loc for loc in config.locations if loc.tier == t]
            tier_genes = pools_by_tier[t]
            rng.shuffle(tier_genes)
            for loc, gene in zip(tier_locs, tier_genes):
                by_loc_idx[loc.index] = gene

    return [
        GeneAssignment(location=loc, assigned_gene=by_loc_idx[loc.index])
        for loc in config.locations
    ]


def apply_gene_assignments(
    assignments: Sequence[GeneAssignment],
    gene_objects: Sequence[Any],
) -> None:
    """Write canonical ``0..16`` gene indices onto ``GeneObject`` instances."""
    by_idx = {int(g.index): g for g in gene_objects}
    for assignment in assignments:
        gobj = by_idx[assignment.location.index]
        gobj.gene_index = int(assignment.assigned_gene.id)


def assignments_from_gene_objects(
    gene_objects: Sequence[Any],
    config: DragonGenesConfig,
) -> List[GeneAssignment]:
    """Reconstruct ``GeneAssignment`` records from live ``GeneObject.every``."""
    by_idx = {int(g.index): g for g in gene_objects}
    genes_by_id = config.genes_by_id
    result: List[GeneAssignment] = []
    for loc in config.locations:
        gobj = by_idx[loc.index]
        gid = normalize_gene_index(gobj.gene_index)
        result.append(GeneAssignment(location=loc, assigned_gene=genes_by_id[gid]))
    return result


def format_genes_spoiler(
    assignments: Sequence[GeneAssignment],
    *,
    mode: str = "tiered",
    randomized: bool = True,
) -> str:
    """Format the ``DRAGON GENES`` spoiler section grouped by progression tier."""
    mode_label = mode if randomized else "vanilla (not randomized)"
    lines = [f"Mode: {mode_label}"]
    tier_order = ("early", "mid", "late")
    tier_titles = {
        "early": "EARLY TIER (Child Act I)",
        "mid": "MID TIER (Child Act II / Early-Mid Adult)",
        "late": "LATE TIER (Outer Sea Endgame)",
    }

    for tier in tier_order:
        tier_entries = [a for a in assignments if a.location.tier == tier]
        if not tier_entries:
            continue
        lines.append("")
        lines.append(f"[{tier_titles[tier]}]")
        for a in tier_entries:
            bleed_tag = (
                f" [bled from {a.assigned_gene.tier.upper()}]"
                if a.is_cross_tier and randomized and mode != "flat"
                else ""
            )
            lines.append(
                f"  {a.location.index:02d} {a.location.area_name:<38} -> "
                f"{a.assigned_gene.name:<10} (was {a.location.vanilla_gene_name}){bleed_tag}"
            )
    return "\n".join(lines)
