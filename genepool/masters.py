"""Curated Master Kits loader, validator, assigner, and ROM adapter (pure Python).

Replaces independent random stat-delta / skill draws with thematically coherent
Master Kits defined in ``data/masters.json``, while enforcing every Breath of
Fire III PS1 invariant:
  - 17 Masters total; restricted Masters (Bais, Lang, Lee, Wynn) keep their
    vanilla skills and compact single-stat bonuses untouched.
  - Every non-restricted Master's assigned stat deltas fit cleanly inside its
    ``AFLDKWA.EMI`` / ``FIRST.EMI`` menu text byte budget (zero ``???``
    fallbacks).
  - Signed int8 stat bounds (``-128..127``) and valid two's-complement packing.
  - ``Backhand`` (``0xA5``) is guaranteed on a non-restricted, non-Hondara
    Master.
  - Zero collisions with character level-up skills (even when paired with
    legacy randomized character abilities).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .schema import DATA_DIR

DEFAULT_MASTERS_PATH = DATA_DIR / "masters.json"

MASTER_STAT_ORDER: Tuple[str, ...] = ("hp", "ap", "pwr", "dfn", "agi", "int")
RESTRICTED_MASTER_NAMES: FrozenSet[str] = frozenset({"Bais", "Lang", "Lee", "Wynn"})
MAX_MASTER_SKILLS = 6
MIN_SKILL_LEVEL = 1
MAX_SKILL_LEVEL = 98
MIN_SIGNED_INT8 = -128
MAX_SIGNED_INT8 = 127
BACKHAND_SKILL_ID = 0xA5


@dataclass(frozen=True)
class MasterSkillEntry:
    """Single learnable skill entry on a Master Kit."""

    level: int
    skill_id: int
    name: str


@dataclass(frozen=True)
class MasterSlotSpec:
    """Metadata and ROM constraints for one of the 17 BoF3 Masters."""

    index: int
    name: str
    restricted: bool
    allow_backhand: bool
    max_msg_bytes: int
    vanilla_stats: Dict[str, int]


@dataclass(frozen=True)
class MasterKit:
    """Curated stat-delta and examinable skill bundle."""

    id: str
    name: str
    theme: str
    description: str
    stats: Dict[str, int]
    skills: Tuple[MasterSkillEntry, ...]

    @property
    def has_backhand(self) -> bool:
        return any(s.skill_id == BACKHAND_SKILL_ID for s in self.skills)

    @property
    def stat_sum(self) -> int:
        return sum(self.stats[k] for k in MASTER_STAT_ORDER)


@dataclass(frozen=True)
class MasterKitsConfig:
    """Validated ``data/masters.json`` catalog."""

    backhand_skill_id: int
    masters: Tuple[MasterSlotSpec, ...]
    kits: Tuple[MasterKit, ...]
    safe_fallback_skills: Tuple[Tuple[int, str], ...]

    @property
    def non_restricted_masters(self) -> Tuple[MasterSlotSpec, ...]:
        return tuple(m for m in self.masters if not m.restricted)

    @property
    def masters_by_index(self) -> Dict[int, MasterSlotSpec]:
        return {m.index: m for m in self.masters}


@dataclass(frozen=True)
class MasterKitAssignment:
    """Resolved assignment for one Master slot."""

    master: MasterSlotSpec
    kit: Optional[MasterKit]  # None for restricted Masters (kept vanilla)
    stats: Dict[str, int]
    skills: Tuple[MasterSkillEntry, ...]  # Empty tuple for restricted Masters (untouched)
    substituted_skills: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# AFLDKWA.EMI / FIRST.EMI in-place menu text length verification
# ---------------------------------------------------------------------------


def _bof3_encoded_len(text: str) -> int:
    """Return exact PS1 byte length matching ``NameMixin.convert_from_str``."""
    raw = text.encode("ascii")
    # Control tokens mirror randomizer.NameMixin.CHARSWAPS
    raw = raw.replace(b"$BLUE$", b"\x05\x03")
    raw = raw.replace(b"$RED$", b"\x05\x02")
    raw = raw.replace(b"$NOCOLOR$", b"\x06")
    raw = raw.replace(b"\n", b"\x01")
    return len(raw)


def _format_master_entry(attr: str, sign: str, value: int, *, short: bool) -> str:
    label = "Def" if attr == "dfn" else (attr.upper() if attr in ("hp", "ap") else attr[0].upper() + attr[1:])
    label = label[:2]
    color = "$BLUE$" if sign == "+" else "$RED$"
    if short:
        return f"{color}{label:2}{abs(value)}"
    return f"{color}{label:3}{sign}{abs(value)}"


def measure_master_message_bytes(stats: Mapping[str, int]) -> Tuple[int, int]:
    """Return ``(full_bytes, short_bytes)`` produced by ``rewrite_master_list()``.

    Mirrors ``randomizer.rewrite_master_list()`` exactly so we can prove before
    writing a ROM that no Master stat display overflows into ``???``.
    """
    plus: List[Optional[Tuple[str, str]]] = [
        ("+", attr) for attr in MASTER_STAT_ORDER if int(stats[attr]) > 0
    ]
    minus: List[Optional[Tuple[str, str]]] = [
        ("-", attr) for attr in MASTER_STAT_ORDER if int(stats[attr]) < 0
    ]
    plus, extra_plus = plus[:4], plus[4:]
    minus, extra_minus = minus[:4], minus[4:]
    plus += [None] * (4 - len(plus))
    minus += [None] * (4 - len(minus))
    if extra_plus:
        minus[-len(extra_plus) :] = extra_plus
    if extra_minus:
        plus[-len(extra_minus) :] = extra_minus

    full_msg = ""
    short_msg = ""
    for left, right in zip(plus, minus):
        if not (left or right):
            continue
        left_full = (
            _format_master_entry(left[1], left[0], int(stats[left[1]]), short=False)
            if left
            else "     "
        )
        right_full = (
            _format_master_entry(right[1], right[0], int(stats[right[1]]), short=False)
            if right
            else "     "
        )
        full_msg += f"{left_full} {right_full}".rstrip() + "\n"

        left_short = (
            _format_master_entry(left[1], left[0], int(stats[left[1]]), short=True)
            if left
            else "     "
        )
        right_short = (
            _format_master_entry(right[1], right[0], int(stats[right[1]]), short=True)
            if right
            else "     "
        )
        short_msg += f"{left_short} {right_short}".rstrip() + "\n"

    full_msg = full_msg.rstrip() + "$NOCOLOR$"
    short_msg = short_msg.rstrip() + "$NOCOLOR$"
    return (_bof3_encoded_len(full_msg), _bof3_encoded_len(short_msg))


def stats_fit_master_message(stats: Mapping[str, int], max_msg_bytes: int) -> bool:
    """Return True iff ``stats`` fits in full or short format without ``???``."""
    full_len, short_len = measure_master_message_bytes(stats)
    return min(full_len, short_len) <= max_msg_bytes


def to_twos_complement_byte(value: int) -> int:
    """Convert signed int8 ``-128..127`` to unsigned byte ``0..255``."""
    if not (MIN_SIGNED_INT8 <= value <= MAX_SIGNED_INT8):
        raise ValueError(f"Master stat delta {value} out of signed int8 range [-128, 127].")
    return value + 0x100 if value < 0 else value


def from_twos_complement_byte(byte_val: int) -> int:
    """Convert unsigned byte ``0..255`` to signed int8 ``-128..127``."""
    if not (0 <= byte_val <= 0xFF):
        raise ValueError(f"Master stat byte {byte_val} out of uint8 range [0, 255].")
    return byte_val - 0x100 if byte_val >= 0x80 else byte_val


# ---------------------------------------------------------------------------
# Loader & validator
# ---------------------------------------------------------------------------


def _parse_stats(raw: Mapping[str, Any], label: str) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for attr in MASTER_STAT_ORDER:
        if attr not in raw:
            raise ValueError(f"{label}: missing stat {attr!r}.")
        val = int(raw[attr])
        if not (MIN_SIGNED_INT8 <= val <= MAX_SIGNED_INT8):
            raise ValueError(f"{label}.{attr}={val} out of int8 range [-128, 127].")
        stats[attr] = val
    return stats


def load_master_kits(path: Path = DEFAULT_MASTERS_PATH) -> MasterKitsConfig:
    """Load and validate ``data/masters.json``."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    backhand_id = int(raw.get("backhand_skill_id", BACKHAND_SKILL_ID))

    masters: List[MasterSlotSpec] = []
    seen_master_indices: Set[int] = set()
    for mraw in raw["masters"]:
        idx = int(mraw["index"])
        if idx in seen_master_indices:
            raise ValueError(f"Duplicate master index {idx}.")
        seen_master_indices.add(idx)
        name = str(mraw["name"])
        restricted = bool(mraw["restricted"])
        if (name in RESTRICTED_MASTER_NAMES) != restricted:
            raise ValueError(
                f"Master {name!r} restricted flag ({restricted}) disagrees with RESTRICTED_MASTER_NAMES."
            )
        masters.append(
            MasterSlotSpec(
                index=idx,
                name=name,
                restricted=restricted,
                allow_backhand=bool(mraw["allow_backhand"]),
                max_msg_bytes=int(mraw["max_msg_bytes"]),
                vanilla_stats=_parse_stats(mraw["vanilla_stats"], f"master[{name}].vanilla_stats"),
            )
        )

    if len(masters) != 17 or seen_master_indices != set(range(17)):
        raise ValueError(f"Expected 17 masters indexed 0..16, got {len(masters)}.")

    masters.sort(key=lambda m: m.index)

    kits: List[MasterKit] = []
    seen_kit_ids: Set[str] = set()
    for kraw in raw["kits"]:
        kid = str(kraw["id"])
        if kid in seen_kit_ids:
            raise ValueError(f"Duplicate master kit id {kid!r}.")
        seen_kit_ids.add(kid)
        stats = _parse_stats(kraw["stats"], f"kit[{kid}].stats")

        raw_skills = kraw["skills"]
        if not (1 <= len(raw_skills) <= MAX_MASTER_SKILLS):
            raise ValueError(
                f"kit[{kid}] must have 1..{MAX_MASTER_SKILLS} skills, got {len(raw_skills)}."
            )
        seen_levels: Set[int] = set()
        seen_sids: Set[int] = set()
        skill_entries: List[MasterSkillEntry] = []
        for sraw in raw_skills:
            lv = int(sraw["level"])
            sid = int(sraw["skill_id"])
            sname = str(sraw["name"])
            if not (MIN_SKILL_LEVEL <= lv <= MAX_SKILL_LEVEL):
                raise ValueError(f"kit[{kid}] skill {sname!r} level {lv} out of 1..98.")
            if not (1 <= sid <= 0xE3):
                raise ValueError(f"kit[{kid}] skill {sname!r} id 0x{sid:02X} out of valid range.")
            if lv in seen_levels:
                raise ValueError(f"kit[{kid}] has duplicate learn level {lv}.")
            if sid in seen_sids:
                raise ValueError(f"kit[{kid}] has duplicate skill_id 0x{sid:02X}.")
            seen_levels.add(lv)
            seen_sids.add(sid)
            skill_entries.append(MasterSkillEntry(level=lv, skill_id=sid, name=sname))

        skill_entries.sort(key=lambda e: e.level)
        kits.append(
            MasterKit(
                id=kid,
                name=str(kraw["name"]),
                theme=str(kraw["theme"]),
                description=str(kraw["description"]),
                stats=stats,
                skills=tuple(skill_entries),
            )
        )

    non_restricted_count = sum(1 for m in masters if not m.restricted)
    if len(kits) < non_restricted_count:
        raise ValueError(
            f"Need at least {non_restricted_count} curated kits for non-restricted Masters, got {len(kits)}."
        )
    if not any(k.has_backhand for k in kits):
        raise ValueError("At least one curated Master Kit must include Backhand (0xA5).")

    fallbacks = tuple(
        (int(entry["skill_id"]), str(entry["name"]))
        for entry in raw.get("safe_fallback_skills", [])
    )
    if not fallbacks:
        raise ValueError("masters.json must provide non-empty safe_fallback_skills.")

    return MasterKitsConfig(
        backhand_skill_id=backhand_id,
        masters=tuple(masters),
        kits=tuple(kits),
        safe_fallback_skills=fallbacks,
    )


