# Breath of Fire III (US PS1) ROM Tables Reference

Reference for the PS1 binary tables used by **Accursed Brood** (`randomizer.py`, `tables/`, and `genepool/`). All character, level-up, ability, and equipment layouts below were verified directly against US `BOF3_1.1` ("Ginseng") via `python -m genepool.inspect_rom` and cross-checked against `tables/tables_list_1.0.txt` and `tables/tables_list_1.1.txt`.

For broader US SLUS-00422 file format documentation, EMI archive specs, and decompilation notes, see the upstream community wiki:
- **bof3-wiki:** https://raulcorreia7.github.io/bof3-wiki/
- **bof3-tools / bof3-decomp:** https://github.com/raulcorreia7/bof3-tools

---

## Supported ROM Versions (`tables/master.txt`)

| Label | Codename | MD5 (Track 1 `.bin`) | Table Manifest |
|---|---|---|---|
| `BOF3_1.0` | Vodka Shot | `226771993e29ca5c8e6e2c094c40e8d2` | `tables/tables_list_1.0.txt` |
| `BOF3_1.1` | Ginseng | `9dd9a7c934b8b59d0ce76b0f25d18176` | `tables/tables_list_1.1.txt` |

All character, level-up, ability, weapon, armor, accessory, and master table offsets are **identical** between v1.0 and v1.1. Version differences are confined to Manillo stock/trades, area chest/formation/monster pointer tables, `patch_fast_text`, and seed/master menu text addresses.

---

## Core Table Offsets

| `TableObject` | Subfile & Offset | Count | Record Size | Spec File |
|---|---|---|---|---|
| `BaseStatsObject` | `0x72914@BIN/ETC/START.EMI` | 8 | `164 B` (`0xA4`) | `tables/struct_base_stats.txt` |
| `BaseStats2Object` | `0x1B114@BIN/ETC/STATUS.EMI` | 8 | `164 B` (`0xA4`) | `tables/struct_base_stats.txt` |
| `LevelObject` | `0x368DC@BIN/ETC/GAME.EMI` | 693 (`7 × 99`) | `8 B` | `tables/struct_level.txt` |
| `AbilityObject` | `0x3570C@BIN/ETC/GAME.EMI` | 228 (`0x00..0xE3`) | `20 B` | `tables/struct_ability.txt` |
| `WeaponObject` | `0x340DC@BIN/ETC/GAME.EMI` | 83 (`0x00..0x52`) | `24 B` | `tables/struct_weapon.txt` |
| `ArmorObject` | `0x348A4@BIN/ETC/GAME.EMI` | 68 (`0x00..0x43`) | `22 B` | `tables/struct_armor.txt` |
| `AccessoryObject` | `0x34E7C@BIN/ETC/GAME.EMI` | 52 (`0x00..0x33`) | `20 B` | `tables/struct_accessory.txt` |
| `ShopObject` | `0x3528C@BIN/ETC/GAME.EMI` | 40 | `23 B` | `tables/struct_shop.txt` |
| `MasterSkillsObject` | `0x03C88@BIN/ETC/SISYOU.EMI` | 17 | `12 B` | `tables/struct_master_skills.txt` |
| `MasterStatsObject` | `0x03D54@BIN/ETC/SISYOU.EMI` | 17 | `6 B` | `tables/struct_master_stats.txt` |

---

## Character Starting Stats (`BaseStatsObject` & `BaseStats2Object`)

- **Size:** `164 bytes` (`0xA4`), little-endian.
- **Mirroring:** `START.EMI` (`0x72914`) and `STATUS.EMI` (`0x1B114`) are byte-for-byte identical in vanilla and must stay synchronized (`BaseStats2Object.cleanup()` mirrors `BaseStatsObject`).
- **Character indices (`0..7`):**

