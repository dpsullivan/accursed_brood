"""Zero-ROM unit tests for Named Presets, CLI resolution, and copyable Share Strings."""

from __future__ import annotations

import shlex
import unittest

from genepool.options import (
    FEATURE_CODES,
    GUARDRAIL_CODES,
    PRESET_CODES,
    REWARD_CODES,
    RunOptions,
    extract_cli_options,
    resolve_options,
)
from genepool.presets import (
    apply_preset_to_argv,
    format_share_string,
    get_preset,
    load_presets,
)


class TestPresetsAndShareStrings(unittest.TestCase):
    def test_presets_load_and_match_design_invariants(self) -> None:
        presets = load_presets()
        self.assertEqual(set(presets.keys()), {"standard", "fiesta", "chaos"})

        std = presets["standard"]
        self.assertEqual(std.class_mode, "archetypes")
        self.assertTrue(std.master_kits)
        self.assertEqual(std.gene_mode, "tiered")
        self.assertTrue(std.crash_guard)
        self.assertTrue(std.tier_clamp)
        self.assertTrue(std.weapon_guard)
        self.assertEqual(std.exp_mult, 1.0)

        fiesta = presets["fiesta"]
        self.assertEqual(fiesta.class_mode, "archetypes")
        self.assertTrue(fiesta.master_kits)
        self.assertEqual(fiesta.gene_mode, "tiered_bleed")
        self.assertTrue(fiesta.crash_guard)
        self.assertTrue(fiesta.tier_clamp)
        self.assertTrue(fiesta.weapon_guard)
        self.assertEqual(fiesta.exp_mult, 2.0)
        self.assertEqual(fiesta.zenny_mult, 2.0)

        chaos = presets["chaos"]
        self.assertIsNone(chaos.class_mode)
        self.assertFalse(chaos.master_kits)
        self.assertEqual(chaos.gene_mode, "flat")
        self.assertTrue(chaos.crash_guard)  # PS1 stability stays ON by default
        self.assertFalse(chaos.tier_clamp)
        self.assertFalse(chaos.weapon_guard)
        self.assertGreater(chaos.random_degree, std.random_degree)

        with self.assertRaises(ValueError):
            get_preset("nonexistent", presets=presets)

    def test_preset_cli_overrides_and_precedence(self) -> None:
        presets = load_presets()

        # Fiesta default 2x EXP/Zenny overridden cleanly to 10x
        cli, rem = extract_cli_options(
            ["randomizer.py", "rom.bin", "--preset", "fiesta", "--exp-mult", "10", "--zenny-mult", "10"],
            presets=presets,
        )
        opts = resolve_options(cli, [], presets=presets)
        self.assertEqual(opts.preset, "fiesta")
        self.assertEqual(opts.class_mode, "archetypes")
        self.assertTrue(opts.master_kits)
        self.assertEqual(opts.gene_mode, "tiered_bleed")
        self.assertEqual(opts.exp_mult, 10.0)
        self.assertEqual(opts.zenny_mult, 10.0)

        # Chaos preset with crash guard disabled explicitly, plus opting into curated Master Kits
        cli2, _ = extract_cli_options(
            ["randomizer.py", "rom.bin", "--preset=chaos", "--no-crash-guard", "--master-kits", "--gene-mode", "tiered"],
            presets=presets,
        )
        opts2 = resolve_options(cli2, [], presets=presets)
        self.assertEqual(opts2.preset, "chaos")
        self.assertFalse(opts2.crash_guard)
        self.assertFalse(opts2.tier_clamp)
        self.assertFalse(opts2.weapon_guard)
        self.assertTrue(opts2.master_kits)
        self.assertEqual(opts2.gene_mode, "tiered")

        # Standard preset overridden to legacy class mode and no master kits
        cli3, _ = extract_cli_options(
            ["randomizer.py", "rom.bin", "--preset", "standard", "--class-mode", "legacy", "--no-master-kits"],
            presets=presets,
        )
        opts3 = resolve_options(cli3, [], presets=presets)
        self.assertIsNone(opts3.class_mode)
        self.assertFalse(opts3.master_kits)

        # Flag-string preset code + CLI override precedence
        cli4, _ = extract_cli_options(["randomizer.py", "--exp-mult", "5"], presets=presets)
        opts4 = resolve_options(cli4, ["fiestarun", "turbo10x"], presets=presets)
        self.assertEqual(opts4.preset, "fiesta")
        self.assertEqual(opts4.exp_mult, 5.0)  # CLI wins over turbo10x and fiesta
        self.assertEqual(opts4.zenny_mult, 10.0)  # turbo10x wins over fiesta 2x

    def test_apply_preset_to_argv_preserves_explicit_positionals(self) -> None:
        presets = load_presets()

        # Minimal preset invocation fills flags, empty seed, randomness, difficulty
        cli, rem = extract_cli_options(
            ["randomizer.py", "rom.bin", "--preset", "chaos", "--seed", "424242"],
            presets=presets,
        )
        expanded = apply_preset_to_argv(rem, cli, presets=presets)
        self.assertEqual(expanded, ["randomizer.py", "rom.bin", "acegmnqst", "424242", "0.85", "1"])

        # Explicit positional flags & randomness are preserved
        cli2, rem2 = extract_cli_options(
            ["randomizer.py", "rom.bin", "acemg", "12345", "0.7", "1.2", "--preset", "standard"],
            presets=presets,
        )
        expanded2 = apply_preset_to_argv(rem2, cli2, presets=presets)
        self.assertEqual(expanded2, ["randomizer.py", "rom.bin", "acemg", "12345", "0.7", "1.2"])

        # Legacy invocation without preset stays untouched
        cli3, rem3 = extract_cli_options(["randomizer.py", "rom.bin", "acemqt", "12345"], presets=presets)
        expanded3 = apply_preset_to_argv(rem3, cli3, presets=presets)
        self.assertEqual(expanded3, ["randomizer.py", "rom.bin", "acemqt", "12345"])

    def test_share_string_roundtrip(self) -> None:
        presets = load_presets()
        cases = [
            (["--preset", "standard", "--seed", "424242"], "acegmnqst", 424242, 0.5, 1.0),
            (
                ["--preset", "fiesta", "--seed", "777", "--exp-mult", "10", "--zenny-mult", "10", "--class-mode", "roleswap"],
                "acegmnqst",
                777,
                0.5,
                1.0,
            ),
            (
                ["--preset", "chaos", "--seed", "999", "--flags", "acemg", "--no-crash-guard", "--master-kits"],
                "acegm",
                999,
                0.85,
                1.0,
            ),
            (
                ["acemgt", "555", "0.6", "1.1", "--class-mode", "archetypes", "--master-kits", "--gene-mode", "tiered"],
                "acegmt",
                555,
                0.6,
                1.1,
            ),
        ]

        for extra_args, exp_flags, exp_seed, exp_rand, exp_diff in cases:
            cli1, rem1 = extract_cli_options(["randomizer.py", "rom.bin", *extra_args], presets=presets)
            argv1 = apply_preset_to_argv(rem1, cli1, presets=presets)
            opts1 = resolve_options(cli1, [], presets=presets)

            share = format_share_string(
                opts1,
                flags=exp_flags,
                seed=exp_seed,
                random_degree=exp_rand,
                difficulty=exp_diff,
                presets=presets,
            )

            # Parse the share string back as CLI arguments
            parsed_tokens = shlex.split(share)
            cli2, rem2 = extract_cli_options(["randomizer.py", "rom.bin", *parsed_tokens], presets=presets)
            argv2 = apply_preset_to_argv(rem2, cli2, presets=presets)
            opts2 = resolve_options(cli2, [], presets=presets)

            self.assertEqual(opts2.preset, opts1.preset, share)
            self.assertEqual(opts2.class_mode, opts1.class_mode, share)
            self.assertEqual(opts2.master_kits, opts1.master_kits, share)
            self.assertEqual(opts2.gene_mode, opts1.gene_mode, share)
            self.assertEqual(opts2.exp_mult, opts1.exp_mult, share)
            self.assertEqual(opts2.zenny_mult, opts1.zenny_mult, share)
            self.assertEqual(opts2.drop_mult, opts1.drop_mult, share)
            self.assertEqual(opts2.crash_guard, opts1.crash_guard, share)
            self.assertEqual(opts2.tier_clamp, opts1.tier_clamp, share)
            self.assertEqual(opts2.weapon_guard, opts1.weapon_guard, share)
            self.assertEqual(argv2[2], exp_flags, share)
            self.assertEqual(int(argv2[3]), exp_seed, share)
            self.assertAlmostEqual(float(argv2[4]), exp_rand, places=5, msg=share)
            self.assertAlmostEqual(float(argv2[5]), exp_diff, places=5, msg=share)

    def test_all_codes_have_zero_substring_collisions(self) -> None:
        legacy_codes = {
            "archetypes": ["archetypes", "classes"],
            "roleswap": ["roleswap", "vanillaswap"],
            "easymodo": ["easymodo"],
            "equipanything": ["equipanything"],
            "feyday": ["feyday", "faeday"],
            "thinkwell": ["thinkwell"],
            "bluemagician": ["bluemagician", "bluemage"],
            "abilonym": ["abilonym"],
        }
        combined = {
            **legacy_codes,
            **REWARD_CODES,
            **GUARDRAIL_CODES,
            **FEATURE_CODES,
            **PRESET_CODES,
        }
        for code_a, aliases_a in combined.items():
            for code_b, aliases_b in combined.items():
                if code_a == code_b:
                    continue
                for a in aliases_a:
                    for b in aliases_b:
                        self.assertNotIn(
                            a, b, f"{code_a}:{a!r} is a substring of {code_b}:{b!r}"
                        )
            for idx_a, a in enumerate(aliases_a):
                for idx_b, b in enumerate(aliases_a):
                    if idx_a < idx_b:
                        self.assertNotIn(
                            a, b, f"{code_a}: shorter alias {a!r} precedes {b!r}"
                        )


if __name__ == "__main__":
    unittest.main()
