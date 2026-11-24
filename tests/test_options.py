"""Unit tests for CLI option parsing and EXP / Zenny / drop-rate scaling."""

from __future__ import annotations

import unittest

from genepool.options import (
    GUARDRAIL_CODES,
    MAX_REWARD_UINT16,
    REWARD_CODES,
    RunOptions,
    extract_cli_options,
    resolve_options,
    scale_drop_rate_exp,
    scale_reward,
)


class TestOptionsAndRewards(unittest.TestCase):
    def test_extract_cli_options_strips_named_flags_preserving_positionals(self) -> None:
        argv = [
            "randomizer.py",
            "rom.bin",
            "c_archetypes",
            "424242",
            "--exp-mult",
            "10",
            "--zenny-mult=10",
            "--drop-mult",
            "2",
            "0.5",
            "1.0",
        ]
        opts, remaining = extract_cli_options(argv)
        self.assertEqual(remaining, ["randomizer.py", "rom.bin", "c_archetypes", "424242", "0.5", "1.0"])
        self.assertEqual(opts.exp_mult, 10.0)
        self.assertEqual(opts.zenny_mult, 10.0)
        self.assertEqual(opts.drop_mult, 2.0)

    def test_code_tokens_resolve_and_have_no_substring_collisions(self) -> None:
        # Ensure no alias of one code can accidentally match inside a different code's alias
        for code_a, aliases_a in REWARD_CODES.items():
            for code_b, aliases_b in REWARD_CODES.items():
                if code_a == code_b:
                    continue
                for a in aliases_a:
                    for b in aliases_b:
                        self.assertNotIn(
                            a, b, f"{code_a}:{a!r} is a substring of {code_b}:{b!r}"
                        )

        merged = resolve_options(RunOptions(), ["archetypes", "turbo10x"])
        self.assertEqual(merged.class_mode, "archetypes")
        self.assertEqual(merged.exp_mult, 10.0)
        self.assertEqual(merged.zenny_mult, 10.0)

        # Explicit CLI flag overrides code token
        cli, _ = extract_cli_options(["randomizer.py", "--exp-mult", "5", "--zenny-mult", "2"])
        merged2 = resolve_options(cli, ["turbo10x"])
        self.assertEqual(merged2.exp_mult, 5.0)
        self.assertEqual(merged2.zenny_mult, 2.0)

    def test_scale_reward_clamps_uint16_and_preserves_zero(self) -> None:
        self.assertEqual(scale_reward(0, 10.0), 0)
        self.assertEqual(scale_reward(15, 10.0), 150)
        self.assertEqual(scale_reward(12000, 10.0), MAX_REWARD_UINT16)
        self.assertEqual(scale_reward(1, 0.2), 1)

    def test_scale_drop_rate_exp(self) -> None:
        self.assertEqual(scale_drop_rate_exp(0, 10.0), 0)
        self.assertEqual(scale_drop_rate_exp(3, 2.0), 4)
        self.assertEqual(scale_drop_rate_exp(5, 10.0), 7)

    def test_invalid_cli_values_raise(self) -> None:
        with self.assertRaises(ValueError):
            extract_cli_options(["randomizer.py", "--exp-mult", "0"])
        with self.assertRaises(ValueError):
            extract_cli_options(["randomizer.py", "--zenny-mult", "-2"])
        with self.assertRaises(ValueError):
            extract_cli_options(["randomizer.py", "--class-mode", "invalid"])

    def test_guardrail_override_cli_flags_and_codes(self) -> None:
        # Defaults: all guardrails ON
        opts, rem = extract_cli_options(["randomizer.py", "rom.bin", "acemqt", "123"])
        self.assertTrue(opts.crash_guard)
        self.assertTrue(opts.tier_clamp)
        self.assertTrue(opts.weapon_guard)
        self.assertEqual(rem, ["randomizer.py", "rom.bin", "acemqt", "123"])

        # Granular CLI overrides
        o1, rem1 = extract_cli_options(["randomizer.py", "--no-tier-clamp", "rom.bin"])
        self.assertFalse(o1.tier_clamp)
        self.assertTrue(o1.weapon_guard)
        self.assertTrue(o1.crash_guard)
        self.assertEqual(rem1, ["randomizer.py", "rom.bin"])

        o2, _ = extract_cli_options(["randomizer.py", "--no-weapon-guard"])
        self.assertTrue(o2.tier_clamp)
        self.assertFalse(o2.weapon_guard)

        # Chaos CLI override disables tier + weapon guardrails while keeping crash blacklist ON
        o3, _ = extract_cli_options(["randomizer.py", "--chaos"])
        self.assertFalse(o3.tier_clamp)
        self.assertFalse(o3.weapon_guard)
        self.assertTrue(o3.crash_guard)

        # Flag-string codes resolve properly
        m_chaos = resolve_options(RunOptions(), ["chaos"])
        self.assertFalse(m_chaos.tier_clamp)
        self.assertFalse(m_chaos.weapon_guard)
        self.assertTrue(m_chaos.crash_guard)

        m_tier = resolve_options(RunOptions(), ["notierclamp"])
        self.assertFalse(m_tier.tier_clamp)
        self.assertTrue(m_tier.weapon_guard)

        m_wpn = resolve_options(RunOptions(), ["noweaponguard"])
        self.assertTrue(m_wpn.tier_clamp)
        self.assertFalse(m_wpn.weapon_guard)

        # Cross-code substring collision check across REWARD_CODES and GUARDRAIL_CODES
        combined = {**REWARD_CODES, **GUARDRAIL_CODES}
        for code_a, aliases_a in combined.items():
            for code_b, aliases_b in combined.items():
                if code_a == code_b:
                    continue
                for a in aliases_a:
                    for b in aliases_b:
                        self.assertNotIn(
                            a, b, f"{code_a}:{a!r} is a substring of {code_b}:{b!r}"
                        )
            # Within the same code key, longer aliases must precede shorter substrings
            for idx_a, a in enumerate(aliases_a):
                for idx_b, b in enumerate(aliases_a):
                    if idx_a < idx_b:
                        self.assertNotIn(
                            a, b, f"{code_a}: shorter alias {a!r} precedes {b!r}"
                        )


if __name__ == "__main__":
    unittest.main()
