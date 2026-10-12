#!/usr/bin/env python3
"""Where the numbers live in a decrypted demon record (P2*.BIN, 121-124 bytes).

Every offset here was settled by matching the record against the demon sheets in the unofficial guide
(run/guide_demons.json, 400 demons): an offset is taken as a field only when its value decides that
field's value across the whole set - except the speed and the action row, which the guide does not
print and the program's code settled (SPEED_AT, AI_ROW_AT). Kept in one place because several tools want the same labels, and
a label written out twice is a label that goes wrong in one of the copies.

種族, 種族系, 神族 and 属性 are not in the record. Demon ids are handed out in blocks by race, and the
384 demons that pair with the guide fall into only 56 runs of one race, so the game reads them off the
id. They cannot be edited per demon.
"""
import struct

SKILLS_AT, SKILL_SLOTS = 0x10, 8      # ET0004 indices: 6 the demon has, then 2 enemy-only
HELD_SKILLS = 6
AFFINITY_AT = 0x20                    # 装備相性: 0..33, shown as 1-9 then A-Y
EQUIP_AT = [(0x22, "头"), (0x24, "体"), (0x26, "腕"), (0x28, "脚"),
            (0x2A, "饰"), (0x2C, "剑"), (0x2E, "枪"), (0x30, "弹")]
DROP_AT = 0x32                        # the item the demon leaves behind
ID_AT = 0x34                          # the record's own number, same as its file name's suffix
NAME_AT, NAME_FIELD = 0x36, 17
# Two bytes the guide does not print, found in the program instead: the speed of an enemy built from this record
# (how often its turns come round; a party member's speed is worked out from 敏捷性 and its armour, 358E:1992), and
# the enemy's action row - which row of ET0005 its turns roll a plain attack or a skill slot from (ov32:051A; the
# choices: run/dump_ai_rows.py, p2enums.json 行動パターン).
SPEED_AT = 0x66
AI_ROW_AT = 0x6A

# (offset, width, label); width 4 and 2 are little-endian
FIELDS = [(0x00, 4, "ＥＸＰ"), (0x04, 4, "魔货"), (0x08, 4, "ＭＡＧ"),
          (0x0C, 2, "ＨＰ"), (0x0E, 2, "ＭＰ"), (0x47, 1, "等级"),
          (0x4C, 1, "直感"), (0x4D, 1, "精神力"), (0x4E, 1, "魔力"), (0x4F, 1, "知力"),
          (0x50, 1, "加护"), (0x51, 1, "力量"), (0x52, 1, "体力"), (0x53, 1, "敏捷性"),
          (0x54, 1, "器用"), (0x55, 1, "魅力"), (0x56, 1, "命运"),
          (0x57, 1, "ＣＰ"), (0x58, 1, "月龄对应"), (0x67, 1, "取得率"), (0x73, 1, "会话类型"),
          (SPEED_AT, 1, "速度"), (AI_ROW_AT, 1, "行动模式")]

LEARN_AT, LEARN_SLOTS = 0x63, 3       # 習得魔法・特技: which three skill families it can teach

RESIST_AT = 0x59
RESIST = ["直接", "枪击", "火炎", "冰结", "冲击", "电击", "破魔", "魔力", "咒杀", "神经"]

# Below 0xFA the byte is the percentage halved. 0xFA-0xFF are sentinels; only the two a demon sheet
# has been seen to spell out are named, the rest are shown raw rather than guessed at.
RESIST_SPECIAL = {0x00: "Immune", 0xFC: "Absorb", 0xFF: "Reflect"}

# Bytes with no field found for them yet. Listed so a tool can show them rather than pretend the
# record is fully understood.
UNKNOWN = [0x48, 0x49, 0x4A, 0x4B, 0x68, 0x6B, 0x6D, 0x6E, 0x75, 0x79]


def read(plain, off, width):
    if width == 1:
        return plain[off]
    fmt = "<H" if width == 2 else "<I"
    return struct.unpack_from(fmt, plain, off)[0]


def write(plain, off, width, value):
    if width == 1:
        plain[off] = value
    else:
        struct.pack_into("<H" if width == 2 else "<I", plain, off, value)


def skills(plain):
    return [read(plain, SKILLS_AT + 2 * i, 2) for i in range(SKILL_SLOTS)]


def resist_text(v):
    if v in RESIST_SPECIAL:
        return RESIST_SPECIAL[v]
    return f"Special {v:02X}" if v >= 0xFA else f"{v * 2}%"
