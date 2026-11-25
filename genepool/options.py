"""CLI option parsing, preset resolution, guardrail overrides, and reward scaling."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .genes import VALID_GENE_MODES
from .presets import PresetSpec, get_preset, load_presets

MAX_REWARD_UINT16 = 65000
MAX_DROP_RATE_EXP = 7  # 2**7 / 128 = 100%

# Substring-safe secret codes usable inside randomtools' flags argument.
REWARD_CODES: Dict[str, List[str]] = {
    "exp10x": ["exp10x", "xp10x"],
    "exp5x": ["exp5x", "xp5x"],
    "exp3x": ["exp3x", "xp3x"],
    "exp2x": ["exp2x", "xp2x"],
    "zenny10x": ["zenny10x", "z10x"],
    "zenny5x": ["zenny5x", "z5x"],
    "zenny3x": ["zenny3x", "z3x"],
    "zenny2x": ["zenny2x", "z2x"],
    "turbo10x": ["turbo10x", "fast10x"],
}

# Substring-safe guardrail override codes usable inside randomtools' flags argument.
# Longer aliases precede shorter aliases so randomtools strips the full token cleanly.
GUARDRAIL_CODES: Dict[str, List[str]] = {
    "notierclamp": ["notierclamp", "noclamp"],
    "noweaponguard": ["noweaponguard", "noweapguard"],
    "chaos": ["truechaos", "noguardrails", "chaos"],
}

# Substring-safe Phase 3 feature & preset codes usable inside randomtools' flags argument.
# Carefully chosen to avoid substring overlaps with REWARD_CODES, GUARDRAIL_CODES,
# and legacy randomizer codes (e.g. 'chaos' must not appear inside a preset alias).
FEATURE_CODES: Dict[str, List[str]] = {
    "masterkits": ["masterkits"],
    "legacymasters": ["legacymasters"],
    "tieredgenes": ["tieredgenes"],
    "bleedgenes": ["bleedgenes"],
    "flatgenes": ["flatgenes"],
}

PRESET_CODES: Dict[str, List[str]] = {
    "standardrun": ["standardrun"],
    "fiestarun": ["fiestarun"],
    "wildrun": ["wildrun"],
}

_PRESET_CODE_TO_ID: Dict[str, str] = {
    "standardrun": "standard",
    "fiestarun": "fiesta",
    "wildrun": "chaos",
}

_EXP_CODE_VALUES: Dict[str, float] = {
    "exp2x": 2.0,
    "exp3x": 3.0,
    "exp5x": 5.0,
    "exp10x": 10.0,
    "turbo10x": 10.0,
}

_ZENNY_CODE_VALUES: Dict[str, float] = {
    "zenny2x": 2.0,
    "zenny3x": 3.0,
    "zenny5x": 5.0,
    "zenny10x": 10.0,
    "turbo10x": 10.0,
}


@dataclass(frozen=True)
class RunOptions:
    """Resolved Accursed Brood runtime options."""

    preset: Optional[str] = None
    exp_mult: float = 1.0
    zenny_mult: float = 1.0
    drop_mult: float = 1.0
    class_mode: Optional[str] = None
    master_kits: bool = False
    gene_mode: str = "flat"
    crash_guard: bool = True
    tier_clamp: bool = True
    weapon_guard: bool = True
    flags_override: Optional[str] = None
    seed_override: Optional[int] = None
    randomness_override: Optional[float] = None
    difficulty_override: Optional[float] = None
    open_wiki: bool = False
    _exp_explicit: bool = False
    _zenny_explicit: bool = False
    _drop_explicit: bool = False
    _class_mode_explicit: bool = False
    _master_kits_explicit: bool = False
    _gene_mode_explicit: bool = False
    _crash_guard_explicit: bool = False
    _tier_clamp_explicit: bool = False
    _weapon_guard_explicit: bool = False


def _parse_positive_float(flag: str, raw: str) -> float:
    try:
        val = float(raw)
    except ValueError as exc:
        raise ValueError(f"{flag} expects a positive number, got {raw!r}.") from exc
    if not math.isfinite(val) or val <= 0.0:
        raise ValueError(f"{flag} must be > 0, got {val!r}.")
    return val


def _parse_unit_float(flag: str, raw: str) -> float:
    try:
        val = float(raw)
    except ValueError as exc:
        raise ValueError(f"{flag} expects a number in [0, 1], got {raw!r}.") from exc
    if not math.isfinite(val) or not (0.0 <= val <= 1.0):
        raise ValueError(f"{flag} must be between 0.0 and 1.0, got {val!r}.")
    return val


def _parse_seed_int(flag: str, raw: str) -> int:
    try:
        val = int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{flag} expects an integer seed, got {raw!r}.") from exc
    if val < 0:
        raise ValueError(f"{flag} must be >= 0, got {val!r}.")
    return val


def extract_cli_options(
    argv: Sequence[str],
    *,
    presets: Optional[Mapping[str, PresetSpec]] = None,
) -> Tuple[RunOptions, List[str]]:
    """Strip Accursed Brood ``--flag`` options from ``argv``.

    Returns ``(options, remaining_argv)`` so ``randomtools.interface`` still
    receives the exact positional arguments it expects.
    """
    preset: Optional[str] = None
    exp_mult = 1.0
    zenny_mult = 1.0
    drop_mult = 1.0
    class_mode: Optional[str] = None
    master_kits = False
    gene_mode = "flat"
    crash_guard = True
    tier_clamp = True
    weapon_guard = True
    flags_override: Optional[str] = None
    seed_override: Optional[int] = None
    randomness_override: Optional[float] = None
    difficulty_override: Optional[float] = None
    open_wiki = False

    exp_explicit = False
    zenny_explicit = False
    drop_explicit = False
    class_mode_explicit = False
    master_kits_explicit = False
    gene_mode_explicit = False
    crash_guard_explicit = False
    tier_clamp_explicit = False
    weapon_guard_explicit = False

    remaining: List[str] = []
    i = 0
    args = list(argv)
    while i < len(args):
        token = args[i]

        def _take_value(opt_name: str) -> str:
            nonlocal i
            if "=" in token:
                return token.split("=", 1)[1]
            if i + 1 >= len(args):
                raise ValueError(f"Missing value for {opt_name}.")
            i += 1
            return args[i]

        key = token.split("=", 1)[0]
        if key == "--preset":
            raw_preset = _take_value(key)
            preset_spec = get_preset(raw_preset, presets=presets)
            preset = preset_spec.id
        elif key == "--flags":
            flags_override = _take_value(key).strip().lower()
        elif key == "--seed":
            seed_override = _parse_seed_int(key, _take_value(key))
        elif key in ("--randomness", "--random-degree"):
            randomness_override = _parse_unit_float(key, _take_value(key))
        elif key == "--difficulty":
            difficulty_override = _parse_positive_float(key, _take_value(key))
        elif key in ("--exp-mult", "--exp", "--xp"):
            exp_mult = _parse_positive_float(key, _take_value(key))
            exp_explicit = True
        elif key in ("--zenny-mult", "--zenny"):
            zenny_mult = _parse_positive_float(key, _take_value(key))
            zenny_explicit = True
        elif key in ("--drop-mult", "--drop"):
            drop_mult = _parse_positive_float(key, _take_value(key))
            drop_explicit = True
        elif key == "--class-mode":
            val = _take_value(key).strip().lower()
            if val == "legacy":
                class_mode = None
            elif val in ("archetypes", "roleswap"):
                class_mode = val
            else:
                raise ValueError(
                    f"--class-mode must be 'archetypes', 'roleswap', or 'legacy', got {val!r}."
                )
            class_mode_explicit = True
        elif key == "--master-kits":
            master_kits = True
            master_kits_explicit = True
        elif key == "--no-master-kits":
            master_kits = False
            master_kits_explicit = True
        elif key == "--gene-mode":
            val = _take_value(key).strip().lower().replace("-", "_")
            if val not in VALID_GENE_MODES:
                raise ValueError(
                    f"--gene-mode must be one of {VALID_GENE_MODES}, got {val!r}."
                )
            gene_mode = val
            gene_mode_explicit = True
        elif key == "--tier-clamp":
            tier_clamp = True
            tier_clamp_explicit = True
        elif key == "--no-tier-clamp":
            tier_clamp = False
            tier_clamp_explicit = True
        elif key == "--weapon-guard":
            weapon_guard = True
            weapon_guard_explicit = True
        elif key == "--no-weapon-guard":
            weapon_guard = False
            weapon_guard_explicit = True
        elif key in ("--no-guardrails", "--chaos", "--true-chaos"):
            tier_clamp = False
            weapon_guard = False
            tier_clamp_explicit = True
            weapon_guard_explicit = True
        elif key == "--crash-guard":
            crash_guard = True
            crash_guard_explicit = True
        elif key == "--no-crash-guard":
            crash_guard = False
            crash_guard_explicit = True
        elif key == "--open-wiki":
            open_wiki = True
        elif key == "--no-open-wiki":
            open_wiki = False
        else:
            remaining.append(token)
        i += 1

    return (
        RunOptions(
            preset=preset,
            exp_mult=exp_mult,
            zenny_mult=zenny_mult,
            drop_mult=drop_mult,
            class_mode=class_mode,
            master_kits=master_kits,
            gene_mode=gene_mode,
            crash_guard=crash_guard,
            tier_clamp=tier_clamp,
            weapon_guard=weapon_guard,
            flags_override=flags_override,
            seed_override=seed_override,
            randomness_override=randomness_override,
            difficulty_override=difficulty_override,
            open_wiki=open_wiki,
            _exp_explicit=exp_explicit,
            _zenny_explicit=zenny_explicit,
            _drop_explicit=drop_explicit,
            _class_mode_explicit=class_mode_explicit,
            _master_kits_explicit=master_kits_explicit,
            _gene_mode_explicit=gene_mode_explicit,
            _crash_guard_explicit=crash_guard_explicit,
            _tier_clamp_explicit=tier_clamp_explicit,
            _weapon_guard_explicit=weapon_guard_explicit,
        ),
        remaining,
    )


def resolve_options(
    cli_options: RunOptions,
    activated_codes: Sequence[str],
    *,
    presets: Optional[Mapping[str, PresetSpec]] = None,
) -> RunOptions:
    """Merge defaults < preset < flag-string codes < explicit CLI overrides."""
    code_set = set(activated_codes)
    catalog = presets if presets is not None else load_presets()

    # 1. Resolve active preset (CLI --preset wins over flag-string preset code)
    preset_id = cli_options.preset
    if preset_id is None:
        for code, pid in _PRESET_CODE_TO_ID.items():
            if code in code_set:
                preset_id = pid
                break
    preset_spec = get_preset(preset_id, presets=catalog) if preset_id is not None else None

    # 2. Start from preset defaults (or built-in defaults if no preset)
    if preset_spec is not None:
        exp_mult = preset_spec.exp_mult
        zenny_mult = preset_spec.zenny_mult
        drop_mult = preset_spec.drop_mult
        class_mode = preset_spec.class_mode
        master_kits = preset_spec.master_kits
        gene_mode = preset_spec.gene_mode
        crash_guard = preset_spec.crash_guard
        tier_clamp = preset_spec.tier_clamp
        weapon_guard = preset_spec.weapon_guard
    else:
        exp_mult = 1.0
        zenny_mult = 1.0
        drop_mult = 1.0
        class_mode = None
        master_kits = False
        gene_mode = "flat"
        crash_guard = True
        tier_clamp = True
        weapon_guard = True

    # 3. Layer flag-string codes on top of preset defaults
    for code, val in _EXP_CODE_VALUES.items():
        if code in code_set:
            exp_mult = max(exp_mult, val)
    for code, val in _ZENNY_CODE_VALUES.items():
        if code in code_set:
            zenny_mult = max(zenny_mult, val)

    if "archetypes" in code_set:
        class_mode = "archetypes"
    elif "roleswap" in code_set:
        class_mode = "roleswap"

    if "masterkits" in code_set:
        master_kits = True
    elif "legacymasters" in code_set:
        master_kits = False

    if "tieredgenes" in code_set:
        gene_mode = "tiered"
    elif "bleedgenes" in code_set:
        gene_mode = "tiered_bleed"
    elif "flatgenes" in code_set:
        gene_mode = "flat"

    if "notierclamp" in code_set or "chaos" in code_set:
        tier_clamp = False
    if "noweaponguard" in code_set or "chaos" in code_set:
        weapon_guard = False

    # 4. Explicit CLI flags always win
    if cli_options._exp_explicit:
        exp_mult = cli_options.exp_mult
    if cli_options._zenny_explicit:
        zenny_mult = cli_options.zenny_mult
    if cli_options._drop_explicit:
        drop_mult = cli_options.drop_mult
    if cli_options._class_mode_explicit:
        class_mode = cli_options.class_mode
    if cli_options._master_kits_explicit:
        master_kits = cli_options.master_kits
    if cli_options._gene_mode_explicit:
        gene_mode = cli_options.gene_mode
    if cli_options._crash_guard_explicit:
        crash_guard = cli_options.crash_guard
    if cli_options._tier_clamp_explicit:
        tier_clamp = cli_options.tier_clamp
    if cli_options._weapon_guard_explicit:
        weapon_guard = cli_options.weapon_guard

    return RunOptions(
        preset=preset_id,
        exp_mult=exp_mult,
        zenny_mult=zenny_mult,
        drop_mult=drop_mult,
        class_mode=class_mode,
        master_kits=master_kits,
        gene_mode=gene_mode,
        crash_guard=crash_guard,
        tier_clamp=tier_clamp,
        weapon_guard=weapon_guard,
        flags_override=cli_options.flags_override,
        seed_override=cli_options.seed_override,
        randomness_override=cli_options.randomness_override,
        difficulty_override=cli_options.difficulty_override,
        open_wiki=cli_options.open_wiki,
        _exp_explicit=cli_options._exp_explicit,
        _zenny_explicit=cli_options._zenny_explicit,
        _drop_explicit=cli_options._drop_explicit,
        _class_mode_explicit=cli_options._class_mode_explicit,
        _master_kits_explicit=cli_options._master_kits_explicit,
        _gene_mode_explicit=cli_options._gene_mode_explicit,
        _crash_guard_explicit=cli_options._crash_guard_explicit,
        _tier_clamp_explicit=cli_options._tier_clamp_explicit,
        _weapon_guard_explicit=cli_options._weapon_guard_explicit,
    )


def scale_reward(
    base_value: int, multiplier: float, *, maximum: int = MAX_REWARD_UINT16
) -> int:
    """Scale a non-negative uint16 battle reward (EXP / Zenny) safely."""
    if base_value <= 0 or multiplier == 1.0:
        return base_value
    scaled = int(round(base_value * multiplier))
    return max(1, min(maximum, scaled))


def scale_drop_rate_exp(base_rate: int, multiplier: float) -> int:
    """Scale a BoF3 drop-rate exponent ``0..7`` where ``chance = 2**r / 128``."""
    if base_rate <= 0 or multiplier == 1.0:
        return base_rate
    base_chance = (2 ** base_rate) / 128.0
    target_chance = min(1.0, base_chance * multiplier)
    if target_chance <= 0.0:
        return 1
    scaled_exp = int(round(math.log2(target_chance * 128.0)))
    return max(1, min(MAX_DROP_RATE_EXP, scaled_exp))