| Index | Name | Vanilla Join Lv | `START.EMI` Stats (HP/AP/PWR/DEF/AGL/INT) | De-leveled Lv 1 (`START - sum(rows[1..L-1])`) | Vanilla Lv 40 | Vanilla Lv 99 | Playable Class Target? |
|---:|---|---:|---|---|---|---|---|
| 0 | Ryu | 1 | `20 / 11 / 12 / 10 / 8 / 10` | `20 / 11 / 12 / 10 / 8 / 10` | `227 / 154 / 144 / 100 / 49 / 127` | `328 / 228 / 207 / 146 / 91 / 187` | Yes |
| 1 | Nina | 5 | `27 / 33 / 13 / 13 / 14 / 24` | `17 / 18 / 9 / 8 / 11 / 16` | `152 / 224 / 72 / 70 / 55 / 153` | `220 / 321 / 102 / 112 / 100 / 229` | Yes |
| 2 | Garr | 13 | `99 / 7 / 58 / 44 / 17 / 21` | `30 / 0 / 20 / 16 / 11 / 5` | `270 / 29 / 174 / 128 / 36 / 63` | `384 / 47 / 252 / 189 / 63 / 98` | Yes |
| 3 | Teepo | 1 | `22 / 13 / 13 / 10 / 10 / 12` | `22 / 13 / 13 / 10 / 10 / 12` | `234 / 169 / 148 / 107 / 55 / 134` | `335 / 243 / 211 / 153 / 101 / 194` | No (prologue only) |
| 4 | Rei | 5 | `42 / 12 / 23 / 15 / 19 / 22` | `26 / 6 / 15 / 11 / 16 / 14` | `203 / 68 / 120 / 92 / 68 / 95` | `285 / 108 / 178 / 144 / 123 / 139` | Yes |
| 5 | Momo | 10 | `52 / 40 / 30 / 25 / 15 / 50` | `22 / 15 / 12 / 10 / 9 / 20` | `194 / 143 / 116 / 83 / 42 / 185` | `272 / 212 / 178 / 124 / 74 / 267` | Yes |
| 6 | Peco | 1 | `40 / 8 / 18 / 14 / 3 / 4` | `40 / 8 / 18 / 14 / 3 / 4` | `333 / 122 / 155 / 122 / 25 / 41` | `458 / 193 / 236 / 196 / 41 / 57` | Yes |
| 7 | Whelp | 0 | `15 / 15 / 10 / 8 / 4 / 8` | N/A (no `LevelObject` rows) | N/A | N/A | No (prologue only) |

### Record Byte Map (`0x00..0xA3`)

| Offset | Size | Field(s) | Notes |
|---|---:|---|---|
| `0x00` | 5 | `character_name` | Custom ASCII (`0xFF` = space/padding) |
| `0x05` | 3 | `character_index`, `level`, `unknown1` | `level` is the vanilla join level `L` |
| `0x08` | 6 | `exp` (4B), `status` (2B) | |
| `0x0E` | 6 | `weapon`, `shield`, `helmet`, `armor`, `accessories[2]` | Item indices (`0` = empty) |
| `0x14` | 8 | `current_hp` (2B), `current_ap` (2B), `current_willpower`, `innoculation`, `fatigue`, `master` | `current_hp`/`current_ap` must match `hp`/`ap` |
| `0x1C` | 32 | Active stat block: `hp`, `ap`, `pwr`, `dfn`, `agi`, `int` (6×2B), `unknown2` (2B), `willpower` (1B), `resistances` (9B), `surprise..accuracy` (5B), `unknown3` (3B) | |
| `0x3C` | 32 | Base stat mirror block: `base_hp..base_accuracy`, `unknown5` (3B) | Must match active stat block |
| `0x5C` | 40 | Starting spell buckets: `healing_abilities` (10B), `assist_abilities` (10B), `attack_abilities` (10B), `skills_abilities` (10B) | `0`-padded `AbilityObject` indices; max **10 per bucket** |
| `0x84` | 32 | `unknown6` | |

---

## 1–99 Level-Up Stat & Spell Table (`LevelObject`)

- **Location:** `0x368DC@BIN/ETC/GAME.EMI`, **693 records** (`7 characters × 99 levels`; Whelp index 7 has no rows).
- **Indexing:** `char_index = index // 99`, `row_index = index % 99` (`0..98`), `level = row_index + 1` (`1..99`).
- **Record Layout (`8 bytes`):**

| Offset | Size | Field | Range / Encoding |
|---|---:|---|---|
| `0x00` | 2 | `exp` | uint16 |
| `0x02` | 1 | `hp` | uint8 (`0..255`) |
| `0x03` | 1 | `ap` | uint8 (`0..255`) |
| `0x04` | 1 | `pwr_dfn` | **Upper nibble (`>> 4`) = PWR (`0..15`)**, **Lower nibble (`& 0x0F`) = DEF (`0..15`)** |
| `0x05` | 1 | `agi_int` | **Upper nibble (`>> 4`) = AGL (`0..15`)**, **Lower nibble (`& 0x0F`) = INT (`0..15`)** |
| `0x06` | 1 | `ability` | `AbilityObject` index (`0x00` = none) |
| `0x07` | 1 | `unknown` | uint8 |

### Verified Indexing & Join-Level Normalization Rule
- **Row 0 (`level = 1`):** Always has all 6 stat gains equal to `0` (`hp=ap=pwr=def=agl=int=0`) and `exp=0`. Its only active payload is the Lv 1 starting spell (if any).
- **Rows `1..98` (`level = 2..99`):** Row `k` holds the exact integer stat gains and spell learned when leveling **from Level `k` to Level `k + 1`**.
- **Join-Level > 1 Characters (Nina Lv 5, Rei Lv 5, Momo Lv 10, Garr Lv 13):** All early rows `1..L-1` are populated with real growth values in vanilla `GAME.EMI`.
- **Exact Normalization Formula:** For a character joining at level `L` (`1 <= L <= 99`):
  - Starting stats written to `START.EMI` & `STATUS.EMI`: `base_lv1 + sum(rows[1 .. L-1])`
  - Starting spells written to `START.EMI` & `STATUS.EMI`: every spell in `rows[0 .. L-1]` (`level <= L`), bucketed by `ability.skill_type & 0x03`.
  - Stat total at any target level `T` (`1 <= T <= 99`): `base_lv1 + sum(rows[1 .. T-1])`.

