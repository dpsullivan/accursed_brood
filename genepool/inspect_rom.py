"""Read-only diagnostic inspector for US Breath of Fire III PS1 ROMs.

Extracts ``BIN/ETC/GAME.EMI``, ``BIN/ETC/START.EMI``, and ``BIN/ETC/STATUS.EMI``
into a temporary directory without modifying the source disc image, then prints
vanilla character starting stats, Level 1..99 growth rows, ability metadata,
and equipment tables.

Usage:
    python -m genepool.inspect_rom "workspace/base_files/Breath of Fire III (v1.1) (Track 1).bin"
"""

from __future__ import annotations

import argparse
import os
import struct
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

from randomtools.psx_file_extractor import FileManager
from randomtools.utils import md5hash

# Verified identical across US BOF3 v1.0 ("Vodka Shot") and v1.1 ("Ginseng")
START_BASE_STATS_OFFSET = 0x72914
STATUS_BASE_STATS_OFFSET = 0x1B114
BASE_STATS_COUNT = 8
BASE_STATS_SIZE = 0xA4  # 164 bytes (28 + 32 + 32 + 40 + 32)

GAME_WEAPON_OFFSET = 0x340DC
GAME_WEAPON_COUNT = 83
GAME_WEAPON_SIZE = 24

GAME_ARMOR_OFFSET = 0x348A4
GAME_ARMOR_COUNT = 68
GAME_ARMOR_SIZE = 22

GAME_ACCESSORY_OFFSET = 0x34E7C
GAME_ACCESSORY_COUNT = 52
GAME_ACCESSORY_SIZE = 20

GAME_ABILITY_OFFSET = 0x3570C
GAME_ABILITY_COUNT = 228
GAME_ABILITY_SIZE = 20

GAME_LEVEL_OFFSET = 0x368DC
GAME_LEVEL_CHARS = 7
GAME_LEVEL_PER_CHAR = 99
GAME_LEVEL_SIZE = 8

KNOWN_MD5S = {
    "226771993e29ca5c8e6e2c094c40e8d2": "BOF3_1.0 (Vodka Shot)",
    "9dd9a7c934b8b59d0ce76b0f25d18176": "BOF3_1.1 (Ginseng)",
}

CHARSWAPS = {
    b"\xff": b" ",
    b"\x8b": b"+",
    b"\x3d": b"-",
    b"\x8e": b"'",
    b"\x06": b"$NOCOLOR$",
    b"\x01": b"\n",
    b"\x05\x03": b"$BLUE$",
    b"\x05\x02": b"$RED$",
}

EQUIP_BITS = ("ryu", "nina", "garr", "teepo", "rei", "momo", "peco", "whelp")
SKILL_TYPES = {0: "healing", 1: "assist", 2: "attack", 3: "examine"}


def decode_bof3_str(raw: bytes) -> str:
    data = raw
    for src, dst in CHARSWAPS.items():
        data = data.replace(src, dst)
    return data.decode("ascii", errors="replace").rstrip("\x00").strip()


def extract_core_emis(rom_path: Path) -> Tuple[bytes, bytes, bytes]:
    """Read-only extraction of GAME.EMI, START.EMI, and STATUS.EMI."""
    abs_rom = str(rom_path.resolve())
    prev_cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="accursed_brood_inspect_") as tmpdir:
        try:
            os.chdir(tmpdir)
            fm = FileManager(abs_rom, os.path.join(tmpdir, "root"))
            game_path = fm.export_file(
                os.path.join("BIN", "ETC", "GAME.EMI"), os.path.join(tmpdir, "GAME.EMI")
            )
            start_path = fm.export_file(
                os.path.join("BIN", "ETC", "START.EMI"), os.path.join(tmpdir, "START.EMI")
            )
            status_path = fm.export_file(
                os.path.join("BIN", "ETC", "STATUS.EMI"), os.path.join(tmpdir, "STATUS.EMI")
            )
            if not (game_path and start_path and status_path):
                raise RuntimeError("Failed to export core EMI files from disc image.")
            return (
                Path(game_path).read_bytes(),
                Path(start_path).read_bytes(),
                Path(status_path).read_bytes(),
            )
        finally:
            os.chdir(prev_cwd)


