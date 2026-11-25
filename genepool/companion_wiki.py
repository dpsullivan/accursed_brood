"""Companion Wiki Seed Manifest exporter, Vanilla Baseline cache, and local script registry.

Generates zero-server static SPA payloads under ``output/`` (gitignored):
  - ``output/vanilla_baseline_<rom_version>.json`` + ``.js``
  - ``output/seeds/<run_id>.json`` + ``.js``
  - ``output/seeds/registry.js`` (auto-healing on every run)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import webbrowser

from .genes import (
    assignments_from_gene_objects,
    load_dragon_genes_config,
    normalize_gene_index,
)
from .growth_compiler import grade_totals_lv40
from .guardrails import (
    MONSTER_COMBAT_STATS,
    collect_canonical_area_codes,
    extract_area_code,
    load_encounter_tiers,
    load_weapon_accessibility_config,
)
from .masters import MASTER_STAT_ORDER, RESTRICTED_MASTER_NAMES
from .schema import (
    CHARACTER_INDEX,
    PLAYABLE_CHARACTERS,
    REPO_ROOT,
    STAT_TO_ROM_ATTR,
    STATS,
    load_classes,
    load_equipment_categories,
)
from .wiki_export import build_wiki_payload

SCHEMA_VERSION = 1
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"
DEFAULT_WIKI_HTML_PATH = REPO_ROOT / "wiki.html"

_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_.-]+")
_DUMMY_NAMES = frozenset({"", "nothing", "noting", "none"})

MASTER_NAMES: Tuple[str, ...] = (
    "Bunyan", "Mygas", "Yggdrasil", "D'lonzo", "Fahl",
    "Durandal", "Giotto", "Hondara", "Emitai", "Deis",
    "Hachio", "Bais", "Lang", "Lee", "Wynn",
    "Ladon", "Meryleep",
)

MASTER_LOCATIONS: Dict[str, str] = {
    "Bunyan": "Cedar Woods",
    "Mygas": "Southern Wyndia Clearing",
    "Yggdrasil": "Wyndia / Kombinat Clearing",
    "D'lonzo": "Coffee Shop (Rhapala Region)",
    "Fahl": "Genmel Pub",
    "Durandal": "Mt. Myrneg / Wyndia Region",
    "Giotto": "Fisher's Pier (Dauna Region)",
    "Hondara": "Urkan Tapa",
    "Emitai": "Emitai's House (Dauna Region)",
    "Deis": "Mt. Zublo Inner Chamber",
    "Hachio": "Wyndia Castle Kitchen",
    "Bais": "Contest of Champions (Restricted)",
    "Lang": "Contest of Champions (Restricted)",
    "Lee": "Contest of Champions (Restricted)",
    "Wynn": "Contest of Champions (Restricted)",
    "Ladon": "Dragnier Dragon Shrine",
    "Meryleep": "Scramasax Woods",
}

MANILLO_TRADER_NAMES: Dict[int, str] = {
    0x00: "Farm",
    0x02: "Tower",
    0x07: "Urkan Tapa",
    0x09: "Dauna Mine",
    0x0B: "Cliff",
    0x0D: "Steel Beach",
    0x0F: "Kombinat",
}

DEFAULT_TABLES_DIR = REPO_ROOT / "tables"
_TIER_DISPLAY: Dict[str, str] = {
    "early": "Early",
    "mid": "Mid",
    "late": "Late",
    "protected": "Protected",
}
_ITEM_TABLE_TYPE_MAP: Tuple[Tuple[int, str], ...] = (
    (0, "items"),
    (1, "weapons"),
    (2, "armors"),
    (3, "accessories"),
    (4, "key_items"),
)

RESISTANCE_ELEMENTS: Tuple[str, ...] = (
    "Fire", "Frost", "Thunder", "Earth", "Wind",
    "Holy", "Psionic", "Status", "Death",
)

RESISTANCE_DECODE_TABLE: Tuple[Dict[str, Any], ...] = (
    {"code": 0, "label": "Very Weak",     "short": "200%", "multiplier": "200%",   "tone": "vuln-2"},
    {"code": 1, "label": "Weak",          "short": "150%", "multiplier": "150%",   "tone": "vuln-1"},
    {"code": 2, "label": "Normal",        "short": "100%", "multiplier": "100%",   "tone": "neutral"},
    {"code": 3, "label": "Resist",        "short": "50%",  "multiplier": "50%",    "tone": "res-1"},
    {"code": 4, "label": "Strong Resist", "short": "25%",  "multiplier": "25%",    "tone": "res-2"},
    {"code": 5, "label": "Null",          "short": "0%",   "multiplier": "0%",     "tone": "null"},
    {"code": 6, "label": "Absorb",        "short": "ABS",  "multiplier": "Absorb", "tone": "absorb"},
    {"code": 7, "label": "Immune",        "short": "IMM",  "multiplier": "Immune", "tone": "immune"},
)


def decode_resistance(code: int, element: Optional[str] = None) -> Dict[str, Any]:
    """Decode a raw Breath of Fire III ``0..7`` elemental/status resistance integer."""
    clamped = max(0, min(7, int(code)))
    entry = dict(RESISTANCE_DECODE_TABLE[clamped])
    if element is not None:
        entry["element"] = element
    return entry


def decode_resistances(raw_values: Sequence[int]) -> List[Dict[str, Any]]:
    """Decode a 9-element resistance vector into structured human-readable dicts."""
    padded = list(raw_values)[:9]
    while len(padded) < 9:
        padded.append(2)
    return [
        decode_resistance(val, element=elem)
        for elem, val in zip(RESISTANCE_ELEMENTS, padded)
    ]


@dataclass(frozen=True)
class ExportResult:
    """Paths and metadata produced by ``export_companion_wiki_run``."""

    run_id: str
    rom_version: str
    manifest_json_path: Path
    manifest_js_path: Path
    baseline_json_path: Path
    baseline_js_path: Path
    registry_js_path: Path
    wiki_html_path: Path


def slugify(text: str) -> str:
    """Create a deterministic, URL-safe lowercase identifier."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(text).strip().lower()).strip("_")
    return cleaned or "unknown"


def _safe_filename(token: str) -> str:
    cleaned = _SAFE_ID_RE.sub("_", str(token).strip())
    return cleaned.strip("._") or "unknown"


def _to_signed_int8(value: int) -> int:
    val = int(value)
    if val >= 0x80:
        return val - 0x100
    return val


def _is_dummy_name(name: Optional[str]) -> bool:
    if name is None:
        return True
    return str(name).strip().lower() in _DUMMY_NAMES


def _js_safe_json(payload: Any) -> str:
    """Serialize JSON safe for embedding inside classic ``<script>`` files."""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _wrap_register_script(method_name: str, payload: Any) -> str:
    """Wrap a JSON payload in a classic script call for ``file://`` loading (ADR 0002)."""
    encoded = _js_safe_json(payload)
    return (
        f"(function(){{var d={encoded};"
        "var w=window.__ACCURSED_BROOD_WIKI__=window.__ACCURSED_BROOD_WIKI__||{};"
        f"if(typeof w.{method_name}==='function'){{w.{method_name}(d);}}"
        f"else{{w._queue=w._queue||[];w._queue.push(['{method_name}',d]);}}"
        "})();\n"
    )


