#!/usr/bin/env python3
"""The attack skills fix (攻击技能修复): skills the original ships with no power made to work. A fix of the
game's own data, so every build carries it (the user, 2026-10-01: 「算 bug 修复，两版都默认打上」), with no
switch.

    skillfix.py      every edited field before and after, and the executable's site

ET0004 ids 1-15 are the plain-attack templates (剣攻撃, 攻撃, ハンドガン, マシンガン, 襲撃, 鈍器攻撃, 突き攻撃,
鞭攻撃, ショットガン, レーザーガン, 攻撃11-15), with power, hit and effect all 0. Only a skill list reaches them
as skills: the plain attack loads template 1 for its animation alone (25CA:9D82; the cached hit and power are read
only after a skill entry, 25CA:9220 from A24B), the gun attack loads none (its animation is the gun's or the
bullet's, 25CA:9D2A), and neither the skill menu (25CA:95C0) nor the learning scan (ov02:0C68) singles out an id
below 10h. A skill of power 0 is a status-only roll (25CA:AC9E), and these have no status, so the enemies that list
them among their P2 skills spend the turn on nothing: バール兵, 処刑ライダー, リュティナント, ハイウェイスター and the other
gunmen, and the bosses アドニス (#24, 突き攻撃) and バールゼフォン (#36, 鞭攻撃).

The gun templates become real gun skills, like ボンブ: type 2 (+00h >> 6), which is gun hit against gun evasion and a
gun attack (below) against gun defence, one shot per entry, no bullets spent and no decay - the power byte only has
to be nonzero; 枪击; any distance, so the hit is halved as with every gun; and a cost in HP, as a physical skill, but
about two fifths of what a sword skill of the same reach costs - a gun never closes in, and that is the route's edge
(the user's ruling). The 再平衡版 also puts them in the protagonist's 枪 pool (tools/poolfix.py).

  ハンドガン   the chosen enemy twice (count 12h)                             4 HP, learnt at 5
  ショットガン every enemy of the chosen one's group once (list 0Ah, count F1h) 10 HP, at 15
  マシンガン   4-6 shots at random among that group (count 05h)               12 HP, at 25
  レーザーガン the chosen enemy and the next two found (range 6, count 30h)   16 HP, at 35
  ボンブ       up to three of the group once: its count (31h) and the guide say three, but target
               list 02h only ever takes the chosen enemy, so the list becomes 0Ah; 5 HP, not 8 MP

The melee templates with a name (剣攻撃, 攻撃, 襲撃, 鈍器攻撃, 突き攻撃, 鞭攻撃) become one plain physical blow:
still type 1, the user's own sword hit and attack, the chosen enemy once, no cost - only the power (and, like the
guns, the hit shown) is set. 攻撃11-15 are unnamed and no unit lists them, so they stay as shipped.

処刑ライダー (P2105) lists ハンドガン, マシンガン and ボンブ but carries no gun, so its gun attack is 1; it gets
リュティナント's ８９式自動小銃 and 5.56mm通常弾.

The executable, three changes:
  cost    The engine charges no cost for a skill id below 10h (25CA:9434 `cmp si, 10h; jl`); lowered to 3, so ids 1
          and 2 stay free and every other template costs what its cost byte says (the melee ones 0).
  gun     A gun-type skill strikes with the gun alone, not gun and bullet (the user's ruling: the bullet is the plain
          gun attack's). Its entries take their attack from ov16:3ECA: DS:864E when that is nonzero, else the gun
          attack panel +138h (the equipment's gun-attack word, gun and bullet together, with カジャ). 864E is the
          plain gun attack's queue of burst powers: ov16:3DE4 clears and fills it in that attack's setup (25CA:9BBE)
          and ov16:3EE6 shifts it after each of its entries (25CA:A1FD); skills take the other branch (25CA:A224 ->
          AB80), which neither touches. The action setup (25CA:9D02, once an action, es:di the actor) now calls
          GUNPANEL, which for a skill (kind 4, or 6 from an item) writes the panel less the loaded bullet's gun
          attack (+20h of 25CA:C1DA's decoded item; at least 1) to 864E, so every entry of a gun-type skill reads
          that. Other skills never read 864E, and the next plain gun attack clears it. The status roll (ov16:3BD5)
          keeps the panel, as it does for the plain gun attack, which shares it. A gun that has run dry keeps the
          spent bullet in its panel until the next rebuild (the slot is cleared, the panel is not), and this reads
          no bullet then.
  where   GUNPANEL sits in 25CA:E43F-E475 and E478-E485, the last part of the unused routine at 25CA:E294 whose middle
          (E2E1-E410) 能力值修复 holds (tools/statfix.py: no call, jump or pointer reaches E291-E4C0); the relocated
          word at E476 is jumped over.

table() is these edits as an edit table (tools/balance.py's form) for make.py and the balance lab; mend_exe() writes
the executable's sites. Nothing here is text, so every build takes the same edits."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balance  # noqa: E402
import p2fields  # noqa: E402
import records  # noqa: E402
import tables  # noqa: E402
from tables import ITEM_HEADER, SKILL_HEADER  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98")
NAME = "攻击技能修复"
EXE_NAME = "DDS98.EXE"


def hp(n):
    """A cost byte in HP: the signed byte -n (25CA:8EF6)."""
    return (256 - n) & 0xFF


GUN = {0x00: 0x81, 0x09: 30, 0x0A: 15, 0x0C: 1}        # type 2 like ボンブ, its hit and power, 枪击
BLOW = {0x09: 30, 0x0A: 15}                            # the melee templates: the hit shown, a power to act on
# id: (Japanese name, Chinese name, {header offset: value})
SKILLS = {
    1: ("剣攻撃", "剑攻击", BLOW),
    2: ("攻撃", "攻击", BLOW),
    3: ("ハンドガン", "手枪", {**GUN, 0x02: 5, 0x03: hp(4), 0x07: 0x12}),
    4: ("マシンガン", "机枪", {**GUN, 0x02: 25, 0x03: hp(12), 0x07: 0x05}),
    5: ("襲撃", "袭击", BLOW),
    6: ("鈍器攻撃", "钝器攻击", BLOW),
    7: ("突き攻撃", "突刺攻击", BLOW),
    8: ("鞭攻撃", "鞭攻击", BLOW),
    9: ("ショットガン", "霰弹枪", {**GUN, 0x02: 15, 0x03: hp(10), 0x07: 0xF1, 0x08: 0x15}),
    10: ("レーザーガン", "激光枪", {**GUN, 0x02: 35, 0x03: hp(16), 0x05: 6, 0x07: 0x30, 0x08: 0x15}),
    247: ("ボンブ", "炸弹", {0x03: hp(5), 0x06: 0x0A}),
}
DEMON = ("P2105", "処刑ライダー", "处刑骑手", ("８９式自動小銃", "5.56mm通常弾"))
GUN_SLOT = [off for off, label in p2fields.EQUIP_AT if label == "枪"][0]
BULLET_SLOT = [off for off, label in p2fields.EQUIP_AT if label == "弹"][0]

HDR, SEG25 = 0x3800, 0x25CA0            # DDS98.EXE: file offset = HDR + SEG25 + offset in 25CA
HOOK = 0x9D02                           # the action setup: mov word ptr [bp - 0xa], di / mov bx, di
HOOK_ORIG = bytes.fromhex("897ef68bdf")
CAVE, RELOC, CAVE2_END = 0xE43F, 0xE476, 0xE495     # the relocated word at E476 splits the room in two
GUNPANEL = """
gunpanel:
    mov word ptr [bp - 0xa], di         ; the setup's own instruction, which the call took the place of
    mov al, byte ptr es:[di + 0x181]    ; the action's kind
    and al, 0xfd                        ; 4 (a skill) and 6 (a skill from an item) alike
    cmp al, 4
    jne done
    xor cx, cx                          ; the bullet's gun attack, 0 with none loaded
    mov ax, word ptr es:[di + 0x1be]    ; the bullet slot: the item in the low 11 bits
    shl ax, 5
    sar ax, 5
    or ax, ax
    jle panel
    push es
    push ax
    push cs
    call 0xc1da                         ; the item, decoded: dx:ax
    mov es, dx
    mov bx, ax
    mov cl, byte ptr es:[bx + 0x20]     ; its gun attack
    xor ch, ch
    pop es
