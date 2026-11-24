"""Standalone wiki-ready JSON exporter for Accursed Brood classes.

Usage:
    python -m genepool.wiki_export
    python -m genepool.wiki_export --input data/classes.json --output data/generated/classes_wiki.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .growth_compiler import (
    LV40_GRADE_THRESHOLDS,
    CompiledClass,
    compile_class,
    normalize_for_join_level,
)
from .schema import (
    DATA_DIR,
    DEFAULT_CLASSES_PATH,
    DEFAULT_EQUIPMENT_PATH,
    PLAYABLE_CHARACTERS,
    STATS,
    VANILLA_JOIN_LEVELS,
    ClassDefinition,
    load_classes,
    load_equipment_categories,
)

DEFAULT_WIKI_OUTPUT_PATH = DATA_DIR / "generated" / "classes_wiki.json"


def export_class_entry(compiled: CompiledClass) -> Dict[str, Any]:
    """Serialize one compiled class into a companion-wiki JSON record."""
    defn = compiled.definition
    join_previews = {
        char: {
            "join_level": VANILLA_JOIN_LEVELS[char],
            "stats": normalize_for_join_level(compiled, VANILLA_JOIN_LEVELS[char]).stats,
        }
        for char in PLAYABLE_CHARACTERS
    }
    return {
        "id": defn.id,
        "name": defn.name,
        "role": defn.role,
        "description": defn.description,
        "curve": defn.curve,
        "weapons": list(defn.weapons),
        "equipment": list(defn.equipment),
        "growth_per_level": dict(defn.growth_per_level),
        "totals": {
            "lv1": dict(compiled.totals_lv1),
            "lv40": dict(compiled.totals_lv40),
            "lv99": dict(compiled.totals_lv99),
        },
        "bst": {
            "lv1": sum(compiled.totals_lv1.values()),
            "lv40": sum(compiled.totals_lv40.values()),
            "lv99": sum(compiled.totals_lv99.values()),
        },
        "grades_lv40": dict(compiled.grades_lv40),
        "spells": [sp.to_dict() for sp in defn.spells],
        "join_previews": join_previews,
    }


def build_wiki_payload(classes: List[ClassDefinition]) -> Dict[str, Any]:
    """Compile all classes and assemble the top-level wiki JSON document."""
    compiled_entries = [export_class_entry(compile_class(c)) for c in classes]
    return {
        "schema_version": 1,
        "project": "Accursed Brood",
        "grading_level": 40,
        "stats_order": list(STATS),
        "grade_thresholds_lv40": {
            stat: {
                "S": cutoffs[0],
                "A": cutoffs[1],
                "B": cutoffs[2],
                "C": cutoffs[3],
                "D": cutoffs[4],
            }
            for stat, cutoffs in LV40_GRADE_THRESHOLDS.items()
        },
        "class_count": len(compiled_entries),
        "classes": compiled_entries,
    }


def write_wiki_json(
    input_path: Path = DEFAULT_CLASSES_PATH,
    equipment_path: Optional[Path] = DEFAULT_EQUIPMENT_PATH,
    output_path: Path = DEFAULT_WIKI_OUTPUT_PATH,
) -> Dict[str, Any]:
    """Load classes, compile, write formatted JSON to ``output_path``, and return payload."""
    equip = load_equipment_categories(equipment_path) if equipment_path else None
    classes = load_classes(input_path, equipment_catalog=equip)
    payload = build_wiki_payload(classes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_CLASSES_PATH)
    parser.add_argument("--equipment", type=Path, default=DEFAULT_EQUIPMENT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_WIKI_OUTPUT_PATH)
    args = parser.parse_args()

    payload = write_wiki_json(
        input_path=args.input,
        equipment_path=args.equipment,
        output_path=args.output,
    )
    print(f"Exported {payload['class_count']} classes to {args.output}")


if __name__ == "__main__":
    main()