def compute_run_id(
    *,
    seed: Any,
    version: str,
    rom_version: str,
    flags: str,
    options: Any,
    random_degree: float = 0.5,
    difficulty: float = 1.0,
    activated_codes: Sequence[str] = (),
) -> str:
    """Compute a deterministic Run ID from Seed, version, ROM revision, and option hash."""
    norm_seed = str(seed).strip()
    norm_flags = "".join(sorted(set(str(flags or "").strip().lower())))
    preset_id = getattr(options, "preset", None)
    preset_slug = _safe_filename(str(preset_id).lower()) if preset_id else "custom"
    ver_slug = _safe_filename(str(version).lstrip("vV"))

    canonical_options = {
        "rom_version": str(rom_version),
        "version": str(version),
        "preset": str(preset_id).lower() if preset_id else None,
        "flags": norm_flags,
        "random_degree": round(float(random_degree), 6),
        "difficulty": round(float(difficulty), 6),
        "class_mode": getattr(options, "class_mode", None) or "legacy",
        "master_kits": bool(getattr(options, "master_kits", False)),
        "gene_mode": str(getattr(options, "gene_mode", "flat")),
        "exp_mult": round(float(getattr(options, "exp_mult", 1.0)), 6),
        "zenny_mult": round(float(getattr(options, "zenny_mult", 1.0)), 6),
        "drop_mult": round(float(getattr(options, "drop_mult", 1.0)), 6),
        "crash_guard": bool(getattr(options, "crash_guard", True)),
        "tier_clamp": bool(getattr(options, "tier_clamp", True)),
        "weapon_guard": bool(getattr(options, "weapon_guard", True)),
        "codes": sorted({str(c).strip().lower() for c in activated_codes if str(c).strip()}),
    }
    digest = hashlib.sha256(
        json.dumps(canonical_options, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:8]

    return f"run_{_safe_filename(norm_seed)}_{preset_slug}_v{ver_slug}_{digest}"


# ---------------------------------------------------------------------------
# Category extractors: Characters, Classes Catalog, Masters
# ---------------------------------------------------------------------------


def _ability_name_map(
    abilities: Sequence[Any], *, vanilla: bool = False
) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for ab in abilities:
        idx = int(getattr(ab, "index", 0))
        if vanilla and hasattr(ab, "old_name"):
            name = str(ab.old_name).strip()
        else:
            name = str(getattr(ab, "name", "")).strip()
        if not _is_dummy_name(name):
            out[idx] = name
    return out


def _level_stat_gain(lvl_obj: Any, rom_attr: str, *, vanilla: bool) -> int:
    if vanilla:
        if hasattr(lvl_obj, "get_old_stat"):
            return int(lvl_obj.get_old_stat(rom_attr))
        old_data = getattr(lvl_obj, "old_data", {})
        if rom_attr in old_data:
            return int(old_data[rom_attr])
        if rom_attr == "pwr" and "pwr_dfn" in old_data:
            return int(old_data["pwr_dfn"]) >> 4
        if rom_attr == "dfn" and "pwr_dfn" in old_data:
            return int(old_data["pwr_dfn"]) & 0xF
        if rom_attr == "agi" and "agi_int" in old_data:
            return int(old_data["agi_int"]) >> 4
        if rom_attr == "int" and "agi_int" in old_data:
            return int(old_data["agi_int"]) & 0xF
        return 0
    return int(getattr(lvl_obj, rom_attr, 0))


def _infer_allowed_categories(
    char_key: str,
    tables: Mapping[str, Sequence[Any]],
    equip_catalog: Any,
    *,
    vanilla: bool = False,
) -> Tuple[List[str], List[str]]:
    """Infer allowed weapon & gear categories from live or vanilla equipability bitmasks."""
    if equip_catalog is None:
        return [], []

    char_bit = 1 << CHARACTER_INDEX[char_key]

    def _can_equip(obj: Any) -> bool:
        if vanilla:
            old_mask = int(getattr(obj, "old_data", {}).get("equipability", 0))
            return bool(old_mask & char_bit)
        if hasattr(obj, "get_bit"):
            return bool(obj.get_bit(char_key))
        mask = int(getattr(obj, "equipability", 0))
        return bool(mask & char_bit)

    weapons_by_id = {int(w.index): w for w in tables.get("weapons", ())}
    armors_by_id = {int(a.index): a for a in tables.get("armors", ())}
    accs_by_id = {int(a.index): a for a in tables.get("accessories", ())}

    allowed_weapons: List[str] = []
    for cat, ids in equip_catalog.weapons.items():
        present = [weapons_by_id[i] for i in ids if i in weapons_by_id]
        if present and sum(1 for w in present if _can_equip(w)) >= max(1, len(present) // 2):
            allowed_weapons.append(cat)

    allowed_gear: List[str] = []
    for cat, ids in equip_catalog.armors.items():
        present = [armors_by_id[i] for i in ids if i in armors_by_id]
        if present and sum(1 for a in present if _can_equip(a)) >= max(1, len(present) // 2):
            allowed_gear.append(cat)
    for cat, ids in equip_catalog.accessories.items():
        present = [accs_by_id[i] for i in ids if i in accs_by_id]
        if present and sum(1 for a in present if _can_equip(a)) >= max(1, len(present) // 2):
            allowed_gear.append(cat)

    return allowed_weapons, allowed_gear


def _extract_character_progression(
    bso: Any,
    char_levels: Sequence[Any],
    ability_names: Mapping[int, str],
    *,
    vanilla: bool,
) -> Dict[str, Any]:
    """Compute Join, Lv1, Lv40, Lv99 stats, Lv40 grades, and level-up spells for one character."""
    old_data = getattr(bso, "old_data", {})
    join_level = int(old_data.get("level", getattr(bso, "level", 1))) if vanilla else int(getattr(bso, "level", 1))
    join_level = max(1, min(99, join_level))

    ordered_levels = sorted(char_levels, key=lambda l: int(getattr(l, "level", (int(l.index) % 99) + 1)))

    join_stats: Dict[str, int] = {}
    for stat in STATS:
        rom_attr = STAT_TO_ROM_ATTR[stat]
        join_stats[stat] = int(old_data.get(rom_attr, getattr(bso, rom_attr, 0))) if vanilla else int(getattr(bso, rom_attr, 0))

    gains: Dict[str, List[int]] = {stat: [] for stat in STATS}
    spells: List[Dict[str, Any]] = []
    for row_idx, lvl_obj in enumerate(ordered_levels[:99]):
        lv_num = int(getattr(lvl_obj, "level", row_idx + 1))
        for stat in STATS:
            rom_attr = STAT_TO_ROM_ATTR[stat]
            gains[stat].append(_level_stat_gain(lvl_obj, rom_attr, vanilla=vanilla))

        ab_id = int(getattr(lvl_obj, "old_data", {}).get("ability", 0)) if vanilla else int(getattr(lvl_obj, "ability", 0))
        if ab_id > 0:
            ab_name = ability_names.get(ab_id)
            if ab_name:
                spells.append({"level": lv_num, "name": ab_name, "ability_id": ab_id})

    # Pad gains to 99 if stub provided fewer rows
    for stat in STATS:
        if len(gains[stat]) < 99:
            gains[stat].extend([0] * (99 - len(gains[stat])))

    lv1_stats = {
        stat: max(0, join_stats[stat] - sum(gains[stat][1:join_level]))
        for stat in STATS
    }
    lv40_stats = {
        stat: lv1_stats[stat] + sum(gains[stat][1:40])
        for stat in STATS
    }
    lv99_stats = {
        stat: lv1_stats[stat] + sum(gains[stat][1:99])
        for stat in STATS
    }

    return {
        "join_level": join_level,
        "join": join_stats,
        "lv1": lv1_stats,
        "lv40": lv40_stats,
        "lv99": lv99_stats,
        "grades_lv40": grade_totals_lv40(lv40_stats),
        "spells": spells,
    }


def _extract_characters(
    tables: Mapping[str, Sequence[Any]],
    *,
    vanilla: bool,
    options: Optional[Any] = None,
    flags: str = "",
    class_assignments: Optional[Mapping[str, Any]] = None,
    equip_catalog: Any = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Extract normalized playable character records (list for manifest, dict by id for baseline)."""
    base_stats = tables.get("base_stats", ())
    levels = tables.get("levels", ())
    abilities = tables.get("abilities", ())

    by_index = {int(b.index): b for b in base_stats}
    levels_by_char_idx: Dict[int, List[Any]] = {}
    for lvl in levels:
        cidx = int(lvl.index) // 99
        levels_by_char_idx.setdefault(cidx, []).append(lvl)

    ability_names = _ability_name_map(abilities, vanilla=vanilla)
    class_mode = getattr(options, "class_mode", None) if options is not None else None

    records_list: List[Dict[str, Any]] = []
    records_by_id: Dict[str, Dict[str, Any]] = {}

    for char_key in PLAYABLE_CHARACTERS:
        cidx = CHARACTER_INDEX[char_key]
        bso = by_index.get(cidx)
        if bso is None:
            continue
        char_levels = levels_by_char_idx.get(cidx) or list(getattr(bso, "levels", ()))
        prog = _extract_character_progression(bso, char_levels, ability_names, vanilla=vanilla)
        display_name = str(getattr(bso, "old_name", None) or getattr(bso, "name", char_key.title())).strip() or char_key.title()

        if vanilla:
            weapons, gear = _infer_allowed_categories(char_key, tables, equip_catalog, vanilla=True)
            entry = {
                "id": char_key,
                "index": cidx,
                "name": display_name,
                "join_level": prog["join_level"],
                "join": prog["join"],
                "lv1": prog["lv1"],
                "lv40": prog["lv40"],
                "lv99": prog["lv99"],
                "grades_lv40": prog["grades_lv40"],
                "weapons": weapons,
                "gear": gear,
                "spells": prog["spells"],
            }
            records_by_id[char_key] = entry
            continue

        assignment = class_assignments.get(char_key) if class_assignments else None
        if class_mode == "archetypes" and assignment is not None and hasattr(assignment, "compiled"):
            defn = assignment.compiled.definition
            class_id = defn.id
            class_name = defn.name
            role = defn.role
            curve = defn.curve
            description = defn.description
            weapons = list(defn.weapons)
            gear = list(defn.equipment)
            mode_label = "archetypes"
        elif class_mode == "roleswap" and assignment is not None and hasattr(assignment, "donor_key"):
            donor = str(assignment.donor_key)
            class_id = f"vanilla_{donor}"
            class_name = f"Vanilla {donor.title()} Kit"
            role = "Vanilla Role Swap"
            curve = "vanilla"
            description = f"Inherited intact vanilla {donor.title()} stats, spells, and equipment permissions."
            weapons, gear = _infer_allowed_categories(char_key, tables, equip_catalog, vanilla=False)
            mode_label = "roleswap"
        else:
            randomized_chars = "c" in str(flags or "").lower()
            class_id = f"legacy_{char_key}" if randomized_chars else f"vanilla_{char_key}"
            class_name = "Legacy Randomized" if randomized_chars else "Vanilla"
            role = "Legacy Growth" if randomized_chars else "Original Kit"
            curve = "vanilla"
            description = (
                "Randomized using legacy stat/spell mutation."
                if randomized_chars
                else "Unmodified vanilla character growth."
            )
            weapons, gear = _infer_allowed_categories(char_key, tables, equip_catalog, vanilla=False)
            mode_label = "legacy" if randomized_chars else "vanilla"

        entry = {
            "id": char_key,
            "index": cidx,
            "name": display_name,
            "join_level": prog["join_level"],
            "class_mode": mode_label,
            "class_id": class_id,
            "class_name": class_name,
            "role": role,
            "curve": curve,
            "description": description,
            "weapons": weapons,
            "gear": gear,
            "join": prog["join"],
            "lv1": prog["lv1"],
            "lv40": prog["lv40"],
            "lv99": prog["lv99"],
            "grades_lv40": prog["grades_lv40"],
            "spells": prog["spells"],
        }
        records_list.append(entry)
        records_by_id[char_key] = entry

    return records_list, records_by_id


def _extract_classes_catalog(configs: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Reuse ``genepool.wiki_export.build_wiki_payload`` for the premade Classes catalog."""
    classes_list = configs.get("classes") if configs else None
    if classes_list is None:
        equip = (configs.get("equipment_catalog") if configs else None) or load_equipment_categories()
        classes_list = load_classes(equipment_catalog=equip)
    payload = build_wiki_payload(list(classes_list))
    return list(payload.get("classes", []))


def _decode_master_skills(
    raw_skill_levels: Sequence[int], ability_names: Mapping[int, str]
) -> List[Dict[str, Any]]:
    skills: List[Dict[str, Any]] = []
    for packed in raw_skill_levels:
        packed_int = int(packed)
        sid = packed_int >> 8
        lv = packed_int & 0xFF
        if sid == 0xFF or sid == 0:
            continue
        name = ability_names.get(sid)
        if not name:
            continue
        skills.append({"level": lv, "name": name, "ability_id": sid})
    skills.sort(key=lambda s: (s["level"], s["ability_id"]))
    return skills


def _extract_masters(
    tables: Mapping[str, Sequence[Any]],
    *,
    vanilla: bool,
    options: Optional[Any] = None,
    flags: str = "",
    master_assignments: Optional[Sequence[Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Extract all 17 Masters (active list or vanilla dict keyed by master id)."""
    master_stats = tables.get("master_stats", ())
    master_skills = tables.get("master_skills", ())
    abilities = tables.get("abilities", ())

    stats_by_idx = {int(m.index): m for m in master_stats}
    skills_by_idx = {int(m.index): m for m in master_skills}
    ability_names = _ability_name_map(abilities, vanilla=vanilla)

    assignments_by_idx: Dict[int, Any] = {}
    if master_assignments:
        for asgn in master_assignments:
            assignments_by_idx[int(asgn.master.index)] = asgn

    curated_active = bool(getattr(options, "master_kits", False)) if options is not None else False
    masters_flag_active = "m" in str(flags or "").lower()

    records_list: List[Dict[str, Any]] = []
    records_by_id: Dict[str, Dict[str, Any]] = {}

    indices = sorted(set(stats_by_idx) | set(skills_by_idx))
    for idx in indices:
        mstats = stats_by_idx.get(idx)
        mskills = skills_by_idx.get(idx)
        raw_name = getattr(mstats, "name", None) if mstats is not None else None
        if not raw_name and 0 <= idx < len(MASTER_NAMES):
            raw_name = MASTER_NAMES[idx]
        if not raw_name:
            continue
        name = str(raw_name).strip()
        mid = slugify(name)
        restricted = name in RESTRICTED_MASTER_NAMES
        location = MASTER_LOCATIONS.get(name, "Unknown")

        stats_dict: Dict[str, int] = {}
        for attr in MASTER_STAT_ORDER:
            if mstats is None:
                stats_dict[attr] = 0
            elif vanilla:
                stats_dict[attr] = _to_signed_int8(mstats.old_data.get(attr, 0))
            else:
                stats_dict[attr] = _to_signed_int8(getattr(mstats, attr, 0))

        if mskills is None:
            skills_list: List[Dict[str, Any]] = []
        elif vanilla:
            skills_list = _decode_master_skills(mskills.old_data.get("skill_levels", ()), ability_names)
        else:
            skills_list = _decode_master_skills(getattr(mskills, "skill_levels", ()), ability_names)

        if vanilla:
            records_by_id[mid] = {
                "id": mid,
                "index": idx,
                "name": name,
                "location": location,
                "restricted": restricted,
                "stats": stats_dict,
                "skills": skills_list,
            }
            continue

        asgn = assignments_by_idx.get(idx)
        if restricted:
            kit_id = None
            kit_name = "Restricted (Vanilla)"
            role = "Tournament Master (Unchanged)"
            description = "Restricted Contest of Champions Master kept untouched for stability."
            subs: List[str] = []
        elif curated_active and asgn is not None and getattr(asgn, "kit", None) is not None:
            kit = asgn.kit
            kit_id = kit.id
            kit_name = kit.name
            role = kit.theme
            description = kit.description
            subs = list(getattr(asgn, "substituted_skills", ()))
        elif masters_flag_active:
            kit_id = None
            kit_name = "Legacy Randomized"
            role = "Random Stat & Skill Pool"
            description = "Randomized with legacy Master stat/skill shuffling."
            subs = []
        else:
            kit_id = None
            kit_name = "Vanilla"
            role = "Original Master"
            description = "Unmodified vanilla Master stats and skills."
            subs = []

        entry = {
            "id": mid,
            "index": idx,
            "name": name,
            "location": location,
            "restricted": restricted,
            "kit_id": kit_id,
            "kit_name": kit_name,
            "role": role,
            "description": description,
            "stats": stats_dict,
            "skills": skills_list,
            "substituted_skills": subs,
        }
        records_list.append(entry)
        records_by_id[mid] = entry

    return records_list, records_by_id


# ---------------------------------------------------------------------------
# Shared ROM table name & item lookup helpers
# ---------------------------------------------------------------------------


def _load_area_names(tblpath: Optional[Any] = None) -> Dict[int, str]:
    base = Path(tblpath) if tblpath else DEFAULT_TABLES_DIR
    area_file = base / "names_areas.txt"
    if not area_file.exists():
        return {}
    names: Dict[int, str] = {}
    for raw_line in area_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or " " not in line:
            continue
        idx_str, desc = line.split(" ", 1)
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        names[idx] = desc.strip()
    return names


def _load_shop_names(tblpath: Optional[Any] = None) -> Dict[int, str]:
    base = Path(tblpath) if tblpath else DEFAULT_TABLES_DIR
    shop_file = base / "names_shops.txt"
    if not shop_file.exists():
        return {}
    names: Dict[int, str] = {}
    for idx, raw_line in enumerate(shop_file.read_text(encoding="utf-8", errors="replace").splitlines()):
        names[idx] = raw_line.strip()
    return names


def _build_item_lookup(
    tables: Mapping[str, Sequence[Any]], *, vanilla: bool = False
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Build ``(item_type, index) -> {id, name, price}`` with deterministic unique slugs."""
    used_slugs: Dict[str, Tuple[int, int]] = {}
    lookup: Dict[Tuple[int, int], Dict[str, Any]] = {}
    kind_suffix = {0: "item", 1: "weapon", 2: "armor", 3: "acc", 4: "key"}

    for item_type, table_key in _ITEM_TABLE_TYPE_MAP:
        for obj in sorted(tables.get(table_key, ()), key=lambda o: int(getattr(o, "index", 0))):
            idx = int(getattr(obj, "index", 0))
            if idx <= 0:
                continue
            raw_name = (
                getattr(obj, "old_name", None) if vanilla else None
            ) or getattr(obj, "name", "")
            name = str(raw_name).strip()
            if _is_dummy_name(name):
                continue
            base_slug = slugify(name)
            if base_slug in used_slugs and used_slugs[base_slug] != (item_type, idx):
                item_id = f"{base_slug}_{kind_suffix[item_type]}_{idx:02x}"
            else:
                item_id = base_slug
                used_slugs[base_slug] = (item_type, idx)
            old_data = getattr(obj, "old_data", {})
            price = int(old_data.get("price", 0)) if vanilla else int(getattr(obj, "price", 0))
            lookup[(item_type, idx)] = {
                "id": item_id,
                "name": name,
                "price": price,
                "item_type": item_type,
                "index": idx,
            }
    return lookup


# ---------------------------------------------------------------------------
# Category extractors: Dragon Genes, Shops, Manillos, Chests, Guardrails
# ---------------------------------------------------------------------------


def _extract_genes(
    tables: Mapping[str, Sequence[Any]],
    configs: Mapping[str, Any],
    *,
    vanilla: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    gene_objs = tables.get("genes", ())
    gene_cfg = configs.get("dragon_genes") or load_dragon_genes_config()

    by_idx = {int(g.index): g for g in gene_objs}
    genes_by_id = gene_cfg.genes_by_id

    if vanilla:
        out: Dict[str, Dict[str, Any]] = {}
        for loc in gene_cfg.locations:
            gobj = by_idx.get(loc.index)
            if gobj is not None and "gene_index" in getattr(gobj, "old_data", {}):
                gid = normalize_gene_index(gobj.old_data["gene_index"])
                gname = genes_by_id[gid].name
            else:
                gid = loc.vanilla_gene_id
                gname = loc.vanilla_gene_name
            loc_id = f"{loc.index:02d}"
            out[loc_id] = {
                "id": loc_id,
                "index": loc.index,
                "tier": _TIER_DISPLAY.get(loc.tier, loc.tier.title()),
                "location": loc.area_name,
                "gene_id": gid,
                "gene": gname,
            }
        return [], out

    if not gene_objs:
        return [], {}

    assignments = assignments_from_gene_objects(gene_objs, gene_cfg)
    records: List[Dict[str, Any]] = []
    for asgn in assignments:
        loc = asgn.location
        gene = asgn.assigned_gene
        loc_id = f"{loc.index:02d}"
        records.append(
            {
                "id": loc_id,
                "index": loc.index,
                "tier": _TIER_DISPLAY.get(loc.tier, loc.tier.title()),
                "location": loc.area_name,
                "has_chrysm": loc.has_chrysm,
                "gene_id": gene.id,
                "gene": gene.name,
                "gene_tier": _TIER_DISPLAY.get(gene.tier, gene.tier.title()),
                "gene_role": gene.role,
                "description": gene.description,
                "is_cross_tier": asgn.is_cross_tier,
                "vanilla_gene": loc.vanilla_gene_name,
            }
        )
    return records, {}


def _parse_guardrail_tag(detail: str) -> str:
    m = re.match(r"^\[([^\]]+)\]", str(detail).strip())
    return m.group(1).strip() if m else "Adjusted"


def _extract_guardrails(
    guardrail_report: Optional[Any], options: Optional[Any]
) -> Dict[str, Any]:
    enabled = {
        "crash": bool(getattr(options, "crash_guard", True)) if options is not None else True,
        "tiers": bool(getattr(options, "tier_clamp", True)) if options is not None else True,
        "weapons": bool(getattr(options, "weapon_guard", True)) if options is not None else True,
    }
    if guardrail_report is None:
        return {
            "enabled": enabled,
            "crash_count": 0,
            "clamp_count": 0,
            "weapon_count": 0,
            "crash_items": [],
            "clamp_items": [],
            "weapon_items": [],
        }

    crash_items: List[Dict[str, Any]] = []
    clamp_items: List[Dict[str, Any]] = []
    weapon_items: List[Dict[str, Any]] = []

    for iv in getattr(guardrail_report, "interventions", ()):
        pillar = str(getattr(iv, "pillar", ""))
        subject = str(getattr(iv, "subject", ""))
        detail = str(getattr(iv, "detail", ""))
        tag = _parse_guardrail_tag(detail)

        if pillar == "crash_blacklist":
            crash_items.append({"subject": subject, "detail": detail})
        elif pillar == "encounter_tier":
            clamp_items.append({"subject": subject, "tag": tag, "detail": detail})
        elif pillar == "weapon_access":
            shop_match = re.match(r"^Shop 0x([0-9A-Fa-f]{2})\s*\(([^)]+)\)", subject)
            item_match = re.search(r"(?:Added|Replaced .*?->)\s+([^(]+?)\s+\(0x([0-9A-Fa-f]{2})", detail)
            tier_match = re.match(r"^\[(early|mid|late)", detail, re.IGNORECASE)
            weapon_items.append(
                {
                    "subject": subject,
                    "tag": tag,
                    "detail": detail,
                    "tier": tier_match.group(1).title() if tier_match else "Early",
                    "shop_id": shop_match.group(1).upper() if shop_match else None,
                    "shop_name": shop_match.group(2).strip() if shop_match else subject,
                    "item": item_match.group(1).strip() if item_match else subject,
                }
            )

    return {
        "enabled": enabled,
        "crash_count": len(crash_items),
        "clamp_count": len(clamp_items),
        "weapon_count": len(weapon_items),
        "crash_items": crash_items,
        "clamp_items": clamp_items,
        "weapon_items": weapon_items,
    }


def _extract_shops(
    tables: Mapping[str, Sequence[Any]],
    configs: Mapping[str, Any],
    *,
    vanilla: bool,
    guardrails_data: Optional[Mapping[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    shops = tables.get("shops", ())
    if not shops:
        return [], {}

    shop_names = _load_shop_names(configs.get("tblpath"))
    weapon_cfg = configs.get("weapon_access") or load_weapon_accessibility_config()
    item_lookup = _build_item_lookup(tables, vanilla=vanilla)

    # Index guardrail shop notes by (shop_id, item_name_lower)
    guardrail_by_shop_item: Dict[Tuple[str, str], str] = {}
    if guardrails_data:
        for w in guardrails_data.get("weapon_items", ()):
            if w.get("shop_id") and w.get("item"):
                guardrail_by_shop_item[(str(w["shop_id"]).upper(), str(w["item"]).lower())] = (
                    f"{w.get('tier', 'Early')} Guardrail"
                )

    def _shop_tier(shop_idx: int) -> str:
        if shop_idx in weapon_cfg.faerie_shop_ids:
            return "Faerie"
        if shop_idx in weapon_cfg.early_shops:
            return "Early"
        if shop_idx in weapon_cfg.mid_shops:
            return "Mid"
        return "Late"

    def _decode_stock(packed_list: Sequence[int], shop_hex: str) -> List[Dict[str, Any]]:
        stock: List[Dict[str, Any]] = []
        for val in packed_list:
            v = int(val)
            if v == 0:
                continue
            itype = v & 0xFF
            iidx = v >> 8
            if iidx == 0:
                continue
            info = item_lookup.get((itype, iidx))
            if not info:
                continue
            entry: Dict[str, Any] = {
                "item": info["name"],
                "item_id": info["id"],
                "price": info["price"],
            }
            if not vanilla:
                note = guardrail_by_shop_item.get((shop_hex, info["name"].lower()))
                if note:
                    entry["guardrail"] = note
            stock.append(entry)
        return stock

    records_list: List[Dict[str, Any]] = []
    records_by_id: Dict[str, Dict[str, Any]] = {}

    for shop in sorted(shops, key=lambda s: int(s.index)):
        idx = int(shop.index)
        shop_hex = f"{idx:02X}"
        raw_name = shop_names.get(idx) or getattr(shop, "name", "") or f"Shop {shop_hex}"
        name = str(raw_name).strip()
        old_packed = getattr(shop, "old_data", {}).get("item_type_item_indexes", ())
        cur_packed = getattr(shop, "item_type_item_indexes", ())
        stock = _decode_stock(old_packed if vanilla else cur_packed, shop_hex)
        if not stock and name == "?":
            continue
        if not stock and not _decode_stock(old_packed, shop_hex):
            continue

        entry = {
            "id": shop_hex,
            "index": idx,
            "name": name,
            "tier": _shop_tier(idx),
            "stock": stock,
        }
        records_list.append(entry)
        records_by_id[shop_hex] = entry

    return records_list, records_by_id


def _extract_manillos(
    tables: Mapping[str, Sequence[Any]],
    *,
    vanilla: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    stocks = tables.get("manillo_stocks", ())
    mitems = tables.get("manillo_items", ())
    if not stocks or not mitems:
        return [], {}

    mitem_by_idx = {int(mi.index): mi for mi in mitems}
    item_lookup = _build_item_lookup(tables, vanilla=vanilla)

    records_list: List[Dict[str, Any]] = []
    records_by_id: Dict[str, Dict[str, Any]] = {}

    for ms in sorted(stocks, key=lambda s: int(s.index)):
        idx = int(ms.index)
        trader_id = f"{idx:02X}"
        trade_indexes = (
            getattr(ms, "old_data", {}).get("trade_indexes", ())
            if vanilla
            else getattr(ms, "trade_indexes", ())
        )
        trades: List[Dict[str, Any]] = []
        for tidx in trade_indexes:
            tidx_int = int(tidx)
            if tidx_int == 0xFF:
                continue
            mi = mitem_by_idx.get(tidx_int)
            if mi is None:
                continue
            old_data = getattr(mi, "old_data", {})
            itype = int(old_data.get("item_type", 0)) if vanilla else int(getattr(mi, "item_type", 0))
            iidx = int(old_data.get("item_index", 0)) if vanilla else int(getattr(mi, "item_index", 0))
            reward = item_lookup.get((itype, iidx))
            if not reward:
                continue

            f_indexes = old_data.get("fish_indexes", ()) if vanilla else getattr(mi, "fish_indexes", ())
            f_qtys = old_data.get("fish_quantities", ()) if vanilla else getattr(mi, "fish_quantities", ())
            fishes: List[Dict[str, Any]] = []
            for fi, fq in zip(f_indexes, f_qtys):
                fi_int, fq_int = int(fi), int(fq)
                if fi_int == 0xFF or fq_int <= 0:
                    continue
                fish_info = item_lookup.get((0, 0x38 + fi_int))
                fish_name = fish_info["name"] if fish_info else f"Fish 0x{0x38 + fi_int:02X}"
                fishes.append({"name": fish_name, "qty": fq_int})

            cost_text = ", ".join(f"{f['name']} x{f['qty']}" for f in fishes) or "Free"
            trades.append(
                {
                    "trade_index": tidx_int,
                    "item": reward["name"],
                    "item_id": reward["id"],
                    "fishes": fishes,
                    "cost": cost_text,
                }
            )

        if not trades:
            continue

        name = MANILLO_TRADER_NAMES.get(idx) or str(getattr(ms, "name", f"Trader {trader_id}"))
        entry = {
            "id": trader_id,
            "index": idx,
            "name": name,
            "trades": trades,
        }
        records_list.append(entry)
        records_by_id[trader_id] = entry

    return records_list, records_by_id


def _area_tier(area_code: Optional[int], encounter_tiers: Any) -> str:
    if area_code is None or encounter_tiers is None:
        return "Mid"
    for tname in encounter_tiers.tier_order:
        if area_code in encounter_tiers.tiers[tname].area_codes:
            return _TIER_DISPLAY.get(tname, tname.title())
    if area_code <= 68:
        return "Early"
    if area_code <= 136:
        return "Mid"
    return "Late"


def _extract_chests(
    tables: Mapping[str, Sequence[Any]],
    configs: Mapping[str, Any],
    *,
    vanilla: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    chests = tables.get("chests", ())
    if not chests:
        return [], {}

    area_names = _load_area_names(configs.get("tblpath"))
    encounter_tiers = configs.get("encounter_tiers") or load_encounter_tiers()
    item_lookup = _build_item_lookup(tables, vanilla=vanilla)

    records_list: List[Dict[str, Any]] = []
    records_by_id: Dict[str, Dict[str, Any]] = {}

    for ch in sorted(chests, key=lambda c: (extract_area_code(getattr(c, "filename", None)) or 999, int(c.index))):
        idx = int(ch.index)
        cid = f"{idx:02X}"
        area_code = extract_area_code(getattr(ch, "filename", None))
        if area_code is None and hasattr(ch, "area_code"):
            try:
                area_code = int(ch.area_code)
            except Exception:
                area_code = None
        area_name = (
            area_names.get(area_code) if area_code is not None else None
        ) or getattr(ch, "area_name", None) or (f"AREA {area_code:03d}" if area_code is not None else "Unknown Area")

        old_data = getattr(ch, "old_data", {})
        itype = int(old_data.get("item_type", 0)) if vanilla else int(getattr(ch, "item_type", 0))
        iidx = int(old_data.get("item_index", 0)) if vanilla else int(getattr(ch, "item_index", 0))
        memory = int(old_data.get("memory", 0)) if vanilla else int(getattr(ch, "memory", 0))

        if itype == 0xFF:
            item_name = f"{iidx * 40}Z"
            item_id = None
            is_zenny = True
        else:
            info = item_lookup.get((itype, iidx))
            if info:
                item_name = info["name"]
                item_id = info["id"]
                is_zenny = False
            else:
                item_name = "None"
                item_id = None
                is_zenny = False

        entry = {
            "id": cid,
            "index": idx,
            "area_code": area_code,
            "area": str(area_name),
            "memory": memory,
            "tier": _area_tier(area_code, encounter_tiers),
            "is_zenny": is_zenny,
            "item": item_name,
            "item_id": item_id,
        }
        records_list.append(entry)
        records_by_id[cid] = entry

    return records_list, records_by_id


# ---------------------------------------------------------------------------
# Category extractor: Normalized Bestiary (Monsters)
# ---------------------------------------------------------------------------


def _drop_rate_percent(rate_exp: int) -> int:
    r = int(rate_exp)
    if r <= 0:
        return 0
    return min(100, int(round(((2 ** r) / 128.0) * 100.0)))


def _ability_is_examinable(ab: Any, *, vanilla: bool) -> bool:
    if vanilla:
        old_data = getattr(ab, "old_data", {})
        if "unknown2" in old_data:
            return bool(int(old_data["unknown2"]) & 0x02)
        if "examinable" in old_data:
            return bool(old_data["examinable"])
    if hasattr(ab, "get_bit"):
        try:
            return bool(ab.get_bit("examinable"))
        except Exception:
            pass
    return bool(getattr(ab, "examinable", False))


def _monster_ability_ids(monster: Any, *, vanilla: bool) -> List[int]:
    old_data = getattr(monster, "old_data", {})
    if vanilla:
        ids = set(int(x) for x in old_data.get("initial_skills", ()))
        for phase in range(1, 5):
            cond = int(old_data.get(f"condition{phase}", 99))
            if cond < 99:
                ids.update(int(x) for x in old_data.get(f"skills{phase}", ()))
        return sorted(i for i in ids if i > 0)

    ids = set(int(x) for x in getattr(monster, "initial_skills", ()))
    for phase in range(1, 5):
        cond = int(getattr(monster, f"condition{phase}", 99))
        if cond < 99:
            ids.update(int(x) for x in getattr(monster, f"skills{phase}", ()))
    return sorted(i for i in ids if i > 0)


def _extract_monster_abilities(
    monster: Any,
    abilities_by_id: Mapping[int, Any],
    *,
    vanilla: bool,
) -> List[Dict[str, Any]]:
    by_name: Dict[str, Dict[str, Any]] = {}
    for aid in _monster_ability_ids(monster, vanilla=vanilla):
        ab = abilities_by_id.get(aid)
        if ab is None:
            continue
        raw_name = (
            getattr(ab, "old_name", None) if vanilla else None
        ) or getattr(ab, "name", "")
        name = str(raw_name).strip()
        if _is_dummy_name(name):
            continue
        learnable = _ability_is_examinable(ab, vanilla=vanilla)
        key = name.lower()
        if key not in by_name:
            by_name[key] = {
                "id": slugify(name),
                "name": name,
                "ability_id": aid,
                "learnable": learnable,
            }
        elif learnable:
            by_name[key]["learnable"] = True
    return sorted(by_name.values(), key=lambda a: a["name"].lower())


def _extract_monster_loot(
    monster: Any,
    prefix: str,
    item_lookup: Mapping[Tuple[int, int], Dict[str, Any]],
    *,
    vanilla: bool,
) -> Optional[Dict[str, Any]]:
    old_data = getattr(monster, "old_data", {})
    rate_key = f"{prefix}_rate"
    type_key = f"{prefix}_item_type"
    idx_key = f"{prefix}_item_index"

    rate = int(old_data.get(rate_key, 0)) if vanilla else int(getattr(monster, rate_key, 0))
    if rate <= 0:
        return None
    itype = int(old_data.get(type_key, 0)) if vanilla else int(getattr(monster, type_key, 0))
    iidx = int(old_data.get(idx_key, 0)) if vanilla else int(getattr(monster, idx_key, 0))
    info = item_lookup.get((itype, iidx))
    if not info:
        return None
    return {
        "item": info["name"],
        "item_id": info["id"],
        "rate": _drop_rate_percent(rate),
    }


def _extract_monsters(
    tables: Mapping[str, Sequence[Any]],
    configs: Mapping[str, Any],
    *,
    vanilla: bool,
    guardrails_data: Optional[Mapping[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    monsters = tables.get("monsters", ())
    if not monsters:
        return [], {}

    area_names = _load_area_names(configs.get("tblpath"))
    encounter_tiers = configs.get("encounter_tiers") or load_encounter_tiers()
    abilities_by_id = {int(a.index): a for a in tables.get("abilities", ())}
    item_lookup = _build_item_lookup(tables, vanilla=vanilla)
    area_codes_by_canon = collect_canonical_area_codes(monsters)

    # Index guardrail notes by monster name (lowercased)
    notes_by_monster: Dict[str, List[str]] = {}
    if guardrails_data:
        for item in guardrails_data.get("clamp_items", ()):
            subj = str(item.get("subject", "")).strip().lower()
            if subj:
                notes_by_monster.setdefault(subj, []).append(str(item.get("detail", "")))
        for item in guardrails_data.get("crash_items", ()):
            subj = str(item.get("subject", "")).strip().lower()
            if subj:
                notes_by_monster.setdefault(subj, []).append(str(item.get("detail", "")))

    tier_rank = {"Protected": 0, "Early": 1, "Mid": 2, "Late": 3}

    # Build per-slot vanilla baseline records AND grouped active logical monsters
    vanilla_slots: Dict[str, Dict[str, Any]] = {}
    grouped_slots: Dict[str, List[Dict[str, Any]]] = {}
    group_meta: Dict[str, Dict[str, Any]] = {}

    for m in sorted(monsters, key=lambda o: int(o.index)):
        if not getattr(m, "is_canonical", True):
            continue
        raw_name = (
            getattr(m, "old_name", None) if vanilla else None
        ) or getattr(m, "name", "")
        name = str(raw_name).strip()
        old_data = getattr(m, "old_data", {})
        old_hp = int(old_data.get("hp", getattr(m, "hp", 0)))
        old_lv = int(old_data.get("level", getattr(m, "level", 0)))
        cur_hp = int(getattr(m, "hp", 0))
        cur_lv = int(getattr(m, "level", 0))

        # Strip blank/dummy ROM slots (e.g. 000 LV 0)
        if _is_dummy_name(name):
            continue
        if old_lv == 0 and old_hp == 0 and cur_lv == 0 and cur_hp == 0:
            continue

        slot_hex = f"{int(m.index):03X}"
        is_boss = bool(getattr(m, "is_boss", False))
        codes = area_codes_by_canon.get(int(m.index), frozenset())
        tier_raw, _ = encounter_tiers.classify_monster(
            name, is_boss=is_boss, old_hp=old_hp, area_codes=codes
        )
        tier_label = _TIER_DISPLAY.get(tier_raw, tier_raw.title())

        slot_area_names = sorted(
            {area_names.get(code, f"AREA {code:03d}") for code in codes}
        )
        variant_label = slot_area_names[0] if slot_area_names else (f"Boss Slot {slot_hex}" if is_boss else f"Slot {slot_hex}")

        if vanilla:
            stats = {s: int(old_data.get(s, 0)) for s in MONSTER_COMBAT_STATS}
            res = decode_resistances(old_data.get("resistances", (2,) * 9))
            vanilla_slots[slot_hex] = {
                "slot": slot_hex,
                "index": int(m.index),
                "name": name,
                "lv": old_lv,
                "exp": int(old_data.get("exp", 0)),
                "zenny": int(old_data.get("zenny", 0)),
                "stats": stats,
                "resistances": res,
                "steal": _extract_monster_loot(m, "steal", item_lookup, vanilla=True),
                "drop": _extract_monster_loot(m, "drop", item_lookup, vanilla=True),
                "abilities": _extract_monster_abilities(m, abilities_by_id, vanilla=True),
            }
            continue

        cur_stats = {s: int(getattr(m, s, 0)) for s in MONSTER_COMBAT_STATS}
        old_stats = {s: int(old_data.get(s, cur_stats[s])) for s in MONSTER_COMBAT_STATS}
        cur_res_raw = [int(r) for r in getattr(m, "resistances", (2,) * 9)]
        old_res_raw = [int(r) for r in old_data.get("resistances", cur_res_raw)]
        cur_steal = _extract_monster_loot(m, "steal", item_lookup, vanilla=False)
        old_steal = _extract_monster_loot(m, "steal", item_lookup, vanilla=True)
        cur_drop = _extract_monster_loot(m, "drop", item_lookup, vanilla=False)
        old_drop = _extract_monster_loot(m, "drop", item_lookup, vanilla=True)
        cur_abs = _extract_monster_abilities(m, abilities_by_id, vanilla=False)
        old_abs = _extract_monster_abilities(m, abilities_by_id, vanilla=True)

        slot_changed = (
            cur_stats != old_stats
            or cur_res_raw != old_res_raw
            or cur_steal != old_steal
            or cur_drop != old_drop
            or [a["name"] for a in cur_abs] != [a["name"] for a in old_abs]
            or int(getattr(m, "exp", 0)) != int(old_data.get("exp", getattr(m, "exp", 0)))
            or int(getattr(m, "zenny", 0)) != int(old_data.get("zenny", getattr(m, "zenny", 0)))
        )

        variant = {
            "slot": slot_hex,
            "index": int(m.index),
            "label": variant_label,
            "lv": cur_lv,
            "is_boss": is_boss,
            "tier": tier_label,
            "exp": int(getattr(m, "exp", 0)),
            "zenny": int(getattr(m, "zenny", 0)),
            "areas": slot_area_names,
            "stats": cur_stats,
            "resistances": decode_resistances(cur_res_raw),
            "steal": cur_steal,
            "drop": cur_drop,
            "abilities": cur_abs,
            "changed": slot_changed,
        }

        group_key = name.lower()
        grouped_slots.setdefault(group_key, []).append(variant)
        meta = group_meta.setdefault(
            group_key,
            {
                "id": slugify(name),
                "name": name,
                "tier": tier_label,
                "is_boss": is_boss,
                "areas": set(),
                "changed": False,
            },
        )
        if tier_rank.get(tier_label, 3) < tier_rank.get(meta["tier"], 3):
            meta["tier"] = tier_label
        meta["is_boss"] = meta["is_boss"] or is_boss
        meta["areas"].update(slot_area_names)
        meta["changed"] = meta["changed"] or slot_changed

    if vanilla:
        return [], vanilla_slots

    logical_monsters: List[Dict[str, Any]] = []
    for group_key in sorted(grouped_slots, key=lambda k: group_meta[k]["name"].lower()):
        meta = group_meta[group_key]
        variants = grouped_slots[group_key]
        # Disambiguate duplicate variant labels cleanly when same-name slots share an area
        if len(variants) > 1:
            label_counts: Dict[str, int] = {}
            for v in variants:
                label_counts[v["label"]] = label_counts.get(v["label"], 0) + 1
            seen_lbl: Dict[str, int] = {}
            for v in variants:
                if label_counts[v["label"]] > 1:
                    n = seen_lbl.get(v["label"], 0) + 1
                    seen_lbl[v["label"]] = n
                    v["label"] = f"{v['label']} #{n}"

        notes = notes_by_monster.get(group_key, [])
        logical_monsters.append(
            {
                "id": meta["id"],
                "name": meta["name"],
                "tier": meta["tier"],
                "is_boss": meta["is_boss"],
                "areas": sorted(meta["areas"]),
                "guardrail_note": " | ".join(notes) if notes else None,
                "changed": meta["changed"],
                "variants": variants,
            }
        )

    return logical_monsters, {}


# ---------------------------------------------------------------------------
# Category extractors: Unified Abilities & Normalized Equipment / Items
# ---------------------------------------------------------------------------

ABILITY_ELEMENT_BITS: Tuple[Tuple[int, str], ...] = (
    (0x01, "Fire"),
    (0x02, "Ice"),
    (0x04, "Lightning"),
    (0x08, "Earth"),
    (0x10, "Wind"),
    (0x20, "Holy"),
    (0x40, "Psionic"),
    (0x80, "Status"),
)

_SKILL_TYPE_LABELS: Dict[int, str] = {
    0: "Healing",
    1: "Assist",
    2: "Attack",
    3: "Skill",
}

_ARMOR_EQUIP_TYPE_LABELS: Dict[int, str] = {
    2: "Shield",
    3: "Helmet",
    4: "Armor",
}


def _decode_element_bits(obj: Any, *, vanilla: bool) -> List[str]:
    old_data = getattr(obj, "old_data", {})
    if vanilla and "element" in old_data:
        mask = int(old_data["element"])
        return [label for bit, label in ABILITY_ELEMENT_BITS if mask & bit]
    if not vanilla and hasattr(obj, "element"):
        mask = int(getattr(obj, "element", 0))
        return [label for bit, label in ABILITY_ELEMENT_BITS if mask & bit]
    if hasattr(obj, "get_bit"):
        out: List[str] = []
        for _, label in ABILITY_ELEMENT_BITS:
            try:
                if obj.get_bit(label.lower()):
                    out.append(label)
            except Exception:
                pass
        return out
    return []


def _decode_equip_names(mask: int) -> List[str]:
    names: List[str] = []
    for char_key in PLAYABLE_CHARACTERS:
        bit = 1 << CHARACTER_INDEX[char_key]
        if mask & bit:
            names.append(char_key.title())
    return names


def _extract_abilities(
    tables: Mapping[str, Sequence[Any]],
    *,
    vanilla: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Merge duplicate ROM ability slots (level-up vs examine/Master) into canonical records."""
    abilities = tables.get("abilities", ())
    if not abilities:
        return [], {}

    grouped: Dict[str, List[Any]] = {}
    canonical_display: Dict[str, str] = {}

    for ab in sorted(abilities, key=lambda a: int(a.index)):
        idx = int(ab.index)
        if idx <= 0:
            continue
        raw_name = (
            getattr(ab, "old_name", None) if vanilla else None
        ) or getattr(ab, "name", "")
        name = str(raw_name).strip()
        if _is_dummy_name(name):
            continue
        key = name.lower()
        grouped.setdefault(key, []).append(ab)
        if key not in canonical_display:
            canonical_display[key] = name

    records_list: List[Dict[str, Any]] = []
    records_by_id: Dict[str, Dict[str, Any]] = {}

    for key in sorted(grouped, key=lambda k: canonical_display[k].lower()):
        slots = grouped[key]
        name = canonical_display[key]
        ab_id = slugify(name)

        merged_slots: List[str] = []
        merged_slot_ids: List[int] = []
        ap_val = 0
        power_val = 0
        elements: List[str] = []
        target = "Ally / Self"
        any_examinable = False
        chosen_category = "Skill"
        any_changed = False

        for ab in slots:
            idx = int(ab.index)
            old_data = getattr(ab, "old_data", {})
            ex = _ability_is_examinable(ab, vanilla=vanilla)
            old_ex = _ability_is_examinable(ab, vanilla=True)
            cost = int(old_data.get("cost", 0)) if vanilla else int(getattr(ab, "cost", 0))
            pwr = int(old_data.get("power", 0)) if vanilla else int(getattr(ab, "power", 0))
            stype = (
                int(old_data.get("skill_type", 3)) if vanilla else int(getattr(ab, "skill_type", 3))
            ) & 0x03
            old_stype = int(old_data.get("skill_type", stype)) & 0x03

            role_lbl = "Examine/Master" if ex else "Level-up"
            merged_slots.append(f"0x{idx:02X} ({role_lbl})")
            merged_slot_ids.append(idx)

            if cost > 0 and ap_val == 0:
                ap_val = cost
            if pwr > power_val:
                power_val = pwr
            for el in _decode_element_bits(ab, vanilla=vanilla):
                if el not in elements:
                    elements.append(el)
            misc_val = int(old_data.get("misc", 0)) if vanilla else int(getattr(ab, "misc", 0))
            if misc_val & 0x20:
                target = "Enemy"
            if ex:
                any_examinable = True
            if stype in (0, 1, 2) and chosen_category == "Skill":
                chosen_category = _SKILL_TYPE_LABELS[stype]
            if not vanilla and (ex != old_ex or stype != old_stype):
                any_changed = True

        if chosen_category == "Skill":
            if target == "Enemy":
                chosen_category = "Attack"
            elif "Psionic" in elements or "Status" in elements:
                chosen_category = "Assist"

        entry: Dict[str, Any] = {
            "id": ab_id,
            "name": name,
            "ap": ap_val,
            "power": power_val,
            "category": chosen_category,
            "element": ", ".join(elements) if elements else "Physical / None",
            "elements": elements,
            "target": target,
            "examinable": any_examinable,
            "merged_slots": merged_slots,
            "merged_slot_ids": merged_slot_ids,
        }
        if not vanilla:
            entry["changed"] = any_changed
            records_list.append(entry)
        records_by_id[ab_id] = entry

    return records_list, records_by_id


def _extract_equipment(
    tables: Mapping[str, Sequence[Any]],
    configs: Mapping[str, Any],
    *,
    vanilla: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Extract normalized Equipment & Items (static stats clean, mutable fields diffed)."""
    equip_catalog = configs.get("equipment_catalog")
    if equip_catalog is None:
        equip_catalog = load_equipment_categories()

    weapon_cat_by_id: Dict[int, str] = {}
    if equip_catalog is not None:
        for cat, ids in equip_catalog.weapons.items():
            for wid in ids:
                weapon_cat_by_id[int(wid)] = cat.rstrip("s").title()

    item_lookup = _build_item_lookup(tables, vanilla=vanilla)
    records_list: List[Dict[str, Any]] = []
    records_by_id: Dict[str, Dict[str, Any]] = {}

    table_sources = (
        (1, "weapons"),
        (2, "armors"),
        (3, "accessories"),
        (0, "items"),
        (4, "key_items"),
    )

    for item_type, table_key in table_sources:
        for obj in sorted(tables.get(table_key, ()), key=lambda o: int(getattr(o, "index", 0))):
            idx = int(getattr(obj, "index", 0))
            info = item_lookup.get((item_type, idx))
            if not info:
                continue

            item_id = info["id"]
            name = info["name"]
            old_data = getattr(obj, "old_data", {})

            cur_price = int(getattr(obj, "price", 0)) if item_type != 4 else 0
            old_price = int(old_data.get("price", cur_price)) if item_type != 4 else 0

            if item_type in (1, 2, 3):
                cur_mask = int(getattr(obj, "equipability", 0))
                old_mask = int(old_data.get("equipability", cur_mask))
            else:
                cur_mask = 0
                old_mask = 0

            if vanilla:
                records_by_id[item_id] = {
                    "id": item_id,
                    "name": name,
                    "price": old_price,
                    "equip": _decode_equip_names(old_mask),
                    "equip_mask": old_mask,
                }
                continue

            # Immutable combat stats (read without diff clutter)
            atk = 0
            dfn = 0
            wt = int(getattr(obj, "weight", 0)) if item_type in (1, 2, 3) else 0
            elements: List[str] = []

            if item_type == 1:
                wcat = weapon_cat_by_id.get(idx, "Weapon")
                kind = f"Weapon ({wcat})"
                atk = int(getattr(obj, "power", 0))
                elements = _decode_element_bits(obj, vanilla=False)
            elif item_type == 2:
                etype = int(getattr(obj, "equip_type", 4))
                kind = _ARMOR_EQUIP_TYPE_LABELS.get(etype, "Armor")
                dfn = int(getattr(obj, "power", 0))
            elif item_type == 3:
                kind = "Accessory"
            elif item_type == 0:
                kind = "Consumable"
            else:
                kind = "Key Item"

            equip_list = _decode_equip_names(cur_mask)
            changed = (cur_price != old_price) or (cur_mask != old_mask)

            entry = {
                "id": item_id,
                "index": idx,
                "item_type": item_type,
                "name": name,
                "kind": kind,
                "stats": {
                    "atk": atk,
                    "def": dfn,
                    "wt": wt,
                    "elements": elements,
                },
                "price": cur_price,
                "equip": equip_list,
                "equip_mask": cur_mask,
                "changed": changed,
            }
            records_list.append(entry)
            records_by_id[item_id] = entry

    return records_list, records_by_id


# ---------------------------------------------------------------------------
# Top-level Vanilla Baseline & Seed Manifest builders
# ---------------------------------------------------------------------------


def build_vanilla_baseline(
    *,
    rom_version: str,
    tables: Optional[Mapping[str, Sequence[Any]]] = None,
    configs: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract an unmodified Vanilla Baseline snapshot from ROM TableObjects' ``old_data``."""
    tbls = tables or {}
    cfgs = configs or {}
    equip_catalog = cfgs.get("equipment_catalog")
    if equip_catalog is None and (tbls.get("weapons") or tbls.get("armors")):
        equip_catalog = load_equipment_categories()

    _, characters_by_id = _extract_characters(
        tbls, vanilla=True, equip_catalog=equip_catalog
    )
    _, masters_by_id = _extract_masters(tbls, vanilla=True)
    _, genes_by_id = _extract_genes(tbls, cfgs, vanilla=True)
    _, shops_by_id = _extract_shops(tbls, cfgs, vanilla=True)
    _, manillos_by_id = _extract_manillos(tbls, vanilla=True)
    _, chests_by_id = _extract_chests(tbls, cfgs, vanilla=True)
    _, monsters_by_slot = _extract_monsters(tbls, cfgs, vanilla=True)
    _, abilities_by_id = _extract_abilities(tbls, vanilla=True)
    _, equipment_by_id = _extract_equipment(tbls, cfgs, vanilla=True)

    return {
        "schema_version": SCHEMA_VERSION,
        "rom_version": str(rom_version),
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": {
            "masters": masters_by_id,
            "characters": characters_by_id,
            "genes": genes_by_id,
            "monsters": monsters_by_slot,
            "abilities": abilities_by_id,
            "equipment": equipment_by_id,
            "shops": shops_by_id,
            "manillos": manillos_by_id,
            "chests": chests_by_id,
        },
    }


def _options_summary(
    options: Any,
    *,
    random_degree: float,
    difficulty: float,
    activated_codes: Sequence[str],
) -> Dict[str, Any]:
    return {
        "class_mode": getattr(options, "class_mode", None) or "legacy",
        "masters": "curated" if bool(getattr(options, "master_kits", False)) else "legacy",
        "genes": str(getattr(options, "gene_mode", "flat")),
        "random_degree": round(float(random_degree), 4),
        "difficulty": round(float(difficulty), 4),
        "exp_mult": float(getattr(options, "exp_mult", 1.0)),
        "zenny_mult": float(getattr(options, "zenny_mult", 1.0)),
        "drop_mult": float(getattr(options, "drop_mult", 1.0)),
        "guardrails": {
            "crash": bool(getattr(options, "crash_guard", True)),
            "tiers": bool(getattr(options, "tier_clamp", True)),
            "weapons": bool(getattr(options, "weapon_guard", True)),
        },
        "codes": sorted({str(c).strip().lower() for c in activated_codes if str(c).strip()}),
    }


def build_seed_manifest(
    *,
    run_id: str,
    seed: Any,
    version: str,
    rom_version: str,
    flags: str,
    share_string: str,
    options: Any,
    preset_name: Optional[str] = None,
    random_degree: float = 0.5,
    difficulty: float = 1.0,
    activated_codes: Sequence[str] = (),
    tables: Optional[Mapping[str, Sequence[Any]]] = None,
    configs: Optional[Mapping[str, Any]] = None,
    assignments: Optional[Mapping[str, Any]] = None,
    guardrail_report: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build a versioned Seed Manifest dictionary for a single randomizer Run."""
    tbls = tables or {}
    cfgs = configs or {}
    asgns = assignments or {}
    equip_catalog = cfgs.get("equipment_catalog")
    if equip_catalog is None:
        equip_catalog = load_equipment_categories()

    norm_flags = "".join(sorted(set(str(flags or "").strip().lower())))
    display_version = str(version) if str(version).startswith("v") else f"v{version}"

    characters_list, _ = _extract_characters(
        tbls,
        vanilla=False,
        options=options,
        flags=norm_flags,
        class_assignments=asgns.get("classes"),
        equip_catalog=equip_catalog,
    )
    classes_catalog = _extract_classes_catalog(cfgs)
    masters_list, _ = _extract_masters(
        tbls,
        vanilla=False,
        options=options,
        flags=norm_flags,
        master_assignments=asgns.get("masters"),
    )
    genes_list, _ = _extract_genes(tbls, cfgs, vanilla=False)
    guardrails_data = _extract_guardrails(guardrail_report, options)
    shops_list, _ = _extract_shops(
        tbls, cfgs, vanilla=False, guardrails_data=guardrails_data
    )
    manillos_list, _ = _extract_manillos(tbls, vanilla=False)
    chests_list, _ = _extract_chests(tbls, cfgs, vanilla=False)
    monsters_list, _ = _extract_monsters(
        tbls, cfgs, vanilla=False, guardrails_data=guardrails_data
    )
    abilities_list, _ = _extract_abilities(tbls, vanilla=False)
    equipment_list, _ = _extract_equipment(tbls, cfgs, vanilla=False)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rom_version": str(rom_version),
        "seed": str(seed),
        "version": display_version,
        "preset": preset_name or (str(getattr(options, "preset", "")).title() if getattr(options, "preset", None) else "Custom"),
        "flags": norm_flags,
        "share_string": str(share_string or ""),
        "options": _options_summary(
            options,
            random_degree=random_degree,
            difficulty=difficulty,
            activated_codes=activated_codes,
        ),
        "categories": {
            "masters": masters_list,
            "characters": characters_list,
            "classes": classes_catalog,
            "genes": genes_list,
            "monsters": monsters_list,
            "abilities": abilities_list,
            "equipment": equipment_list,
            "shops": shops_list,
            "manillos": manillos_list,
            "chests": chests_list,
            "guardrails": guardrails_data,
        },
    }


def _baseline_filename_stem(rom_version: str) -> str:
    return f"vanilla_baseline_{_safe_filename(rom_version)}"


def _ensure_vanilla_baseline(
    output_dir: Path,
    *,
    rom_version: str,
    tables: Optional[Mapping[str, Sequence[Any]]],
    configs: Optional[Mapping[str, Any]],
    force_refresh: bool = False,
) -> Tuple[Path, Path]:
    """Cache the per-ROM-revision Vanilla Baseline (JSON + classic JS wrapper)."""
    stem = _baseline_filename_stem(rom_version)
    json_path = output_dir / f"{stem}.json"
    js_path = output_dir / f"{stem}.js"

    needs_extract = force_refresh or not json_path.exists()
    cached_payload: Optional[Dict[str, Any]] = None
    if not needs_extract:
        try:
            cached_payload = json.loads(json_path.read_text(encoding="utf-8"))
            if (
                not isinstance(cached_payload, dict)
                or cached_payload.get("schema_version") != SCHEMA_VERSION
                or cached_payload.get("rom_version") != str(rom_version)
            ):
                needs_extract = True
        except (OSError, json.JSONDecodeError):
            needs_extract = True

    if needs_extract:
        cached_payload = build_vanilla_baseline(
            rom_version=rom_version,
            tables=tables,
            configs=configs,
        )
        json_path.write_text(
            json.dumps(cached_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        js_path.write_text(
            _wrap_register_script("registerBaseline", cached_payload),
            encoding="utf-8",
        )
    elif not js_path.exists() and cached_payload is not None:
        js_path.write_text(
            _wrap_register_script("registerBaseline", cached_payload),
            encoding="utf-8",
        )

    return json_path, js_path


def rebuild_seed_registry(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    """Scan ``output/seeds/*.json`` and regenerate ``output/seeds/registry.js``.

    Automatically heals manual file deletions, removes orphaned ``.js`` wrappers
    whose ``.json`` was deleted, and skips corrupted JSON files gracefully.
    """
    output_dir = Path(output_dir)
    seeds_dir = output_dir / "seeds"
    seeds_dir.mkdir(parents=True, exist_ok=True)

    runs_meta: List[Dict[str, Any]] = []
    valid_stems: set[str] = set()

    for json_file in sorted(seeds_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not data.get("run_id"):
            continue

        run_id = str(data["run_id"])
        stem = json_file.stem
        valid_stems.add(stem)

        js_file = seeds_dir / f"{stem}.js"
        if not js_file.exists():
            js_file.write_text(
                _wrap_register_script("registerSeed", data),
                encoding="utf-8",
            )

        generated_at = str(data.get("generated_at") or "")
        try:
            mtime = json_file.stat().st_mtime
        except OSError:
            mtime = 0.0

        runs_meta.append(
            {
                "run_id": run_id,
                "seed": str(data.get("seed", "")),
                "preset": str(data.get("preset", "Custom")),
                "rom_version": str(data.get("rom_version", "")),
                "version": str(data.get("version", "")),
                "flags": str(data.get("flags", "")),
                "generated_at": generated_at,
                "script_path": f"output/seeds/{stem}.js",
                "_sort_mtime": mtime,
            }
        )

    for js_file in seeds_dir.glob("*.js"):
        if js_file.name == "registry.js":
            continue
        if js_file.stem not in valid_stems:
            try:
                js_file.unlink()
            except OSError:
                pass

    baselines: Dict[str, str] = {}
    for base_json in sorted(output_dir.glob("vanilla_baseline_*.json")):
        try:
            bdata = json.loads(base_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rom_ver = bdata.get("rom_version") if isinstance(bdata, dict) else None
        if not rom_ver:
            continue
        base_js = base_json.with_suffix(".js")
        if not base_js.exists():
            base_js.write_text(
                _wrap_register_script("registerBaseline", bdata),
                encoding="utf-8",
            )
        baselines[str(rom_ver)] = f"output/{base_js.name}"

    runs_meta.sort(
        key=lambda r: (r["generated_at"], r["_sort_mtime"], r["run_id"]),
        reverse=True,
    )
    for entry in runs_meta:
        entry.pop("_sort_mtime", None)

    registry_payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baselines": baselines,
        "runs": runs_meta,
    }
    registry_path = seeds_dir / "registry.js"
    registry_path.write_text(
        _wrap_register_script("registerRegistry", registry_payload),
        encoding="utf-8",
    )
    return registry_path


def export_companion_wiki_run(
    *,
    seed: Any,
    version: str,
    rom_version: str,
    flags: str,
    share_string: str,
    options: Any,
    preset_name: Optional[str] = None,
    random_degree: float = 0.5,
    difficulty: float = 1.0,
    activated_codes: Sequence[str] = (),
    tables: Optional[Mapping[str, Sequence[Any]]] = None,
    configs: Optional[Mapping[str, Any]] = None,
    assignments: Optional[Mapping[str, Any]] = None,
    guardrail_report: Optional[Any] = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    wiki_html_path: Path = DEFAULT_WIKI_HTML_PATH,
    refresh_baseline: bool = False,
) -> ExportResult:
    """Top-level Companion Wiki exporter entry point invoked after each randomizer Run."""
    out_dir = Path(output_dir)
    seeds_dir = out_dir / "seeds"
    seeds_dir.mkdir(parents=True, exist_ok=True)

    run_id = compute_run_id(
        seed=seed,
        version=version,
        rom_version=rom_version,
        flags=flags,
        options=options,
        random_degree=random_degree,
        difficulty=difficulty,
        activated_codes=activated_codes,
    )

    baseline_json_path, baseline_js_path = _ensure_vanilla_baseline(
        out_dir,
        rom_version=rom_version,
        tables=tables,
        configs=configs,
        force_refresh=refresh_baseline,
    )

    manifest = build_seed_manifest(
        run_id=run_id,
        seed=seed,
        version=version,
        rom_version=rom_version,
        flags=flags,
        share_string=share_string,
        options=options,
        preset_name=preset_name,
        random_degree=random_degree,
        difficulty=difficulty,
        activated_codes=activated_codes,
        tables=tables,
        configs=configs,
        assignments=assignments,
        guardrail_report=guardrail_report,
    )

    manifest_json_path = seeds_dir / f"{run_id}.json"
    manifest_js_path = seeds_dir / f"{run_id}.js"
    manifest_json_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest_js_path.write_text(
        _wrap_register_script("registerSeed", manifest),
        encoding="utf-8",
    )

    registry_js_path = rebuild_seed_registry(out_dir)

    return ExportResult(
        run_id=run_id,
        rom_version=str(rom_version),
        manifest_json_path=manifest_json_path,
        manifest_js_path=manifest_js_path,
        baseline_json_path=baseline_json_path,
        baseline_js_path=baseline_js_path,
        registry_js_path=registry_js_path,
        wiki_html_path=Path(wiki_html_path),
    )


def open_companion_wiki(wiki_html_path: Path = DEFAULT_WIKI_HTML_PATH) -> bool:
    """Open the static Companion Wiki entry page in the system default browser."""
    resolved = Path(wiki_html_path).resolve()
    if not resolved.exists():
        return False
    return bool(webbrowser.open(resolved.as_uri()))
