"""Named presets loader, argv expansion, and copyable share-string formatter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .genes import VALID_GENE_MODES
from .schema import DATA_DIR

DEFAULT_PRESETS_PATH = DATA_DIR / "presets.json"
ALL_RANDOMIZER_FLAGS = "acegmnqst"


@dataclass(frozen=True)
class PresetSpec:
    """Validated named preset configuration from ``data/presets.json``."""

    id: str
    name: str
    description: str
    flags: str
    random_degree: float
    difficulty: float
    class_mode: Optional[str]
    master_kits: bool
    gene_mode: str
    crash_guard: bool
    tier_clamp: bool
    weapon_guard: bool
    exp_mult: float
    zenny_mult: float
    drop_mult: float


def load_presets(path: Path = DEFAULT_PRESETS_PATH) -> Dict[str, PresetSpec]:
    """Load and validate ``data/presets.json``."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    presets: Dict[str, PresetSpec] = {}
    for pid, praw in raw["presets"].items():
        key = str(pid).strip().lower()
        class_mode_raw = praw.get("class_mode")
        class_mode = None if class_mode_raw is None else str(class_mode_raw).strip().lower()
        if class_mode not in (None, "archetypes", "roleswap"):
            raise ValueError(f"Preset {key!r} has invalid class_mode {class_mode!r}.")
        gene_mode = str(praw["gene_mode"]).strip().lower().replace("-", "_")
        if gene_mode not in VALID_GENE_MODES:
            raise ValueError(f"Preset {key!r} has invalid gene_mode {gene_mode!r}.")
        flags = "".join(sorted(set(str(praw["flags"]).strip().lower())))
        if not flags or any(ch not in ALL_RANDOMIZER_FLAGS for ch in flags):
            raise ValueError(f"Preset {key!r} has invalid flags {flags!r}.")
        random_degree = float(praw["random_degree"])
        if not (0.0 <= random_degree <= 1.0):
            raise ValueError(f"Preset {key!r} random_degree {random_degree} out of 0..1.")
        difficulty = float(praw["difficulty"])
        if difficulty <= 0.0:
            raise ValueError(f"Preset {key!r} difficulty {difficulty} must be > 0.")
        exp_mult = float(praw.get("exp_mult", 1.0))
        zenny_mult = float(praw.get("zenny_mult", 1.0))
        drop_mult = float(praw.get("drop_mult", 1.0))
        if exp_mult <= 0.0 or zenny_mult <= 0.0 or drop_mult <= 0.0:
            raise ValueError(f"Preset {key!r} reward multipliers must be > 0.")

        presets[key] = PresetSpec(
            id=key,
            name=str(praw["name"]),
            description=str(praw.get("description", "")),
            flags=flags,
            random_degree=random_degree,
            difficulty=difficulty,
            class_mode=class_mode,
            master_kits=bool(praw["master_kits"]),
            gene_mode=gene_mode,
            crash_guard=bool(praw["crash_guard"]),
            tier_clamp=bool(praw["tier_clamp"]),
            weapon_guard=bool(praw["weapon_guard"]),
            exp_mult=exp_mult,
            zenny_mult=zenny_mult,
            drop_mult=drop_mult,
        )
    if not presets:
        raise ValueError("presets.json defines no presets.")
    return presets


def get_preset(
    name: str,
    presets: Optional[Mapping[str, PresetSpec]] = None,
) -> PresetSpec:
    """Look up a preset by case-insensitive id."""
    catalog = presets if presets is not None else load_presets()
    key = name.strip().lower()
    if key not in catalog:
        valid = ", ".join(sorted(catalog))
        raise ValueError(f"Unknown preset {name!r}. Valid presets: {valid}.")
    return catalog[key]