---

## Abilities (`AbilityObject`)

- **Location:** `0x3570C@BIN/ETC/GAME.EMI`, **228 records** (`0x00..0xE3`), `20 bytes` each.
- **`skill_type & 0x03` buckets:**
  - `0` = Healing (`healing_abilities`)
  - `1` = Assist (`assist_abilities`)
  - `2` = Attack (`attack_abilities`)
  - `3` = Examine/Master (`skills_abilities`)
- **Dual-ID Quirk:** Core spells exist twice in `AbilityObject`:
  - **Level-up IDs (`examinable = 0`, `skill_type ∈ {0, 1, 2}`):** e.g., `Heal = 0x46`, `Protect = 0x52`, `Flare = 0x5B`, `Frost = 0x5E`, `Jolt = 0x61`, `Cyclone = 0x64`, `Quake = 0x66`, `Pilfer = 0x41`, `Gambit = 0x02`, `Pyrokinesis = 0x9B`.
  - **Examine/Master IDs (`examinable = 1`, `skill_type = 3`):** e.g., `Heal = 0xAE`, `Protect = 0xB8`, `Flare = 0xC1`, `Steal = 0xD8`.
  - Character level-up tables **must** use the non-examinable level-up IDs so they never collide with Master/Enemy skills. (Vanilla exceptions: Ryu's Lv 36 `Bonebreak 0x15` has `ex=1, type=2`, and Garr's Lv 1 `Flame Strike 0x05` has `ex=1, type=3` while `START.EMI` gives Garr `Pyrokinesis 0x9B` instead.)
- **Known Crash / Banned Skills:** `0x01 Nue Stomp`, `0x80 Head Cracker` (banned globally); `0xA5 Backhand` (banned from character level-up tables, guaranteed on a Master).

---

## Equipment & Permission Bitmasks

All three equipment tables store a 1-byte LSB-first `equipability` bitmask at offset `+0x0C`:

| Bit | Mask | Character | Notes |
|---:|---|---|---|
| 0 | `0x01` | `ryu` | Permanent party |
| 1 | `0x02` | `nina` | Permanent party |
| 2 | `0x04` | `garr` | Permanent party |
| 3 | `0x08` | `teepo` | Prologue only — keep prologue gear usable |
| 4 | `0x10` | `rei` | Permanent party |
| 5 | `0x20` | `momo` | Permanent party; `0x4B HE Shells` forced usable by Momo |
| 6 | `0x40` | `peco` | Permanent party |
| 7 | `0x80` | `whelp` | Prologue only |

- **Permanent party mask:** `0x77` (`ryu | nina | garr | rei | momo | peco`).
- **`ArmorObject.equip_type`:** `2` = Shields/Bracers/Gloves (`0x32..0x42`), `3` = Helmets/Headgear (`0x21..0x31`), `4` = Body Armor (`0x01..0x20`, `0x43`).
- **Weapon ID ranges (`0x01..0x52`):**
  - Daggers & Knives: `0x01, 0x02, 0x05, 0x06, 0x0B, 0x0C, 0x0E, 0x1B, 0x41..0x44`
  - Swords: `0x03, 0x04, 0x07..0x0A, 0x0D, 0x0F..0x1A, 0x1C, 0x45`
  - Staves & Rods: `0x1D..0x28`
  - Spears & Polearms: `0x29..0x36, 0x52`
  - Claws & Knuckles: `0x37..0x40`
  - Cannons / Shells: `0x46..0x51`

---

## PS1 & Upstream `vast_violence` Quirks Fixed in Accursed Brood

1. **Nibble Bounds:** `pwr`, `def`, `agl`, `int` per-level gains are strictly `0..15`; `hp` and `ap` are `0..255`.
2. **Upstream `LevelObject.set_stat()` bug:** Upstream never called `setattr()` on `pwr_dfn` or `agi_int` (silently discarding all 4 core stat growth mutations). Fixed in `randomizer.py`.
3. **Upstream `relevel_stats()` off-by-two bug:** Upstream summed `levels[0..level]` instead of `levels[1..level-1]`. Fixed to use `rows[1..L-1]`.
4. **Upstream `BaseStatsObject.cleanup()` bugs:** Fixed discarded `self.accessories` assignment and nonexistent `max_hp`/`base_max_hp` attributes (`hp`/`base_hp`).
5. **Prologue protection:** `BaseStatsObject.mutate_valid` excludes `Teepo` and `Whelp` so prologue characters are not corrupted.
6. **Hardcoded story guards preserved:** Momo's `HE Shells` (`0x4B`), shop `0x0D` `Flame Chrysm` (`0x47`), `Pilfer`/`Steal` availability fallback on Ryu, `Backhand` Master availability, and vanilla stats for `Gary` and `Mogu`.
