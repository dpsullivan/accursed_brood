"""Anti-softlock guardrails for Accursed Brood (pure Python, ROM-independent).

Covers three data-driven pillars loaded from ``data/*.json``:
  A. Crash Blacklist (``data/crash_blacklist.json``): prevents globally banned,
     dragon-form-only, boss-only, and incompatible-animation skills from
     entering enemy AI pools, with a post-randomization sanitizer pass.
  B. Tiered Enemy & Mandatory Boss Scaling (``data/encounter_tiers.json``):
     clamps Early/Mid/Late stat & resistance variance and protects scripted
     or unwinnable encounters.
  C. Weapon Accessibility Guardrail (``data/equipment_categories.json``):
     ensures every active party weapon category and character has affordable
     early-tier and mid-tier weapons in accessible shops without exceeding
     the PS1 11-item shop limit or displacing protected story items.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .schema import DATA_DIR, DEFAULT_EQUIPMENT_PATH, PLAYABLE_CHARACTERS

DEFAULT_CRASH_BLACKLIST_PATH = DATA_DIR / "crash_blacklist.json"
DEFAULT_ENCOUNTER_TIERS_PATH = DATA_DIR / "encounter_tiers.json"

MONSTER_COMBAT_STATS: Tuple[str, ...] = ("hp", "ap", "pwr", "dfn", "agi", "int")
MAX_MONSTER_HP = 65000
MAX_MONSTER_STAT = 0xFFFE
_AREA_CODE_RE = re.compile(r"AREA(\d{3})\.EMI", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Structured intervention reporting (for spoiler logs & verification)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GuardrailIntervention:
    """A single guardrail adjustment recorded for spoiler reporting."""

    pillar: str  # "crash_blacklist" | "encounter_tier" | "weapon_access"
    subject: str
    detail: str


@dataclass
class GuardrailReport:
    """Aggregated log of all guardrail actions during a randomization run."""

    crash_guard_enabled: bool = True
    tier_clamp_enabled: bool = True
    weapon_guard_enabled: bool = True
    interventions: List[GuardrailIntervention] = field(default_factory=list)

    def add(self, pillar: str, subject: str, detail: str) -> None:
        self.interventions.append(
            GuardrailIntervention(pillar=pillar, subject=subject, detail=detail)
        )

    def by_pillar(self, pillar: str) -> List[GuardrailIntervention]:
        return [iv for iv in self.interventions if iv.pillar == pillar]


# ---------------------------------------------------------------------------
# Pillar A: Crash Blacklist
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrashBlacklist:
    """Data-driven skill ban rules and safe fallback IDs."""

    globally_banned_ids: FrozenSet[int]
    globally_banned_names: Tuple[str, ...]
    global_native_boss_owners: Dict[int, FrozenSet[str]]
    levelup_banned_ids: FrozenSet[int]
    levelup_banned_names: Tuple[str, ...]
    dragon_form_banned_ids: FrozenSet[int]
    boss_only_ids: FrozenSet[int]
    boss_only_native_owners: Dict[int, FrozenSet[str]]
    species_locked_owners: Dict[int, FrozenSet[str]]
    enemy_specific_bans: Dict[str, FrozenSet[int]]
    safe_fallbacks: Dict[str, Tuple[int, ...]]

    def is_skill_forbidden(
        self,
        skill_id: int,
        *,
        monster_name: str,
        is_boss: bool,
    ) -> Optional[str]:
        """Return a reason string if ``skill_id`` is disallowed for this monster."""
        if skill_id <= 0:
            return None

        if skill_id in self.dragon_form_banned_ids:
            return "dragon_form_skill"

        if skill_id in self.globally_banned_ids:
            if is_boss and monster_name in self.global_native_boss_owners.get(
                skill_id, frozenset()
            ):
                return None
            return "globally_banned"

        if skill_id in self.enemy_specific_bans.get(monster_name, frozenset()):
            return "enemy_specific_ban"

        if not is_boss and skill_id in self.boss_only_ids:
            return "boss_only_skill"

        if skill_id in self.species_locked_owners:
            if monster_name not in self.species_locked_owners[skill_id]:
                return "species_locked_animation"

        return None

    def is_candidate_allowed(
        self,
        skill_id: int,
        *,
        monster_name: str,
        is_boss: bool = False,
    ) -> bool:
        return (
            self.is_skill_forbidden(
                skill_id, monster_name=monster_name, is_boss=is_boss
            )
            is None
        )


def load_crash_blacklist(
    path: Path = DEFAULT_CRASH_BLACKLIST_PATH,
) -> CrashBlacklist:
    """Load and validate ``data/crash_blacklist.json``."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    globally_banned_ids: Set[int] = set()
    globally_banned_names: List[str] = []
    global_native_boss_owners: Dict[int, FrozenSet[str]] = {}
    for entry in raw.get("globally_banned_skills", []):
        sid = int(entry["id"])
        globally_banned_ids.add(sid)
        globally_banned_names.append(str(entry["name"]))
        global_native_boss_owners[sid] = frozenset(
            str(n) for n in entry.get("native_boss_owners", [])
        )

    levelup_banned_ids: Set[int] = set()
    levelup_banned_names: List[str] = []
    for entry in raw.get("levelup_banned_skills", []):
        levelup_banned_ids.add(int(entry["id"]))
        levelup_banned_names.append(str(entry["name"]))

    dragon_form_banned_ids = frozenset(
        int(entry["id"]) for entry in raw.get("dragon_form_banned_skills", [])
    )

    boss_only_ids: Set[int] = set()
    boss_only_native_owners: Dict[int, FrozenSet[str]] = {}
    for entry in raw.get("boss_only_skills", []):
        sid = int(entry["id"])
        boss_only_ids.add(sid)
        boss_only_native_owners[sid] = frozenset(
            str(n) for n in entry.get("native_boss_owners", [])
        )

    species_locked_owners: Dict[int, FrozenSet[str]] = {}
    for entry in raw.get("species_locked_skills", []):
        sid = int(entry["id"])
        species_locked_owners[sid] = frozenset(
            str(n) for n in entry.get("native_owners", [])
        )

    enemy_specific_bans = {
        str(name): frozenset(int(sid) for sid in ids)
        for name, ids in raw.get("enemy_specific_bans", {}).items()
    }

    safe_fallbacks: Dict[str, Tuple[int, ...]] = {}
    for cat in ("attack", "assist", "healing"):
        vals = tuple(int(sid) for sid in raw.get("safe_fallbacks", {}).get(cat, []))
        if not vals:
            raise ValueError(f"crash_blacklist.json missing safe_fallbacks[{cat!r}].")
        safe_fallbacks[cat] = vals

    return CrashBlacklist(
        globally_banned_ids=frozenset(globally_banned_ids),
        globally_banned_names=tuple(globally_banned_names),
        global_native_boss_owners=global_native_boss_owners,
        levelup_banned_ids=frozenset(levelup_banned_ids),
        levelup_banned_names=tuple(levelup_banned_names),
        dragon_form_banned_ids=dragon_form_banned_ids,
        boss_only_ids=frozenset(boss_only_ids),
        boss_only_native_owners=boss_only_native_owners,
        species_locked_owners=species_locked_owners,
        enemy_specific_bans=enemy_specific_bans,
        safe_fallbacks=safe_fallbacks,
    )