def apply_preset_to_argv(
    remaining_argv: Sequence[str],
    options: Any,
    presets: Optional[Mapping[str, PresetSpec]] = None,
) -> List[str]:
    """Fill missing ``randomtools.interface`` positional args from preset / named overrides.

    ``randomtools.interface.run_interface`` expects positional arguments:
        ``[script, sourcefile, flags, seed, random_degree, difficulty]``
    Explicit positional arguments already in ``remaining_argv`` are preserved.
    """
    args = list(remaining_argv)
    if len(args) < 2:
        return args

    preset_spec = (
        get_preset(options.preset, presets=presets)
        if getattr(options, "preset", None) is not None
        else None
    )
    has_positional_overrides = (
        preset_spec is not None
        or getattr(options, "flags_override", None) is not None
        or getattr(options, "seed_override", None) is not None
        or getattr(options, "randomness_override", None) is not None
        or getattr(options, "difficulty_override", None) is not None
    )
    if not has_positional_overrides:
        return args

    default_flags = preset_spec.flags if preset_spec is not None else ALL_RANDOMIZER_FLAGS
    default_randomness = preset_spec.random_degree if preset_spec is not None else 0.5
    default_difficulty = preset_spec.difficulty if preset_spec is not None else 1.0

    # Pad up to 6 slots: [script, rom, flags, seed, random_degree, difficulty]
    while len(args) < 6:
        args.append("")

    if getattr(options, "flags_override", None) is not None:
        args[2] = str(options.flags_override)
    elif not args[2]:
        args[2] = default_flags

    if getattr(options, "seed_override", None) is not None:
        args[3] = str(options.seed_override)

    if getattr(options, "randomness_override", None) is not None:
        args[4] = f"{float(options.randomness_override):g}"
    elif not args[4]:
        args[4] = f"{default_randomness:g}"

    if getattr(options, "difficulty_override", None) is not None:
        args[5] = f"{float(options.difficulty_override):g}"
    elif not args[5]:
        args[5] = f"{default_difficulty:g}"

    return args


def _fmt_float(val: float) -> str:
    return f"{float(val):g}"


def format_share_string(
    options: Any,
    *,
    flags: str,
    seed: int,
    random_degree: float,
    difficulty: float,
    presets: Optional[Mapping[str, PresetSpec]] = None,
) -> str:
    """Build a canonical, copyable CLI string that reproduces the exact run.

    Append the returned string after ``python randomizer.py "<rom.bin>" `` to
    reproduce the exact flags, seed, preset, and overrides.
    """
    norm_flags = "".join(sorted(set(flags.lower())))
    tokens: List[str] = []

    if getattr(options, "preset", None) is not None:
        preset = get_preset(options.preset, presets=presets)
        tokens.extend(["--preset", preset.id, "--seed", str(int(seed))])

        if norm_flags != preset.flags:
            tokens.extend(["--flags", norm_flags])
        if abs(float(random_degree) - preset.random_degree) > 1e-6:
            tokens.extend(["--randomness", _fmt_float(random_degree)])
        if abs(float(difficulty) - preset.difficulty) > 1e-6:
            tokens.extend(["--difficulty", _fmt_float(difficulty)])

        if options.class_mode != preset.class_mode:
            tokens.extend(["--class-mode", options.class_mode or "legacy"])
        if bool(options.master_kits) != preset.master_kits:
            tokens.append("--master-kits" if options.master_kits else "--no-master-kits")
        if options.gene_mode != preset.gene_mode:
            tokens.extend(["--gene-mode", options.gene_mode])
        if abs(float(options.exp_mult) - preset.exp_mult) > 1e-6:
            tokens.extend(["--exp-mult", _fmt_float(options.exp_mult)])
        if abs(float(options.zenny_mult) - preset.zenny_mult) > 1e-6:
            tokens.extend(["--zenny-mult", _fmt_float(options.zenny_mult)])
        if abs(float(options.drop_mult) - preset.drop_mult) > 1e-6:
            tokens.extend(["--drop-mult", _fmt_float(options.drop_mult)])
        if bool(options.crash_guard) != preset.crash_guard:
            tokens.append("--crash-guard" if options.crash_guard else "--no-crash-guard")
        if bool(options.tier_clamp) != preset.tier_clamp:
            tokens.append("--tier-clamp" if options.tier_clamp else "--no-tier-clamp")
        if bool(options.weapon_guard) != preset.weapon_guard:
            tokens.append("--weapon-guard" if options.weapon_guard else "--no-weapon-guard")
        return " ".join(tokens)

    # Non-preset canonical CLI string
    tokens.extend([
        norm_flags,
        str(int(seed)),
        _fmt_float(random_degree),
        _fmt_float(difficulty),
    ])
    if options.class_mode is not None:
        tokens.extend(["--class-mode", options.class_mode])
    if options.master_kits:
        tokens.append("--master-kits")
    if options.gene_mode != "flat":
        tokens.extend(["--gene-mode", options.gene_mode])
    if abs(float(options.exp_mult) - 1.0) > 1e-6:
        tokens.extend(["--exp-mult", _fmt_float(options.exp_mult)])
    if abs(float(options.zenny_mult) - 1.0) > 1e-6:
        tokens.extend(["--zenny-mult", _fmt_float(options.zenny_mult)])
    if abs(float(options.drop_mult) - 1.0) > 1e-6:
        tokens.extend(["--drop-mult", _fmt_float(options.drop_mult)])
    if not options.crash_guard:
        tokens.append("--no-crash-guard")
    if not options.tier_clamp:
        tokens.append("--no-tier-clamp")
    if not options.weapon_guard:
        tokens.append("--no-weapon-guard")
    return " ".join(tokens)
