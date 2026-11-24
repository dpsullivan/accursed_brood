"""CLI option parsing and battle reward (EXP / Zenny / drop-rate) scaling."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

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

    exp_mult: float = 1.0
    zenny_mult: float = 1.0
    drop_mult: float = 1.0
    class_mode: Optional[str] = None
    _exp_explicit: bool = False
    _zenny_explicit: bool = False
    _drop_explicit: bool = False


def _parse_positive_float(flag: str, raw: str) -> float:
    try:
        val = float(raw)
    except ValueError as exc:
        raise ValueError(f"{flag} expects a positive number, got {raw!r}.") from exc
    if not math.isfinite(val) or val <= 0.0:
        raise ValueError(f"{flag} must be > 0, got {val!r}.")
    return val


def extract_cli_options(argv: Sequence[str]) -> Tuple[RunOptions, List[str]]:
    """Strip Accursed Brood ``--flag`` options from ``argv``.

    Returns ``(options, remaining_argv)`` so ``randomtools.interface`` still
    receives the exact positional arguments it expects.
    """
    exp_mult = 1.0
    zenny_mult = 1.0
    drop_mult = 1.0
    class_mode: Optional[str] = None
    exp_explicit = False
    zenny_explicit = False
    drop_explicit = False

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
        if key in ("--exp-mult", "--exp", "--xp"):
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
            if val not in ("archetypes", "roleswap"):
                raise ValueError(
                    f"--class-mode must be 'archetypes' or 'roleswap', got {val!r}."
                )
            class_mode = val
        else:
            remaining.append(token)
        i += 1

    return (
        RunOptions(
            exp_mult=exp_mult,
            zenny_mult=zenny_mult,
            drop_mult=drop_mult,
            class_mode=class_mode,
            _exp_explicit=exp_explicit,
            _zenny_explicit=zenny_explicit,
            _drop_explicit=drop_explicit,
        ),
        remaining,
    )


def resolve_options(
    cli_options: RunOptions, activated_codes: Sequence[str]
) -> RunOptions:
    """Merge explicit CLI flags with ``randomtools`` activated flag-string codes."""
    code_set = set(activated_codes)

    exp_mult = cli_options.exp_mult
    if not cli_options._exp_explicit:
        for code, val in _EXP_CODE_VALUES.items():
            if code in code_set:
                exp_mult = max(exp_mult, val)

    zenny_mult = cli_options.zenny_mult
    if not cli_options._zenny_explicit:
        for code, val in _ZENNY_CODE_VALUES.items():
            if code in code_set:
                zenny_mult = max(zenny_mult, val)

    class_mode = cli_options.class_mode
    if class_mode is None:
        if "archetypes" in code_set:
            class_mode = "archetypes"
        elif "roleswap" in code_set:
            class_mode = "roleswap"

    return RunOptions(
        exp_mult=exp_mult,
        zenny_mult=zenny_mult,
        drop_mult=cli_options.drop_mult,
        class_mode=class_mode,
        _exp_explicit=cli_options._exp_explicit,
        _zenny_explicit=cli_options._zenny_explicit,
        _drop_explicit=cli_options._drop_explicit,
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