def classify_ability_category(ability: Any) -> str:
    """Map an AbilityObject (or duck-typed stub) to 'attack', 'assist', or 'healing'."""
    if ability is None:
        return "attack"
    if hasattr(ability, "is_utility") and hasattr(ability, "is_offense"):
        if ability.is_utility:
            return "assist"
        if ability.is_offense:
            return "attack"
        return "healing"
    st = int(getattr(ability, "skill_type", 2)) & 0x03
    if st == 0:
        return "healing"
    if st == 1:
        return "assist"
    return "attack"


def filter_enemy_skill_candidates(
    candidates: Sequence[Any],
    *,
    monster_name: str,
    is_boss: bool,
    blacklist: CrashBlacklist,
) -> List[Any]:
    """Filter candidate ``AbilityObject``s to those safe for ``monster_name``."""
    return [
        c
        for c in candidates
        if blacklist.is_candidate_allowed(
            int(c.index), monster_name=monster_name, is_boss=is_boss
        )
    ]


def choose_safe_fallback_skill(
    bad_ability: Any,
    *,
    monster_name: str,
    is_boss: bool,
    blacklist: CrashBlacklist,
    abilities_by_id: Mapping[int, Any],
    rng: Optional[Any] = None,
) -> int:
    """Pick a safe, same-category replacement skill ID for a blacklisted ability."""
    category = classify_ability_category(bad_ability)
    preferred_ids = list(blacklist.safe_fallbacks.get(category, ()))
    valid = [
        sid
        for sid in preferred_ids
        if sid in abilities_by_id
        and blacklist.is_candidate_allowed(
            sid, monster_name=monster_name, is_boss=is_boss
        )
    ]
    if not valid:
        # Broaden to any category's safe fallback if a stubbed test omits a subset
        for fallback_cat in ("attack", "assist", "healing"):
            for sid in blacklist.safe_fallbacks.get(fallback_cat, ()):
                if sid in abilities_by_id and blacklist.is_candidate_allowed(
                    sid, monster_name=monster_name, is_boss=is_boss
                ):
                    valid.append(sid)
    if not valid:
        # Final fallback: any non-zero safe ability in abilities_by_id
        for sid in sorted(abilities_by_id):
            if sid > 0 and blacklist.is_candidate_allowed(
                sid, monster_name=monster_name, is_boss=is_boss
            ):
                valid.append(sid)
                break
    if not valid:
        return 0

    if rng is not None:
        return int(rng.choice(valid))
    bad_id = int(getattr(bad_ability, "index", 0)) if bad_ability is not None else 0
    pick_idx = (bad_id + sum(ord(ch) for ch in monster_name)) % len(valid)
    return int(valid[pick_idx])