panel:
    mov ax, word ptr es:[di + 0x138]    ; the gun attack panel: gun and bullet, with カジャ
    jmp rest
    db RELOC_LO, RELOC_HI               ; the relocated word, never run
rest:
    sub ax, cx
    cmp ax, 1
    jge store
    mov ax, 1
store:
    mov word ptr [0x864e], ax           ; what ov16:3ECA hands each entry of the action
done:
    ret
"""


class SkillError(ValueError):
    pass


def _exe_sites():
    """[(file offset, as shipped, as changed)]: the cost check, the setup's call of GUNPANEL, and GUNPANEL itself
    in its two runs of room (the relocated word between them left as it is)."""
    from asm86 import assemble
    from mz import MZ
    prog = open(os.path.join(SRC, EXE_NAME), "rb").read()
    image = bytes(MZ(os.path.join(SRC, EXE_NAME)).image)
    reloc = image[0x25CA0 + RELOC:0x25CA0 + RELOC + 2]
    code, labels = assemble(GUNPANEL, org=CAVE, consts={"RELOC_LO": reloc[0], "RELOC_HI": reloc[1]})
    if labels["rest"] != RELOC + 2 or CAVE + len(code) > CAVE2_END:
        raise SkillError(f"GUNPANEL does not fit its room ({len(code)} bytes, rest at {labels['rest']:#x})")
    part1, part2 = code[:RELOC - CAVE], code[RELOC + 2 - CAVE:]
    call = bytes([0xE8]) + ((labels["gunpanel"] - (HOOK + 3)) & 0xFFFF).to_bytes(2, "little")
    sites = [(HDR + SEG25 + 0x943C, bytes.fromhex("83fe107c43"), bytes.fromhex("83fe037c43")),
             (HDR + SEG25 + HOOK, HOOK_ORIG, call + HOOK_ORIG[3:]),
             (HDR + SEG25 + CAVE, prog[HDR + SEG25 + CAVE:HDR + SEG25 + RELOC], part1),
             (HDR + SEG25 + RELOC + 2, prog[HDR + SEG25 + RELOC + 2:HDR + SEG25 + RELOC + 2 + len(part2)], part2)]
    for o, a, _b in sites:
        if prog[o:o + len(a)] != a:
            raise SkillError(f"{EXE_NAME} 0x{o:X}: not the shipped bytes")
    return sites


# DDS98.EXE (file offset = image address + 3800h)
EXE_SITES = _exe_sites()


def item_ids(src_dir=SRC):
    """{Japanese name: item id} from ET0001's string table (a kind's header, then the name)."""
    (chunk,) = tables.chunks_of(open(os.path.join(src_dir, "ET0001.BIN"), "rb").read())[:1]
    out = {}
    for i, e in enumerate(tables.string_table(chunk)):
        head = ITEM_HEADER.get(e[4]) if len(e) > 4 else None
        if head and len(e) > head:
            out.setdefault(bytes(e[head:]).split(b"\0")[0].decode("cp932", "replace"), i)
    return out


def table(src_dir=SRC):
    """The edits as an edit table: [original, edited] per changed byte of each skill's header, and the gun and
    bullet words of 処刑ライダー; a name that does not match its record stops it."""
    plain = records.plain_of(open(os.path.join(src_dir, "ET0004.BIN"), "rb").read())
    edits = {}
    for sid, (jp, zh, fields) in SKILLS.items():
        target = f"ET0004#{sid}"
        base = records.base_of(plain, target)
        name = bytes(plain[base + SKILL_HEADER:]).split(b"\0")[0].decode("cp932", "replace")
        if name != jp:
            raise SkillError(f"{target} 是「{name}」，不是「{jp}」")
        u8 = {f"{off:02X}": [plain[base + off], v] for off, v in sorted(fields.items()) if plain[base + off] != v}
        edits[target] = {"name": zh, "u8": u8}
    stem, jp, zh, (gun, bullet) = DEMON
    demon = records.plain_of(open(os.path.join(src_dir, stem + ".BIN"), "rb").read())
    if records.names(demon, stem)[0] != jp:
        raise SkillError(f"{stem} 是「{records.names(demon, stem)[0]}」，不是「{jp}」")
    ids = item_ids(src_dir)
    u16 = {}
    for off, item in ((GUN_SLOT, gun), (BULLET_SLOT, bullet)):
        if item not in ids:
            raise SkillError(f"ET0001 里没有「{item}」")
        u16[f"{off:02X}"] = [records.read(demon, stem, off, 2), ids[item]]
    edits[stem] = {"name": zh, "u16": u16}
    out = balance.empty(NAME)
    out["edits"] = edits
    return out


def mend_exe(blob, revert=False):
    """DDS98.EXE with the sites in (or out). A site holding neither form stops everything."""
    out = bytearray(blob)
    for off, orig, fixed in EXE_SITES:
        now = bytes(out[off:off + len(orig)])
        if now not in (orig, fixed):
            raise SkillError(f"{EXE_NAME} 第 {off:#x} 字节起既不是原版也不是修复后的内容")
        out[off:off + len(orig)] = orig if revert else fixed
    return bytes(out)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = table()
    for target, entry in data["edits"].items():
        print(f"{target} 「{entry['name']}」")
        for off, w, a, b in balance.edits(entry, target):
            print(f"    {off:02X}  {a:5d} -> {b:5d}")
    prog = open(os.path.join(SRC, EXE_NAME), "rb").read()
    for o, a, b in EXE_SITES:
        now = prog[o:o + len(a)]
        state = "原版" if now == a else ("改后" if now == b else "都不是")
        print(f"{EXE_NAME} 0x{o:X}: {a.hex()} -> {b.hex()}（现在 {now.hex()}，{state}）")


if __name__ == "__main__":
    main()
