"""Unit tests for CLI option parsing and EXP / Zenny / drop-rate scaling."""

from __future__ import annotations

import unittest

from genepool.options import (
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


if __name__ == "__main__":
    unittest.main()