def sanitize_monster_skills(
    monster: Any,
    *,
    abilities_by_id: Mapping[int, Any],
    blacklist: CrashBlacklist,
    rng: Optional[Any] = None,
    sanitize_inactive_phases: bool = False,
) -> List[GuardrailIntervention]:
    """Strip any blacklisted ability from a monster's AI slots with safe fallbacks.

    Only active AI slots (``initial_skills`` and ``skills1..4`` with
    ``condition < 99``) are sanitized by default, matching BoF3's battle engine
    and ``MonsterObject.abilities``.
    """
    monster_name = str(monster.name)
    is_boss = bool(monster.is_boss)

    slot_attrs: List[str] = ["initial_skills"]
    for phase in range(1, 5):
        cond_attr = f"condition{phase}"
        skills_attr = f"skills{phase}"
        if not hasattr(monster, skills_attr):
            continue
        cond = int(getattr(monster, cond_attr, 99))
        if sanitize_inactive_phases or cond < 99:
            slot_attrs.append(skills_attr)

    replacements: Dict[int, Tuple[int, str]] = {}
    interventions: List[GuardrailIntervention] = []

    for attr in slot_attrs:
        raw_skills = list(getattr(monster, attr))
        changed = False
        for i, sid in enumerate(raw_skills):
            sid_int = int(sid)
            if sid_int <= 0:
                continue
            reason = blacklist.is_skill_forbidden(
                sid_int, monster_name=monster_name, is_boss=is_boss
            )
            if reason is None:
                continue
            if sid_int not in replacements:
                bad_ab = abilities_by_id.get(sid_int)
                safe_id = choose_safe_fallback_skill(
                    bad_ab,
                    monster_name=monster_name,
                    is_boss=is_boss,
                    blacklist=blacklist,
                    abilities_by_id=abilities_by_id,
                    rng=rng,
                )
                replacements[sid_int] = (safe_id, reason)
            raw_skills[i] = replacements[sid_int][0]
            changed = True
        if changed:
            setattr(monster, attr, raw_skills)

    for bad_id, (safe_id, reason) in sorted(replacements.items()):
        bad_ab = abilities_by_id.get(bad_id)
        safe_ab = abilities_by_id.get(safe_id)
        bad_name = getattr(bad_ab, "name", f"0x{bad_id:02X}") if bad_ab is not None else f"0x{bad_id:02X}"
        safe_name = getattr(safe_ab, "name", f"0x{safe_id:02X}") if safe_ab is not None else f"0x{safe_id:02X}"
        interventions.append(
            GuardrailIntervention(
                pillar="crash_blacklist",
                subject=monster_name,
                detail=(
                    f"Replaced {bad_name} (0x{bad_id:02X}, {reason}) "
                    f"-> {safe_name} (0x{safe_id:02X})"
                ),
            )
        )

    return interventions


# ---------------------------------------------------------------------------
# Pillar B: Tiered Enemy & Mandatory Boss Scaling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProtectedEncounterRule:
    """Rule locking a scripted/tutorial/unwinnable encounter to vanilla stats."""

    name: str
    area_codes: Optional[FrozenSet[int]]
    reason: str


@dataclass(frozen=True)
class StatClampSpec:
    """Per-tier stat multiplier bounds and resistance variance limits."""

    stat_bounds: Dict[str, Tuple[float, float]]
    resistance_max_delta: int
    resistance_cap: int
    small_stat_headroom: int = 0


@dataclass(frozen=True)
class TierSpec:
    """Progression tier metadata and boss/enemy clamp specifications."""

    name: str
    description: str
    area_codes: FrozenSet[int]
    boss_names: FrozenSet[str]
    boss_clamps: StatClampSpec
    enemy_clamps: StatClampSpec


@dataclass(frozen=True)
class EncounterTiersConfig:
    """Complete encounter tier configuration from ``data/encounter_tiers.json``."""

    protect_max_hp_sentinels: bool
    max_hp_sentinel_threshold: int
    protected_encounters: Tuple[ProtectedEncounterRule, ...]
    tier_order: Tuple[str, ...]
    tiers: Dict[str, TierSpec]

    def classify_monster(
        self,
        monster_name: str,
        *,
        is_boss: bool,
        old_hp: int,
        area_codes: Iterable[int] = (),
    ) -> Tuple[str, Optional[str]]:
        """Classify a monster as ``('protected', reason)`` or ``(tier_name, None)``."""
        area_set = set(area_codes)

        if self.protect_max_hp_sentinels and old_hp >= self.max_hp_sentinel_threshold:
            return ("protected", f"max_hp_sentinel ({old_hp})")

        for rule in self.protected_encounters:
            if rule.name == monster_name:
                if rule.area_codes is None or not area_set or bool(area_set & rule.area_codes):
                    return ("protected", rule.reason)

        if is_boss:
            for tier_name in self.tier_order:
                if monster_name in self.tiers[tier_name].boss_names:
                    return (tier_name, None)

        for tier_name in self.tier_order:
            if area_set & self.tiers[tier_name].area_codes:
                return (tier_name, None)

        return (self.tier_order[-1], None)


