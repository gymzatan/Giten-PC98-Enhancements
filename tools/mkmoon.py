#!/usr/bin/env python3
"""Write tools/moon.json: the moon table the game multiplies damage by, for the numeric editor.

    mkmoon.py [--guide [PDF]]

ET0003.BIN is loaded as it is on disk (ov08:12E0 -> ov20:0216, which reads without the XOR the other tables
get; tables.chunks_of would decrypt it into noise): a length word, then 28 bytes per 月齢対応 number, one for
each moon age 0-27 - the screen's 1/28 to 28/28, 15/28 the full moon. Every sword, gun and magic damage is
multiplied by 2v/100 with v = table[attacker's 月齢対応][moon age] (25CA:8E68 -> 8E4A), so 50 is x1. The
月齢対応 number is P2 +58h, copied into a character's record at +1F8h when the record is built (ov32:1068).

--guide reads the curve the unofficial guide draws on each demon's page (run/moon_from_pdf.py) and checks that
every day of every curve is this table's value cut into the guide's five heights: v <= 40 弱い, 45-50 普通,
55-70 やや強い, 75-100 強い, 110 and up かなり強い (no value of the table falls between those ranges).
tools/mkeditor.py writes the file again before every build of the exe."""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
SRC = os.path.join(WORK, "files", "DDS98", "ET0003.BIN")
PATH = os.path.join(HERE, "moon.json")
DAYS = 28


def table(path=SRC):
    data = open(path, "rb").read()
    size = struct.unpack_from("<H", data, 0)[0]
    if size % DAYS or len(data) < 2 + size:
        raise SystemExit(f"ET0003：长度字 {size} 不是 {DAYS} 的倍数，或文件只有 {len(data)} 字节")
    body = data[2:2 + size]
    return [list(body[r * DAYS:(r + 1) * DAYS]) for r in range(size // DAYS)]


def height(v):
    """The guide's five heights for a table value."""
    return 0 if v < 45 else 1 if v <= 50 else 2 if v <= 70 else 3 if v < 110 else 4


def check_guide(rows, pdf=None):
    sys.path.insert(0, os.path.join(WORK, "run"))
    import moon_from_pdf  # noqa: E402
    curves, split, demons = moon_from_pdf.read(pdf or moon_from_pdf.PDF)
    bad = [n for n, curve in curves.items() if n >= len(rows) or [height(v) for v in rows[n]] != curve]
    print(f"攻略本：{demons} 体、{len(curves)} 种曲线，{'同号一致' if not split else f'{split} 同号不一致'}；"
          f"与表按五档切分{'全部吻合' if not bad else f'不吻合：{bad}'}")
    return not bad and not split


def main(guide=False, pdf=None):
    rows = table()
    note = ("ET0003：每个月龄对应一行，28 个数对应月龄 0-27（画面 1/28-28/28，15/28 满月）。"
            "伤害乘以 2v/100，50 = ×1。由 tools/mkmoon.py 生成。")
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump({"_note": note, "rows": rows}, f, ensure_ascii=False)
        f.write("\n")
    print(f"{PATH}：{len(rows)} 行，倍率 ×{min(map(min, rows)) / 50:g} ~ ×{max(map(max, rows)) / 50:g}")
    if guide and not check_guide(rows, pdf):
        raise SystemExit("月龄表与攻略本曲线不符")
    return rows


if __name__ == "__main__":
    args = sys.argv[1:]
    main("--guide" in args, next((a for a in args if not a.startswith("--")), None))