def parse_base_stats(blob: bytes, offset: int) -> List[Dict]:
    records = []
    for idx in range(BASE_STATS_COUNT):
        base = offset + idx * BASE_STATS_SIZE
        chunk = blob[base : base + BASE_STATS_SIZE]
        name = decode_bof3_str(chunk[0:5])
        char_index, level, _unk1 = struct.unpack_from("<BBB", chunk, 5)
        exp, status = struct.unpack_from("<IH", chunk, 8)
        weapon, shield, helmet, armor, acc0, acc1 = struct.unpack_from("<6B", chunk, 14)
        cur_hp, cur_ap = struct.unpack_from("<HH", chunk, 20)
        hp, ap, pwr, dfn, agi, intel = struct.unpack_from("<6H", chunk, 28)
        base_hp, base_ap, base_pwr, base_dfn, base_agi, base_int = struct.unpack_from(
            "<6H", chunk, 60
        )
        healing = [b for b in chunk[92:102] if b]
        assist = [b for b in chunk[102:112] if b]
        attack = [b for b in chunk[112:122] if b]
        skills = [b for b in chunk[122:132] if b]
        records.append(
            {
                "index": idx,
                "name": name,
                "char_index": char_index,
                "level": level,
                "exp": exp,
                "weapon": weapon,
                "shield": shield,
                "helmet": helmet,
                "armor": armor,
                "accessories": [acc0, acc1],
                "current_hp": cur_hp,
                "current_ap": cur_ap,
                "stats": {
                    "hp": hp,
                    "ap": ap,
                    "pwr": pwr,
                    "def": dfn,
                    "agl": agi,
                    "int": intel,
                },
                "base_stats": {
                    "hp": base_hp,
                    "ap": base_ap,
                    "pwr": base_pwr,
                    "def": base_dfn,
                    "agl": base_agi,
                    "int": base_int,
                },
                "healing_abilities": healing,
                "assist_abilities": assist,
                "attack_abilities": attack,
                "skills_abilities": skills,
            }
        )
    return records


def parse_levels(game_blob: bytes) -> Dict[int, List[Dict]]:
    by_char: Dict[int, List[Dict]] = {}
    for c_idx in range(GAME_LEVEL_CHARS):
        rows = []
        for row_idx in range(GAME_LEVEL_PER_CHAR):
            off = GAME_LEVEL_OFFSET + (c_idx * GAME_LEVEL_PER_CHAR + row_idx) * GAME_LEVEL_SIZE
            exp, hp, ap, pwr_dfn, agi_int, ability, unk = struct.unpack_from(
                "<HBBBBBB", game_blob, off
            )
            rows.append(
                {
                    "row": row_idx,
                    "level": row_idx + 1,
                    "exp": exp,
                    "hp": hp,
                    "ap": ap,
                    "pwr": pwr_dfn >> 4,
                    "def": pwr_dfn & 0x0F,
                    "agl": agi_int >> 4,
                    "int": agi_int & 0x0F,
                    "ability": ability,
                    "unknown": unk,
                }
            )
        by_char[c_idx] = rows
    return by_char


def parse_abilities(game_blob: bytes) -> List[Dict]:
    abilities = []
    for idx in range(GAME_ABILITY_COUNT):
        off = GAME_ABILITY_OFFSET + idx * GAME_ABILITY_SIZE
        chunk = game_blob[off : off + GAME_ABILITY_SIZE]
        name = decode_bof3_str(chunk[0:12])
        misc, skill_type, cost, power, element, unk2 = struct.unpack_from("<6B", chunk, 12)
        abilities.append(
            {
                "index": idx,
                "name": name,
                "skill_type": skill_type & 0x03,
                "skill_type_name": SKILL_TYPES[skill_type & 0x03],
                "cost": cost,
                "power": power,
                "element": element,
                "examinable": bool(unk2 & 0x02),
                "default_target_enemy": bool(misc & 0x20),
            }
        )
    return abilities