def _parse_clamp_spec(raw: Mapping[str, Any], label: str) -> StatClampSpec:
    bounds: Dict[str, Tuple[float, float]] = {}
    for stat in MONSTER_COMBAT_STATS:
        pair = raw[stat]
        lo, hi = float(pair[0]), float(pair[1])
        if lo <= 0.0 or hi < lo:
            raise ValueError(f"{label}.{stat} has invalid clamp range [{lo}, {hi}].")
        bounds[stat] = (lo, hi)
    max_delta = int(raw["resistance_max_delta"])
    cap = int(raw["resistance_cap"])
    if not (0 <= max_delta <= 7) or not (0 <= cap <= 7):
        raise ValueError(f"{label} resistance limits out of 0..7 range.")
    headroom = int(raw.get("small_stat_headroom", 0))
    if headroom < 0:
        raise ValueError(f"{label}.small_stat_headroom must be >= 0, got {headroom}.")
    return StatClampSpec(
        stat_bounds=bounds,
        resistance_max_delta=max_delta,
        resistance_cap=cap,
        small_stat_headroom=headroom,
    )


def load_encounter_tiers(
    path: Path = DEFAULT_ENCOUNTER_TIERS_PATH,
) -> EncounterTiersConfig:
    """Load and validate ``data/encounter_tiers.json``."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    protected: List[ProtectedEncounterRule] = []
    for entry in raw.get("protected_encounters", []):
        raw_areas = entry.get("area_codes")
        area_codes = (
            frozenset(int(a) for a in raw_areas) if raw_areas is not None else None
        )
        protected.append(
            ProtectedEncounterRule(
                name=str(entry["name"]),
                area_codes=area_codes,
                reason=str(entry.get("reason", "scripted encounter")),
            )
        )

    tier_order = tuple(str(t) for t in raw["tier_order"])
    tiers: Dict[str, TierSpec] = {}
    for tname in tier_order:
        traw = raw["tiers"][tname]
        tiers[tname] = TierSpec(
            name=tname,
            description=str(traw.get("description", "")),
            area_codes=frozenset(int(a) for a in traw.get("area_codes", [])),
            boss_names=frozenset(str(n) for n in traw.get("boss_names", [])),
            boss_clamps=_parse_clamp_spec(traw["boss_clamps"], f"{tname}.boss_clamps"),
            enemy_clamps=_parse_clamp_spec(traw["enemy_clamps"], f"{tname}.enemy_clamps"),
        )

    return EncounterTiersConfig(
        protect_max_hp_sentinels=bool(raw.get("protect_max_hp_sentinels", True)),
        max_hp_sentinel_threshold=int(raw.get("max_hp_sentinel_threshold", 65535)),
        protected_encounters=tuple(protected),
        tier_order=tier_order,
        tiers=tiers,
    )


def extract_area_code(filename: Optional[str]) -> Optional[int]:
    """Extract numeric area code (e.g. ``22`` from ``AREA022.EMI``)."""
    if not filename:
        return None
    m = _AREA_CODE_RE.search(str(filename))
    return int(m.group(1)) if m else None


def collect_canonical_area_codes(monsters: Sequence[Any]) -> Dict[int, FrozenSet[int]]:
    """Map each canonical monster's index to all ``AREA###.EMI`` codes it occupies."""
    by_canon: Dict[int, Set[int]] = {}
    for m in monsters:
        canon = getattr(m, "canonical_relative", m)
        cid = int(canon.index)
        code = extract_area_code(getattr(m, "filename", None))
        if code is not None:
            by_canon.setdefault(cid, set()).add(code)
    return {cid: frozenset(codes) for cid, codes in by_canon.items()}


def clamp_stat_value(
    current: int,
    vanilla: int,
    min_mult: float,
    max_mult: float,
    *,
    max_hardware: int = MAX_MONSTER_STAT,
    small_stat_headroom: int = 0,
) -> int:
    """Clamp a single monster stat within ``[min_mult, max_mult]`` of ``vanilla``.

    When ``small_stat_headroom > 0``, the upper bound is at least
    ``vanilla + small_stat_headroom`` (for positive vanilla stats) so very small
    early-game stats still have gentle room to vary.
    """
    if vanilla <= 0:
        return 0
    low = max(1, int(math.floor(vanilla * min_mult)))
    high = min(
        max_hardware,
        max(vanilla + max(0, int(small_stat_headroom)), int(math.ceil(vanilla * max_mult))),
    )
    if low > high:
        low = high
    return max(low, min(high, int(current)))