# ---------------------------------------------------------------------------
# Assignment & collision-safe skill resolution
# ---------------------------------------------------------------------------


def _resolve_kit_skills(
    kit: MasterKit,
    *,
    banned_skill_ids: FrozenSet[int],
    used_skill_ids: Set[int],
    fallback_pool: Sequence[Tuple[int, str]],
) -> Tuple[Tuple[MasterSkillEntry, ...], Tuple[str, ...]]:
    """Replace any skill that collides with character level-up skills."""
    resolved: List[MasterSkillEntry] = []
    substitutions: List[str] = []

    for entry in kit.skills:
        if entry.skill_id not in banned_skill_ids:
            resolved.append(entry)
            used_skill_ids.add(entry.skill_id)
            continue

        replacement: Optional[Tuple[int, str]] = None
        for fb_id, fb_name in fallback_pool:
            if fb_id not in banned_skill_ids and fb_id not in used_skill_ids:
                replacement = (fb_id, fb_name)
                break
        if replacement is None:
            for fb_id, fb_name in fallback_pool:
                if fb_id not in banned_skill_ids:
                    replacement = (fb_id, fb_name)
                    break
        if replacement is None:
            raise RuntimeError(
                f"No non-colliding fallback skill available for {entry.name} (0x{entry.skill_id:02X})."
            )
        fb_id, fb_name = replacement
        resolved.append(MasterSkillEntry(level=entry.level, skill_id=fb_id, name=fb_name))
        used_skill_ids.add(fb_id)
        substitutions.append(
            f"Lv{entry.level:02d} {entry.name} (0x{entry.skill_id:02X}) -> {fb_name} (0x{fb_id:02X})"
        )

    resolved.sort(key=lambda e: e.level)
    return (tuple(resolved), tuple(substitutions))


