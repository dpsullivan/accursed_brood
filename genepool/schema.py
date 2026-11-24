"""Authoring schema, ROM constants, and JSON loaders for Accursed Brood."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DEFAULT_CLASSES_PATH = DATA_DIR / "classes.json"
DEFAULT_EQUIPMENT_PATH = DATA_DIR / "equipment_categories.json"

STATS: Tuple[str, ...] = ("hp", "ap", "pwr", "def", "agl", "int")

# Authoring JSON uses `def`/`agl`; randomtools struct_base_stats / struct_level use `dfn`/`agi`.
STAT_TO_ROM_ATTR: Dict[str, str] = {
    "hp": "hp",
    "ap": "ap",
    "pwr": "pwr",
    "def": "dfn",
    "agl": "agi",
    "int": "int",
}

# Exact PS1 GAME.EMI LevelObject hardware per-level gain bounds:
# hp/ap are uint8 (0..255); pwr/def and agl/int are packed 4-bit nibbles (0..15).
STAT_MAX_GAIN: Dict[str, int] = {
    "hp": 255,
    "ap": 255,
    "pwr": 15,
    "def": 15,
    "agl": 15,
    "int": 15,
}

CURVE_SHAPES: Tuple[str, ...] = ("linear", "frontloaded", "late_bloomer")

PLAYABLE_CHARACTERS: Tuple[str, ...] = ("ryu", "nina", "garr", "rei", "momo", "peco")
RESTRICTED_CHARACTERS: Tuple[str, ...] = ("teepo", "whelp")

CHARACTER_INDEX: Dict[str, int] = {
    "ryu": 0,
    "nina": 1,
    "garr": 2,
    "teepo": 3,
    "rei": 4,
    "momo": 5,
    "peco": 6,
    "whelp": 7,
}

VANILLA_JOIN_LEVELS: Dict[str, int] = {
    "ryu": 1,
    "nina": 5,
    "garr": 13,
    "rei": 5,
    "momo": 10,
    "peco": 1,
}

SKILL_CATEGORIES: Tuple[str, ...] = ("healing", "assist", "attack", "skills")
SKILL_TYPE_TO_CATEGORY: Dict[int, str] = {
    0: "healing",
    1: "assist",
    2: "attack",
    3: "skills",
}
MAX_SPELLS_PER_CATEGORY = 10

# Verified non-examinable (ex=0, skill_type in {0, 1, 2}) level-up spells from US BOF3 GAME.EMI.
# Using these IDs guarantees zero conflicts with Master / Examine skills (0xAE..0xD8, etc.).
LEVELUP_SPELL_CATALOG: Dict[str, Tuple[int, str]] = {
    # Healing (skill_type = 0)
    "Heal": (0x46, "healing"),
    "Rejuvenate": (0x47, "healing"),
    "Restore": (0x48, "healing"),
    "Vitalize": (0x49, "healing"),
    "Vigor": (0x4A, "healing"),
    "Purify": (0x4B, "healing"),
    "Raise Dead": (0x4C, "healing"),
    "Resurrect": (0x4D, "healing"),
    "Leech Power": (0x4E, "healing"),
    "Drain": (0x4F, "healing"),
    "Remedy": (0x73, "healing"),
    # Assist (skill_type = 1)
    "Dream Breath": (0x30, "assist"),
    "Venom Breath": (0x33, "assist"),
    "Identify": (0x3C, "assist"),
    "Foretell": (0x44, "assist"),
    "Protect": (0x52, "assist"),
    "Shield": (0x53, "assist"),
    "Speed": (0x54, "assist"),
    "Might": (0x55, "assist"),
    "Barrier": (0x56, "assist"),
    "Silence": (0x57, "assist"),
    "Slow": (0x58, "assist"),
    "Blunt": (0x59, "assist"),
    "Weaken": (0x5A, "assist"),
    "Sleep": (0x6B, "assist"),
    "Confuse": (0x6C, "assist"),
    # Attack (skill_type = 2)
    "Gambit": (0x02, "attack"),
    "Firebreath": (0x2E, "attack"),
    "Icebreath": (0x2F, "attack"),
    "Pilfer": (0x41, "attack"),
    "Flare": (0x5B, "attack"),
    "Fireblast": (0x5C, "attack"),
    "Inferno": (0x5D, "attack"),
    "Frost": (0x5E, "attack"),
    "Iceblast": (0x5F, "attack"),
    "Blizzard": (0x60, "attack"),
    "Jolt": (0x61, "attack"),
    "Lightning": (0x62, "attack"),
    "Myollnir": (0x63, "attack"),
    "Cyclone": (0x64, "attack"),
    "Typhoon": (0x65, "attack"),
    "Quake": (0x66, "attack"),
    "Simoon": (0x67, "attack"),
    "Sirocco": (0x68, "attack"),
    "Kyrie": (0x69, "attack"),
    "Death": (0x6A, "attack"),
    "Depress": (0x6D, "attack"),
    "Ragnarok": (0x6E, "attack"),
    "Fire Whip": (0x72, "attack"),
    "Pyrokinesis": (0x9B, "attack"),
}


@dataclass(frozen=True)
class SpellLearn:
    """A single level-up spell entry inside a class definition."""

    level: int
    skill: str
    ability_id: int
    category: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "level": self.level,
            "skill": self.skill,
            "ability_id": self.ability_id,
            "category": self.category,
        }


@dataclass(frozen=True)
class ClassDefinition:
    """Curated, human-authored archetype loaded from ``data/classes.json``."""

    id: str
    name: str
    role: str
    description: str
    base_lv1: Dict[str, int]
    growth_per_level: Dict[str, float]
    curve: str
    weapons: Tuple[str, ...]
    equipment: Tuple[str, ...]
    spells: Tuple[SpellLearn, ...]


@dataclass(frozen=True)
class EquipmentCatalog:
    """Mapping from semantic gear categories to ROM Weapon/Armor/Accessory IDs."""

    weapons: Dict[str, Tuple[int, ...]]
    armors: Dict[str, Tuple[int, ...]]
    accessories: Dict[str, Tuple[int, ...]]

    def weapon_ids_for(self, categories: Sequence[str]) -> List[int]:
        ids = set()
        for cat in categories:
            if cat not in self.weapons:
                raise ValueError(f"Unknown weapon category: {cat!r}")
            ids.update(self.weapons[cat])
        return sorted(ids)

    def armor_ids_for(self, categories: Sequence[str]) -> List[int]:
        ids = set()
        for cat in categories:
            if cat in self.armors:
                ids.update(self.armors[cat])
            elif cat not in self.accessories:
                raise ValueError(f"Unknown equipment category: {cat!r}")
        return sorted(ids)

    def accessory_ids_for(self, categories: Sequence[str]) -> List[int]:
        ids = set()
        for cat in categories:
            if cat in self.accessories:
                ids.update(self.accessories[cat])
            elif cat not in self.armors:
                raise ValueError(f"Unknown equipment category: {cat!r}")
        return sorted(ids)


def _validate_stat_map(
    raw: Mapping[str, object], *, class_id: str, field_name: str, allow_float: bool
) -> Dict[str, float] | Dict[str, int]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{class_id}.{field_name} must be an object.")
    missing = [s for s in STATS if s not in raw]
    extra = [k for k in raw if k not in STATS]
    if missing or extra:
        raise ValueError(
            f"{class_id}.{field_name} stat keys mismatch (missing={missing}, extra={extra})."
        )
    out: Dict[str, object] = {}
    for stat in STATS:
        val = raw[stat]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"{class_id}.{field_name}.{stat} must be numeric, got {val!r}.")
        if not allow_float:
            if not isinstance(val, int) or val < 0:
                raise ValueError(
                    f"{class_id}.{field_name}.{stat} must be a non-negative integer, got {val!r}."
                )
            out[stat] = int(val)
        else:
            fval = float(val)
            if fval < 0.0 or fval > STAT_MAX_GAIN[stat]:
                raise ValueError(
                    f"{class_id}.{field_name}.{stat}={fval} out of ROM gain range "
                    f"[0, {STAT_MAX_GAIN[stat]}]."
                )
            out[stat] = fval
    return out  # type: ignore[return-value]


def parse_class_definition(
    raw: Mapping[str, object], equipment_catalog: Optional[EquipmentCatalog] = None
) -> ClassDefinition:
    """Validate and construct a ``ClassDefinition`` from a JSON dict."""
    class_id = str(raw["id"]).strip()
    if not class_id:
        raise ValueError("Class definition 'id' must be non-empty.")

    name = str(raw["name"]).strip()
    role = str(raw.get("role", "")).strip()
    description = str(raw.get("description", "")).strip()

    curve = str(raw["curve"]).strip()
    if curve not in CURVE_SHAPES:
        raise ValueError(f"{class_id}: invalid curve {curve!r}; expected one of {CURVE_SHAPES}.")

    base_lv1 = _validate_stat_map(
        raw["base_lv1"], class_id=class_id, field_name="base_lv1", allow_float=False  # type: ignore[arg-type]
    )
    growth_per_level = _validate_stat_map(
        raw["growth_per_level"],  # type: ignore[arg-type]
        class_id=class_id,
        field_name="growth_per_level",
        allow_float=True,
    )

    weapons = tuple(str(w) for w in raw["weapons"])  # type: ignore[union-attr]
    equipment = tuple(str(e) for e in raw["equipment"])  # type: ignore[union-attr]
    if not weapons:
        raise ValueError(f"{class_id}: must allow at least one weapon category.")
    if not equipment:
        raise ValueError(f"{class_id}: must allow at least one equipment category.")

    if equipment_catalog is not None:
        for w in weapons:
            if w not in equipment_catalog.weapons:
                raise ValueError(f"{class_id}: unknown weapon category {w!r}.")
        for e in equipment:
            if e not in equipment_catalog.armors and e not in equipment_catalog.accessories:
                raise ValueError(f"{class_id}: unknown equipment category {e!r}.")

    seen_levels = set()
    seen_skills = set()
    bucket_counts: Dict[str, int] = {cat: 0 for cat in SKILL_CATEGORIES}
    spells: List[SpellLearn] = []

    for entry in raw.get("spells", []):  # type: ignore[union-attr]
        lvl = entry["level"]
        skill_name = str(entry["skill"]).strip()
        if not isinstance(lvl, int) or not (1 <= lvl <= 99):
            raise ValueError(f"{class_id}: spell {skill_name!r} has invalid level {lvl!r}.")
        if lvl in seen_levels:
            raise ValueError(
                f"{class_id}: multiple spells assigned to Lv {lvl} "
                f"(PS1 LevelObject allows at most 1 spell per level)."
            )
        if skill_name not in LEVELUP_SPELL_CATALOG:
            raise ValueError(
                f"{class_id}: spell {skill_name!r} is not in verified non-examinable "
                f"LEVELUP_SPELL_CATALOG."
            )
        if skill_name in seen_skills:
            raise ValueError(f"{class_id}: duplicate spell {skill_name!r}.")

        ability_id, category = LEVELUP_SPELL_CATALOG[skill_name]
        bucket_counts[category] += 1
        if bucket_counts[category] > MAX_SPELLS_PER_CATEGORY:
            raise ValueError(
                f"{class_id}: exceeds {MAX_SPELLS_PER_CATEGORY} spells in category {category!r}."
            )
        seen_levels.add(lvl)
        seen_skills.add(skill_name)
        spells.append(
            SpellLearn(level=lvl, skill=skill_name, ability_id=ability_id, category=category)
        )

    spells.sort(key=lambda s: s.level)

    return ClassDefinition(
        id=class_id,
        name=name,
        role=role,
        description=description,
        base_lv1=base_lv1,  # type: ignore[arg-type]
        growth_per_level=growth_per_level,  # type: ignore[arg-type]
        curve=curve,
        weapons=weapons,
        equipment=equipment,
        spells=tuple(spells),
    )


def load_equipment_categories(path: Path = DEFAULT_EQUIPMENT_PATH) -> EquipmentCatalog:
    """Load and validate ``data/equipment_categories.json``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    weapons = {k: tuple(int(i) for i in v) for k, v in data["weapons"].items()}
    armors = {k: tuple(int(i) for i in v) for k, v in data["armors"].items()}
    accessories = {k: tuple(int(i) for i in v) for k, v in data["accessories"].items()}
    return EquipmentCatalog(weapons=weapons, armors=armors, accessories=accessories)


def load_classes(
    path: Path = DEFAULT_CLASSES_PATH,
    equipment_catalog: Optional[EquipmentCatalog] = None,
) -> List[ClassDefinition]:
    """Load and validate all curated classes from ``data/classes.json``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_classes = data["classes"] if isinstance(data, dict) else data
    classes: List[ClassDefinition] = []
    seen_ids = set()
    for raw in raw_classes:
        cls = parse_class_definition(raw, equipment_catalog=equipment_catalog)
        if cls.id in seen_ids:
            raise ValueError(f"Duplicate class id: {cls.id!r}")
        seen_ids.add(cls.id)
        classes.append(cls)
    return classes
