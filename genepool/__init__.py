"""Accursed Brood (Breath of Fire III Structured Randomizer) core package.

``genepool`` holds the ROM-independent authoring schema, deterministic Growth
Compiler, curated class/archetype assignment logic, wiki exporter, and thin
adapters that hand compiled payloads off to ``randomizer.py`` / ``randomtools``.
"""

__all__ = [
    "schema",
    "growth_compiler",
    "class_assigner",
    "wiki_export",
    "rom_adapter",
    "options",
    "guardrails",
]