def parse_weapons(game_blob: bytes) -> List[Dict]:
    items = []
    for idx in range(GAME_WEAPON_COUNT):
        off = GAME_WEAPON_OFFSET + idx * GAME_WEAPON_SIZE
        chunk = game_blob[off : off + GAME_WEAPON_SIZE]
        name = decode_bof3_str(chunk[0:12])
        equip_mask = chunk[12]
        element = chunk[15]
        weight = chunk[16]
        power = chunk[18]
        price = struct.unpack_from("<H", chunk, 22)[0]
        users = [EQUIP_BITS[b] for b in range(8) if equip_mask & (1 << b)]
        items.append(
            {
                "index": idx,
                "name": name,
                "equip_mask": equip_mask,
                "users": users,
                "element": element,
                "weight": weight,
                "power": power,
                "price": price,
            }
        )
    return items


def parse_armors(game_blob: bytes) -> List[Dict]:
    items = []
    for idx in range(GAME_ARMOR_COUNT):
        off = GAME_ARMOR_OFFSET + idx * GAME_ARMOR_SIZE
        chunk = game_blob[off : off + GAME_ARMOR_SIZE]
        name = decode_bof3_str(chunk[0:12])
        equip_mask = chunk[12]
        equip_type = chunk[14]
        weight = chunk[15]
        power = chunk[16]
        price = struct.unpack_from("<H", chunk, 20)[0]
        users = [EQUIP_BITS[b] for b in range(8) if equip_mask & (1 << b)]
        items.append(
            {
                "index": idx,
                "name": name,
                "equip_mask": equip_mask,
                "users": users,
                "equip_type": equip_type,
                "weight": weight,
                "power": power,
                "price": price,
            }
        )
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="Path to US BoF3 Track 1 .bin/.iso")
    parser.add_argument("--weapons", action="store_true", help="Dump all weapons")
    parser.add_argument("--armors", action="store_true", help="Dump all armors")
    parser.add_argument("--abilities", action="store_true", help="Dump all abilities")
    parser.add_argument("--max-rows", type=int, default=15, help="Early growth rows to print")
    args = parser.parse_args()

    digest = md5hash(str(args.rom))
    print(f"ROM: {args.rom.name}")
    print(f"MD5: {digest} -> {KNOWN_MD5S.get(digest, 'UNKNOWN')}")

    game_blob, start_blob, status_blob = extract_core_emis(args.rom)
    start_chars = parse_base_stats(start_blob, START_BASE_STATS_OFFSET)
    status_chars = parse_base_stats(status_blob, STATUS_BASE_STATS_OFFSET)
    print(f"START.EMI vs STATUS.EMI identical: {start_chars == status_chars}\n")

    levels = parse_levels(game_blob)
    abilities = parse_abilities(game_blob)
    ab_by_id = {a["index"]: a for a in abilities}

    print("=== CHARACTERS & EARLY GROWTH ROWS ===")
    for ch in start_chars:
        idx = ch["index"]
        lvl = ch["level"]
        s = ch["stats"]
        print(
            f"[{idx}] {ch['name']:5} Lv{lvl:02d} EXP={ch['exp']:5d} "
            f"HP={s['hp']:3d} AP={s['ap']:3d} PWR={s['pwr']:2d} DEF={s['def']:2d} "
            f"AGL={s['agl']:2d} INT={s['int']:2d} "
            f"(wpn=0x{ch['weapon']:02X} shd=0x{ch['shield']:02X} hlm=0x{ch['helmet']:02X} arm=0x{ch['armor']:02X})"
        )
        start_spells = []
        for bucket in ("healing_abilities", "assist_abilities", "attack_abilities", "skills_abilities"):
            for aid in ch[bucket]:
                ab = ab_by_id[aid]
                start_spells.append(f"{ab['name']}(0x{aid:02X},{bucket[:3]})")
        print(f"    Starting abilities: {', '.join(start_spells) or 'none'}")

        if idx in levels:
            rows = levels[idx]
            # Check delevel using rows[1..lvl-1] vs rows[0..lvl-2]
            for label, sl in (
                ("sub rows[1..L-1] (levels 2..L)", rows[1:lvl]),
                ("sub rows[0..L-2] (levels 1..L-1)", rows[0 : max(0, lvl - 1)]),
                ("sub rows[0..L-1] (levels 1..L)", rows[0:lvl]),
            ):
                if lvl > 1:
                    de = {
                        k: s[k] - sum(r[k] for r in sl)
                        for k in ("hp", "ap", "pwr", "def", "agl", "int")
                    }
                    print(f"    Delevel ({label}): {de}")
            # Totals at Lv 40 and Lv 99 using rows[lvl..39] and rows[lvl..98]
            t40 = {
                k: s[k] + sum(r[k] for r in rows[lvl:40])
                for k in ("hp", "ap", "pwr", "def", "agl", "int")
            }
            t99 = {
                k: s[k] + sum(r[k] for r in rows[lvl:99])
                for k in ("hp", "ap", "pwr", "def", "agl", "int")
            }
            print(f"    Vanilla Lv40 (from rows[L..39]): {t40}")
            print(f"    Vanilla Lv99 (from rows[L..98]): {t99}")

            print(f"    First {args.max_rows} rows (row_idx / level):")
            for r in rows[: args.max_rows]:
                ab_str = f" + {ab_by_id[r['ability']]['name']}(0x{r['ability']:02X})" if r["ability"] else ""
                print(
                    f"      row[{r['row']:02d}] Lv{r['level']:02d}: "
                    f"exp={r['exp']:5d} hp+{r['hp']:2d} ap+{r['ap']:2d} "
                    f"pwr+{r['pwr']:2d} def+{r['def']:2d} agl+{r['agl']:2d} int+{r['int']:2d}{ab_str}"
                )
            learned = [
                f"Lv{r['level']:02d}:{ab_by_id[r['ability']]['name']}(0x{r['ability']:02X},t={ab_by_id[r['ability']]['skill_type']},ex={ab_by_id[r['ability']]['examinable']})"
                for r in rows
                if r["ability"]
            ]
            print(f"    Level-up spells ({len(learned)}): {', '.join(learned)}")
        print()

    if args.weapons:
        print("=== WEAPONS ===")
        for w in parse_weapons(game_blob):
            print(
                f"0x{w['index']:02X} {w['name']:14} mask=0x{w['equip_mask']:02X} "
                f"pwr={w['power']:3d} wt={w['weight']:2d} price={w['price']:5d} users={','.join(w['users'])}"
            )

    if args.armors:
        print("=== ARMORS ===")
        for a in parse_armors(game_blob):
            print(
                f"0x{a['index']:02X} {a['name']:14} type={a['equip_type']} mask=0x{a['equip_mask']:02X} "
                f"pwr={a['power']:3d} wt={a['weight']:2d} price={a['price']:5d} users={','.join(a['users'])}"
            )

    if args.abilities:
        print("=== ABILITIES ===")
        for ab in abilities:
            if ab["name"]:
                print(
                    f"0x{ab['index']:02X} {ab['name']:14} type={ab['skill_type']}({ab['skill_type_name']:7}) "
                    f"ex={int(ab['examinable'])} cost={ab['cost']:2d} pwr={ab['power']:3d} "
                    f"elem=0x{ab['element']:02X} enemy={int(ab['default_target_enemy'])}"
                )


if __name__ == "__main__":
    main()