def assign_master_kits(
    config: MasterKitsConfig,
    rng: Any,
    *,
    banned_skill_ids: Iterable[int] = (),
) -> List[MasterKitAssignment]:
    """Assign curated Master Kits to all 13 non-restricted Masters deterministically.

    Invariants enforced:
      1. Restricted Masters (``Bais``, ``Lang``, ``Lee``, ``Wynn``) keep vanilla
         stats and skills untouched.
      2. Every non-restricted Master receives a unique kit whose stat deltas fit
         cleanly inside its ``max_msg_bytes`` text budget (no ``???`` fallback).
      3. ``Backhand`` (``0xA5``) is guaranteed on a non-restricted, non-Hondara
         Master (even if ``banned_skill_ids`` excludes other skills).
      4. No assigned Master skill collides with ``banned_skill_ids``.
    """
    banned = frozenset(int(sid) for sid in banned_skill_ids) - {config.backhand_skill_id}
    non_restricted = list(config.non_restricted_masters)

    # Select 13 unique kits, always including at least one Backhand-bearing kit
    backhand_kits = [k for k in config.kits if k.has_backhand]
    chosen_bh = rng.choice(backhand_kits)

    # Ensure we select enough compact kits to satisfy every tight-budget Master
    chosen_kits: List[MasterKit] = [chosen_bh]
    remaining_pool = [k for k in config.kits if k.id != chosen_bh.id]
    rng.shuffle(remaining_pool)

    # First ensure every tight master can be covered by a distinct compact kit
    min_budget = min(m.max_msg_bytes for m in non_restricted)
    tight_count = sum(1 for m in non_restricted if m.max_msg_bytes == min_budget)
    compact_selected = sum(
        1 for k in chosen_kits if stats_fit_master_message(k.stats, min_budget)
    )
    if compact_selected < tight_count:
        compact_candidates = [
            k for k in remaining_pool if stats_fit_master_message(k.stats, min_budget)
        ]
        needed = tight_count - compact_selected
        if len(compact_candidates) < needed:
            raise ValueError(
                f"Not enough compact Master Kits fitting {min_budget} bytes "
                f"(need {tight_count}, found {compact_selected + len(compact_candidates)})."
            )
        for ck in compact_candidates[:needed]:
            chosen_kits.append(ck)
            remaining_pool.remove(ck)

    while len(chosen_kits) < len(non_restricted):
        chosen_kits.append(remaining_pool.pop(0))

    # Assign constrained Masters first (smallest text budget, then Hondara) so
    # bipartite matching always succeeds without dead ends.
    def _constraint_key(m: MasterSlotSpec) -> Tuple[int, int, int]:
        return (m.max_msg_bytes, 0 if not m.allow_backhand else 1, m.index)

    ordered_masters = sorted(non_restricted, key=_constraint_key)
    available_kits = list(chosen_kits)
    rng.shuffle(available_kits)

    matched: Dict[int, MasterKit] = {}
    for master in ordered_masters:
        eligible = [
            k
            for k in available_kits
            if stats_fit_master_message(k.stats, master.max_msg_bytes)
            and (master.allow_backhand or not k.has_backhand)
        ]
        if not eligible:
            raise RuntimeError(
                f"No eligible curated Master Kit found for {master.name} "
                f"(budget={master.max_msg_bytes}B, allow_backhand={master.allow_backhand})."
            )
        pick = rng.choice(eligible)
        matched[master.index] = pick
        available_kits.remove(pick)

    # Resolve skills cleanly against character level-up collisions
    used_skill_ids: Set[int] = set()
    for kit in matched.values():
        for entry in kit.skills:
            if entry.skill_id not in banned:
                used_skill_ids.add(entry.skill_id)

    fallback_pool = list(config.safe_fallback_skills)
    rng.shuffle(fallback_pool)

    assignments: List[MasterKitAssignment] = []
    for master in config.masters:
        if master.restricted:
            assignments.append(
                MasterKitAssignment(
                    master=master,
                    kit=None,
                    stats=dict(master.vanilla_stats),
                    skills=(),
                )
            )
        else:
            kit = matched[master.index]
            resolved_skills, subs = _resolve_kit_skills(
                kit,
                banned_skill_ids=banned,
                used_skill_ids=used_skill_ids,
                fallback_pool=fallback_pool,
            )
            assignments.append(
                MasterKitAssignment(
                    master=master,
                    kit=kit,
                    stats=dict(kit.stats),
                    skills=resolved_skills,
                    substituted_skills=subs,
                )
            )

    return assignments