def clamp_resistances(
    current: Sequence[int],
    vanilla: Sequence[int],
    *,
    max_delta: int,
    cap: int,
) -> List[int]:
    """Clamp elemental & status resistances (0..7) around vanilla values."""
    clamped: List[int] = []
    for cur, van in zip(current, vanilla):
        van_i = int(van)
        cur_i = int(cur)
        lo = max(0, van_i - max_delta)
        hi = min(7, max(van_i, min(cap, van_i + max_delta)))
        clamped.append(max(lo, min(hi, cur_i)))
    return clamped


def apply_monster_tier_clamps(
    monster: Any,
    *,
    area_codes: Iterable[int],
    config: EncounterTiersConfig,
) -> Optional[GuardrailIntervention]:
    """Apply protected-encounter restoration or tier stat clamps to a canonical monster."""
    monster_name = str(monster.name)
    is_boss = bool(monster.is_boss)
    old_data = monster.old_data
    old_hp = int(old_data["hp"])

    tier_name, reason = config.classify_monster(
        monster_name,
        is_boss=is_boss,
        old_hp=old_hp,
        area_codes=area_codes,
    )

    changes: List[str] = []

    if tier_name == "protected":
        for stat in MONSTER_COMBAT_STATS:
            cur_val = int(getattr(monster, stat))
            van_val = int(old_data[stat])
            if cur_val != van_val:
                setattr(monster, stat, van_val)
                changes.append(f"{stat.upper()} {cur_val}->{van_val}")
        old_res = [int(r) for r in old_data["resistances"]]
        cur_res = [int(r) for r in monster.resistances]
        if cur_res != old_res:
            monster.resistances = list(old_res)
            changes.append("resistances restored")
        if changes:
            return GuardrailIntervention(
                pillar="encounter_tier",
                subject=monster_name,
                detail=f"[protected: {reason}] {', '.join(changes)}",
            )
        return None

    tier_spec = config.tiers[tier_name]
    clamp_spec = tier_spec.boss_clamps if is_boss else tier_spec.enemy_clamps

    for stat in MONSTER_COMBAT_STATS:
        cur_val = int(getattr(monster, stat))
        van_val = int(old_data[stat])
        lo_m, hi_m = clamp_spec.stat_bounds[stat]
        hw_max = max(MAX_MONSTER_HP, van_val) if stat == "hp" else max(MAX_MONSTER_STAT, van_val)
        new_val = clamp_stat_value(
            cur_val,
            van_val,
            lo_m,
            hi_m,
            max_hardware=hw_max,
            small_stat_headroom=clamp_spec.small_stat_headroom,
        )
        if new_val != cur_val:
            setattr(monster, stat, new_val)
            changes.append(f"{stat.upper()} {cur_val}->{new_val} (van {van_val})")

    old_res = [int(r) for r in old_data["resistances"]]
    cur_res = [int(r) for r in monster.resistances]
    new_res = clamp_resistances(
        cur_res,
        old_res,
        max_delta=clamp_spec.resistance_max_delta,
        cap=clamp_spec.resistance_cap,
    )
    if new_res != cur_res:
        monster.resistances = new_res
        changes.append(f"RES {cur_res}->{new_res}")

    if changes:
        role_tag = "boss" if is_boss else "enemy"
        return GuardrailIntervention(
            pillar="encounter_tier",
            subject=monster_name,
            detail=f"[{tier_name} {role_tag}] {', '.join(changes)}",
        )
    return None


# ---------------------------------------------------------------------------
# Pillar C: Weapon Accessibility Guardrail
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeaponAccessibilityConfig:
    """Shop and weapon progression tier definitions from ``data/equipment_categories.json``."""

    weapons_by_category: Dict[str, Tuple[int, ...]]
    weapon_tiers: Dict[str, Dict[str, Tuple[int, ...]]]
    max_items_per_shop: int
    early_max_price: int
    mid_max_price: int
    excluded_weapon_ids: FrozenSet[int]
    protected_shop_items: Dict[int, FrozenSet[Tuple[int, int]]]
    faerie_shop_ids: FrozenSet[int]
    early_shops: Tuple[int, ...]
    early_injection_priority: Tuple[int, ...]
    mid_shops: Tuple[int, ...]
    mid_injection_priority: Tuple[int, ...]

    def category_of_weapon(self, weapon_id: int) -> Optional[str]:
        for cat, ids in self.weapons_by_category.items():
            if weapon_id in ids:
                return cat
        return None