# ---------------------------------------------------------------------------
# Thin ROM adapter & spoiler formatting
# ---------------------------------------------------------------------------


def collect_character_levelup_skill_ids(
    level_objects: Sequence[Any],
    restricted_char_names: FrozenSet[str] = frozenset({"Teepo", "Whelp"}),
) -> FrozenSet[int]:
    """Collect all ability IDs currently on playable characters' level-up tables."""
    ids: Set[int] = set()
    for lvl in level_objects:
        aid = int(lvl.ability)
        if aid > 0 and str(lvl.charname) not in restricted_char_names:
            ids.add(aid)
    return frozenset(ids)


def apply_master_kit_assignments(
    assignments: Sequence[MasterKitAssignment],
    *,
    master_stats_cls: Any,
    master_skills_cls: Any,
    ability_cls: Any,
) -> None:
    """Write curated Master Kit stats and skills onto ``randomtools`` TableObjects."""
    for assignment in assignments:
        idx = assignment.master.index
        mstats = master_stats_cls.get(idx)
        for attr in MASTER_STAT_ORDER:
            setattr(mstats, attr, int(assignment.stats[attr]))

        if assignment.master.restricted:
            continue

        mskills = master_skills_cls.get(idx)
        skill_objs = [ability_cls.get(entry.skill_id) for entry in assignment.skills]
        levels = [entry.level for entry in assignment.skills]
        mskills.set_skills(skill_objs, levels)


def format_master_kits_spoiler(assignments: Sequence[MasterKitAssignment]) -> str:
    """Format a concise summary table of assigned curated Master Kits."""
    lines = ["=== CURATED MASTER KITS ==="]
    for a in assignments:
        if a.master.restricted or a.kit is None:
            continue
        stat_parts = []
        for attr in MASTER_STAT_ORDER:
            val = a.stats[attr]
            if val != 0:
                stat_parts.append(f"{attr.upper()}{val:+d}")
        stat_summary = " ".join(stat_parts) if stat_parts else "Neutral"
        skill_summary = ", ".join(f"Lv{s.level:02d} {s.name}" for s in a.skills)
        lines.append(
            f"  {a.master.name:<10} -> {a.kit.name:<18} ({a.kit.theme}) | "
            f"{stat_summary} | {skill_summary}"
        )
        for sub in a.substituted_skills:
            lines.append(f"      [collision avoided] {sub}")
    return "\n".join(lines)