def load_weapon_accessibility_config(
    path: Path = DEFAULT_EQUIPMENT_PATH,
) -> WeaponAccessibilityConfig:
    """Load weapon and shop tier metadata from ``data/equipment_categories.json``."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    weapons_by_category = {
        str(cat): tuple(int(wid) for wid in ids)
        for cat, ids in raw["weapons"].items()
    }
    weapon_tiers: Dict[str, Dict[str, Tuple[int, ...]]] = {}
    for cat, tier_map in raw["weapon_tiers"].items():
        weapon_tiers[str(cat)] = {
            "early": tuple(int(wid) for wid in tier_map["early"]),
            "mid": tuple(int(wid) for wid in tier_map["mid"]),
        }

    st = raw["shop_tiers"]
    protected_shop_items: Dict[int, FrozenSet[Tuple[int, int]]] = {}
    for shop_id_str, entries in st.get("protected_shop_items", {}).items():
        protected_shop_items[int(shop_id_str)] = frozenset(
            (int(e["item_type"]), int(e["item_index"])) for e in entries
        )

    return WeaponAccessibilityConfig(
        weapons_by_category=weapons_by_category,
        weapon_tiers=weapon_tiers,
        max_items_per_shop=int(st.get("max_items_per_shop", 11)),
        early_max_price=int(st.get("early_max_price", 2500)),
        mid_max_price=int(st.get("mid_max_price", 10000)),
        excluded_weapon_ids=frozenset(int(wid) for wid in st.get("excluded_weapon_ids", [])),
        protected_shop_items=protected_shop_items,
        faerie_shop_ids=frozenset(int(sid) for sid in st.get("faerie_shop_ids", [])),
        early_shops=tuple(int(sid) for sid in st["early_shops"]),
        early_injection_priority=tuple(int(sid) for sid in st["early_injection_priority"]),
        mid_shops=tuple(int(sid) for sid in st["mid_shops"]),
        mid_injection_priority=tuple(int(sid) for sid in st["mid_injection_priority"]),
    )


def _default_item_type(item: Any) -> int:
    if hasattr(item, "item_type"):
        return int(item.item_type)
    cls_name = type(item).__name__
    if "Weapon" in cls_name:
        return 1
    if "Armor" in cls_name:
        return 2
    if "Accessory" in cls_name:
        return 3
    return 0


def _active_items(shop: Any) -> List[Any]:
    return [item for item in shop.items if item is not None and int(item.index) > 0]


def _ensure_affordable(
    weapon: Any,
    max_price: int,
    *,
    tier: str,
    interventions: List[GuardrailIntervention],
) -> None:
    cur_price = int(weapon.price)
    if cur_price > max_price:
        old_price = int(weapon.old_data["price"])
        new_price = min(max_price, max(old_price, int(round(old_price * 1.5))))
        if new_price <= 0:
            new_price = max_price
        weapon.price = new_price
        interventions.append(
            GuardrailIntervention(
                pillar="weapon_access",
                subject=str(weapon.name),
                detail=f"[{tier} affordability] Price {cur_price}Z -> {new_price}Z (cap {max_price}Z)",
            )
        )


def _inject_weapon_into_tier_shops(
    weapon: Any,
    *,
    tier: str,
    reason: str,
    inject_order: Sequence[int],
    tier_shop_ids: Sequence[int],
    shops_by_id: Mapping[int, Any],
    config: WeaponAccessibilityConfig,
    injected_slots: Set[Tuple[int, int]],
    item_type_of: Callable[[Any], int],
    interventions: List[GuardrailIntervention],
) -> bool:
    """Insert ``weapon`` into the best shop in ``inject_order`` without overflowing 11 slots."""
    # Pass 1: prefer a shop with an open slot (< 11 items)
    for shop_id in inject_order:
        if shop_id in config.faerie_shop_ids or shop_id not in shops_by_id:
            continue
        shop = shops_by_id[shop_id]
        items = _active_items(shop)
        if any(item_type_of(it) == 1 and int(it.index) == int(weapon.index) for it in items):
            injected_slots.add((shop_id, int(weapon.index)))
            return True
        if len(items) < config.max_items_per_shop:
            items.append(weapon)
            shop.set_items(items)
            injected_slots.add((shop_id, int(weapon.index)))
            interventions.append(
                GuardrailIntervention(
                    pillar="weapon_access",
                    subject=f"Shop 0x{shop_id:02X} ({getattr(shop, 'name', shop_id)})",
                    detail=f"[{tier}] Added {weapon.name} (0x{weapon.index:02X}, {weapon.price}Z) for {reason}",
                )
            )
            return True

    # Pass 2: all shops are full (11/11); cleanly replace the safest non-protected slot
    # Count weapon category representation across all shops in this tier
    cat_counts: Dict[str, int] = {}
    for sid in tier_shop_ids:
        if sid not in shops_by_id:
            continue
        for it in _active_items(shops_by_id[sid]):
            if item_type_of(it) == 1:
                cat = config.category_of_weapon(int(it.index))
                if cat:
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1

    for shop_id in inject_order:
        if shop_id in config.faerie_shop_ids or shop_id not in shops_by_id:
            continue
        shop = shops_by_id[shop_id]
        items = _active_items(shop)
        protected = config.protected_shop_items.get(shop_id, frozenset())

        # Count duplicates inside this shop
        key_counts: Dict[Tuple[int, int], int] = {}
        for it in items:
            k = (item_type_of(it), int(it.index))
            key_counts[k] = key_counts.get(k, 0) + 1

        candidates: List[Tuple[int, int, Any]] = []
        for idx, it in enumerate(items):
            itype = item_type_of(it)
            iidx = int(it.index)
            if (itype, iidx) in protected:
                continue
            if itype == 1 and (shop_id, iidx) in injected_slots:
                continue

            if key_counts[(itype, iidx)] > 1:
                prio = 0  # duplicate in same shop
            elif itype == 0:
                prio = 1  # consumable item
            elif itype == 3:
                prio = 2  # accessory
            elif itype == 2:
                prio = 3  # armor
            elif itype == 1:
                cat = config.category_of_weapon(iidx)
                prio = 4 if (cat and cat_counts.get(cat, 0) > 1) else 5
            else:
                prio = 6
            candidates.append((prio, idx, it))

        if not candidates:
            continue
        candidates.sort(key=lambda t: (t[0], t[1]))
        _, replace_idx, replaced_item = candidates[0]
        items[replace_idx] = weapon
        shop.set_items(items)
        injected_slots.add((shop_id, int(weapon.index)))
        interventions.append(
            GuardrailIntervention(
                pillar="weapon_access",
                subject=f"Shop 0x{shop_id:02X} ({getattr(shop, 'name', shop_id)})",
                detail=(
                    f"[{tier}] Replaced {replaced_item.name} -> {weapon.name} "
                    f"(0x{weapon.index:02X}, {weapon.price}Z) for {reason}"
                ),
            )
        )
        return True

    return False


def enforce_weapon_accessibility(
    shops: Sequence[Any],
    weapons: Sequence[Any],
    *,
    config: WeaponAccessibilityConfig,
    playable_characters: Sequence[str] = PLAYABLE_CHARACTERS,
    item_type_of: Optional[Callable[[Any], int]] = None,
) -> List[GuardrailIntervention]:
    """Guarantee early- and mid-tier shop weapons for all active categories & party members."""
    if item_type_of is None:
        item_type_of = _default_item_type

    shops_by_id = {int(s.index): s for s in shops}
    weapons_by_id = {int(w.index): w for w in weapons if int(w.index) > 0}
    interventions: List[GuardrailIntervention] = []
    injected_slots: Set[Tuple[int, int]] = set()

    # 1. Discover which weapon categories are actively used by the 6 party members
    char_weapons: Dict[str, List[Any]] = {}
    for char in playable_characters:
        char_weapons[char] = [
            w
            for w in weapons_by_id.values()
            if int(w.old_data["price"]) > 0
            and int(w.index) not in config.excluded_weapon_ids
            and bool(w.get_bit(char))
        ]

    active_category_users: Dict[str, List[str]] = {}
    for cat, cat_ids in config.weapons_by_category.items():
        cat_set = set(cat_ids) - set(config.excluded_weapon_ids)
        users: List[str] = []
        for char in playable_characters:
            usable = [w for w in char_weapons[char] if int(w.index) in cat_set]
            # Require >= 2 weapons in the category (avoids single-item exceptions like HE Shells)
            # unless the character has fewer than 2 total usable weapons overall.
            if len(usable) >= 2 or (len(usable) >= 1 and len(char_weapons[char]) < 2):
                users.append(char)
        if users:
            active_category_users[cat] = users

    # 2. Enforce coverage for Early and Mid shop tiers
    tier_specs = (
        ("early", config.early_shops, config.early_injection_priority, config.early_max_price),
        ("mid", config.mid_shops, config.mid_injection_priority, config.mid_max_price),
    )

    all_early_ids = {
        wid for tmap in config.weapon_tiers.values() for wid in tmap.get("early", ())
    }
    all_mid_ids = {
        wid for tmap in config.weapon_tiers.values() for wid in tmap.get("mid", ())
    }

    for tier, tier_shop_ids, inject_order, max_price in tier_specs:
        def _current_tier_weapons() -> List[Any]:
            found: List[Any] = []
            for sid in tier_shop_ids:
                shop = shops_by_id.get(sid)
                if shop is None:
                    continue
                for it in _active_items(shop):
                    if item_type_of(it) == 1 and int(it.index) in weapons_by_id:
                        found.append(weapons_by_id[int(it.index)])
            return found

        # Pass A: Ensure every active weapon category has a tier weapon stocked
        for cat in sorted(active_category_users):
            users = active_category_users[cat]
            tier_ids = config.weapon_tiers.get(cat, {}).get(tier, ())
            tier_candidates = [
                weapons_by_id[wid]
                for wid in tier_ids
                if wid in weapons_by_id
                and wid not in config.excluded_weapon_ids
                and any(bool(weapons_by_id[wid].get_bit(c)) for c in users)
            ]
            if not tier_candidates:
                continue
            tier_id_set = {int(w.index) for w in tier_candidates}

            stocked = [w for w in _current_tier_weapons() if int(w.index) in tier_id_set]
            if stocked:
                # Ensure at least one stocked weapon in this category is affordable
                affordable = [w for w in stocked if int(w.price) <= max_price]
                if not affordable:
                    cheapest = min(stocked, key=lambda w: (int(w.price), int(w.index)))
                    _ensure_affordable(cheapest, max_price, tier=tier, interventions=interventions)
                continue

            # Prefer an already-affordable weapon in tier_candidates, preserving configured order
            affordable_cands = [w for w in tier_candidates if int(w.price) <= max_price]
            chosen = affordable_cands[0] if affordable_cands else min(
                tier_candidates, key=lambda w: (int(w.price), int(w.index))
            )
            _ensure_affordable(chosen, max_price, tier=tier, interventions=interventions)
            _inject_weapon_into_tier_shops(
                chosen,
                tier=tier,
                reason=f"category '{cat}' ({', '.join(users)})",
                inject_order=inject_order,
                tier_shop_ids=tier_shop_ids,
                shops_by_id=shops_by_id,
                config=config,
                injected_slots=injected_slots,
                item_type_of=item_type_of,
                interventions=interventions,
            )

        # Pass B: Per-character safety net (critical for scrambled 'q' equipability)
        tier_global_ids = all_early_ids if tier == "early" else all_mid_ids
        for char in playable_characters:
            usable = char_weapons[char]
            if not usable:
                continue

            stocked_for_char = [
                w
                for w in _current_tier_weapons()
                if int(w.index) not in config.excluded_weapon_ids
                and bool(w.get_bit(char))
                and (
                    int(w.index) in tier_global_ids
                    or (
                        tier == "early"
                        and int(w.old_data["price"]) <= max_price
                        and int(w.old_data["power"]) >= 4
                    )
                    or (
                        tier == "mid"
                        and 1000 <= int(w.old_data["price"]) <= max_price
                        and int(w.old_data["power"]) >= 20
                    )
                )
            ]
            if stocked_for_char:
                if not any(int(w.price) <= max_price for w in stocked_for_char):
                    cheapest = min(stocked_for_char, key=lambda w: (int(w.price), int(w.index)))
                    _ensure_affordable(cheapest, max_price, tier=tier, interventions=interventions)
                continue

            # Pick the best tier-appropriate weapon usable by this character
            preferred = [w for w in usable if int(w.index) in tier_global_ids]
            if not preferred:
                if tier == "early":
                    preferred = [
                        w for w in usable
                        if int(w.old_data["price"]) <= max_price
                    ]
                else:
                    preferred = [
                        w for w in usable
                        if 1000 <= int(w.old_data["price"]) <= max_price
                    ]
            if not preferred:
                preferred = list(usable)

            preferred.sort(
                key=lambda w: (
                    0 if int(w.price) <= max_price else 1,
                    int(w.old_data["price"]),
                    int(w.index),
                )
            )
            chosen = preferred[0]
            _ensure_affordable(chosen, max_price, tier=tier, interventions=interventions)
            _inject_weapon_into_tier_shops(
                chosen,
                tier=tier,
                reason=f"character '{char}'",
                inject_order=inject_order,
                tier_shop_ids=tier_shop_ids,
                shops_by_id=shops_by_id,
                config=config,
                injected_slots=injected_slots,
                item_type_of=item_type_of,
                interventions=interventions,
            )

    return interventions


# ---------------------------------------------------------------------------
# Spoiler Formatting
# ---------------------------------------------------------------------------


def format_guardrails_spoiler(report: GuardrailReport) -> str:
    """Format a concise human-readable guardrail summary for the spoiler log."""
    lines: List[str] = [
        "GUARDRAILS STATUS: "
        f"crash_blacklist={'ON' if report.crash_guard_enabled else 'OFF'} | "
        f"encounter_tiers={'ON' if report.tier_clamp_enabled else 'OFF'} | "
        f"weapon_access={'ON' if report.weapon_guard_enabled else 'OFF'}",
    ]

    sections = (
        ("crash_blacklist", "Crash Blacklist Interventions"),
        ("encounter_tier", "Encounter Tier Clamps & Protections"),
        ("weapon_access", "Weapon Accessibility Shop Adjustments"),
    )
    for pillar, heading in sections:
        entries = report.by_pillar(pillar)
        lines.append(f"\n  [{heading}] ({len(entries)})")
        if not entries:
            lines.append("    None")
            continue
        for iv in entries:
            lines.append(f"    - {iv.subject}: {iv.detail}")

    return "\n".join(lines)
