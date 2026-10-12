#!/usr/bin/env python3
"""What the 再平衡版 changes in the game (再平衡): one toggle, since its parts were checked together and do not
stand apart.

    rebalance.py      the boss tables, the learning pools and the program's sites, as shipped and as changed

The user (2026-10-01): 「把这个做成独立于现有汉化版的【再平衡版】」, 「原版素材+win素材各自做一份；现有汉化版要包含
其他bug修复，但是不包含新公式和boss调整等等」, then 「原始汉化版本身应该只改但他林抗性，其他平衡要素都不加」. The plain
Chinese builds keep the game's own numbers with its bugs mended and 但他林 II's resists (balance.json, the 难度调整
pair, an extra of the enhanced build); the 再平衡版 is that game with the combat redesign of the balance lab on top:

  boss tables  balance_redesign.json (the bosses #20 #25 #36 #38 #41 #42 #44 #60/#61 #70 #71 #72 #85 #92 #97/#102
               #101 and the late #104 #105 #106/#108 #109 #110 #121 #122 #123 #124/#126 #125 #128), checked in the
               lab under the formulas below with the four routes at P+5 (ヴェパル #60/#61 and the ラマシュトゥ fights
               #106-#108 as the chains they are); in the same table ニュートン
               strengthened (P200D's skills, and the three pieces he joins with: ET0001 #733 ニュートンブレイド, #744
               ニュートロン, #438 １０ミリ複合装甲)
  pools        the protagonist's learning pools (tools/poolfix.py), a whole ET0030
  program      DDS98.EXE sites: the new formulas and growth (the lab's vrules.VNew with tuned38, rolled as its
               sim3 rolls them), under which the bosses were checked

The program's parts, by where they sit (each comment block below has the details):
  W1  the derived values, 358E:296E                     W2  max HP, 358E:4314
  W3  speed: the armour's weight borne by 力量, 358E:1992 W4  the physical hit roll, ov16:0B40 / 3732
  W5  physical damage, ov16:0D04 / 390E; a plain attack's later swings, ov16:07BC
  W6  crits and instant kills, ov16:0964 / 3556        W7  the magic hit roll, ov16:2E22
  W8  magic damage, ov16:3070                           W9  the moon multiplier, 25CA:8E68
  W10 heals, 358E:0252                                  W11 growth, ov02:0272 / 0FBC with 1603 (01D8's room)
  W13 the gun attack values, ov16:390E, and 攻击技能修复's GUNPANEL
  W14 カジャ on the COMP values, 25CA:AF8F               W15 COMP programs' hit and attack, ov16:2E22 / 3070 / 323E
  W16 negotiation: the COMP level in the talk checks, 1603:8844

It builds on 能力值修复 and 攻击技能修复 (the lab's rules include both): a site whose shipped form is one of
theirs names it as its need, and the .bat says to enable it first.

table() and files() are the tables and whole files for make.py and tools/mkpatchbat.py; exe() the program's sites,
mend_exe() writes them; apply_to() puts the tables and files into a build's set of files."""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balance  # noqa: E402
import poolfix  # noqa: E402
import records  # noqa: E402
import skillfix  # noqa: E402
import statfix  # noqa: E402
import tables  # noqa: E402
from asm86 import Asm  # noqa: E402
from mz import MZ, overlays  # noqa: E402

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(WORK, "files", "DDS98")
REDESIGN_PATH = os.path.join(WORK, "balance_redesign.json")
NAME = "再平衡"
EXE_NAME = "DDS98.EXE"
EXE_LABEL = "新公式、成长、召唤与会话"
HDR = 0x3800                            # DDS98.EXE: file offset = HDR + image address
# far calls from code that has no relocated word for the segment: DGROUP (48FCh) less these
DS_TO = {0x0000: 0x48FC, 0x1603: 0x32F9, 0x25CA: 0x2332, 0x358E: 0x136E}


class RebalanceError(ValueError):
    pass


def _load():
    """The program as the sites are built on it: the shipped DDS98.EXE, the same with 能力值修复 only, with 攻击技能修复
    only, with both (what every 再平衡 site starts from), the main image's relocated words, the overlays."""
    path = os.path.join(SRC, EXE_NAME)
    shipped = open(path, "rb").read()
    stat = statfix.apply_to(shipped)
    skill = skillfix.mend_exe(shipped)
    return {"shipped": shipped, "stat": stat, "skill": skill, "fixed": skillfix.mend_exe(stat),
            "relocs": MZ(path).reloc_set, "ovs": overlays(path)}


PROG = _load()


def file_off(place, off):
    """DDS98.EXE's file offset of `off` in `place`: ("main", segment) or ("ov", overlay number)."""
    kind, n = place
    if kind == "main":
        return HDR + n * 16 + off
    ov = PROG["ovs"][n]
    return ov.file_off + ov.hdr + off


def holes_in(place, start, end):
    """The offsets of the relocated words in place's [start, end)."""
    kind, n = place
    if kind == "main":
        base = n * 16
        return sorted(p - base for p in PROG["relocs"] if base + start <= p < base + end)
    return sorted(p for p in PROG["ovs"][n].relocs if start <= p < end)


def pack(source, start, end, holes, consts=None):
    """Assemble `source` (org `start`, x87 in the 8087 emulator's form) to fit [start, end) around `holes` (offsets of
    relocated words, two bytes each, which keep their own bytes - the loader adds the load segment to them): before
    the last statement that still leaves room ahead of a hole, a near jmp over it. -> (code, labels); the holes'
    bytes in `code` are filler."""
    lines = source.strip("\n").split("\n")
    for k in range(len(holes) + 1):
        a = Asm("\n".join(lines), start, consts, fpu="emu")
        code = a.build()
        bad = None
        for n, (addr, blob, st) in enumerate(a.listing):
            if st.text.strip().startswith("resb"):
                continue                        # a hop's filler: the hole is meant to sit in it
            if blob and any(addr < h + 2 and addr + len(blob) > h for h in holes):
                bad = n
                break
        if bad is None:
            if start + len(code) > end:
                raise RebalanceError(f"{start:04X}-{end:04X}: 代码 {len(code)} 字节放不下")
            return code, a.labels
        addr, blob, st = a.listing[bad]
        h = next(h for h in holes if addr < h + 2 and addr + len(blob) > h)
        j = bad
        while a.listing[j][0] > h - 3:
            j -= 1
            if j < 0:
                raise RebalanceError(f"{h:04X}: 重定位字前面没有放跳转的地方")
        at, _blob, st_j = a.listing[j]
        line = st_j.line - 1
        while line > 0 and lines[line - 1].strip().endswith(":"):
            line -= 1
        lines[line:line] = [f"    jmp near __hop{k}", f"    resb {h + 2 - (at + 3)}", f"__hop{k}:"]
    raise RebalanceError(f"{start:04X}-{end:04X}: 跳过重定位字 {h:04X} 的跳转没有收敛（{addr:04X} {st.text.strip()}）")


def _defined(source):
    return set(re.findall(r"^\s*([A-Za-z_.$?@][\w.$?@]*):", source, re.M))


def link(blocks, consts=None):
    """Blocks of one segment [(name, place, start, end, source)], each packed into its own room, their labels shared
    (a block's own labels shadow nothing: each name is defined once). -> {name: (bytes of [start, end), labels)}:
    the code, the relocated words as they are, the rest int3."""
    defined = {name: _defined(src) for name, _p, _s, _e, src in blocks}
    labels = {lab: start for name, _p, start, _e, _src in blocks for lab in defined[name]}
    for _ in range(20):
        out, new = {}, {}
        for name, place, start, end, src in blocks:
            shared = {k: v for k, v in labels.items() if k not in defined[name]}
            code, labs = pack(src, start, end, holes_in(place, start, end), {**(consts or {}), **shared})
            room = bytearray(b"\xcc" * (end - start))
            room[:len(code)] = code
            for h in holes_in(place, start, end):
                o = file_off(place, h)
                room[h - start:h - start + 2] = PROG["fixed"][o:o + 2]
            out[name] = (bytes(room), labs)
            new.update({k: v for k, v in labs.items() if not k.startswith("__hop")})
        if new == labels:
            return out
        labels = new
    raise RebalanceError("各段代码的标签没有收敛")


def dbl(x):
    """A double as db bytes."""
    return "db " + ", ".join(str(b) for b in struct.pack("<d", x))


def flt(x):
    """A float (single precision: the battle's coefficients, within 1e-7 of the lab's doubles) as db bytes."""
    return "db " + ", ".join(str(b) for b in struct.pack("<f", x))


# ---- W1: the derived values (358E:296E) ---------------------------------------------------------------------------
# 296E sums the eight equipment slots and their gems into [bp-36h] (25CA:E4C2, 24 signed words: some armour and guns
# take evasion or hit away), then its tail (2B46-2CEA) hands each value to a helper (263A-296D, called from nowhere
# else) that applies the formula and clamps it to 1..999 (358E:2618). The tail now jumps to DERIVE in the helpers'
# room, which works the new formulas from a table. Each source is a word of 296E's frame, named by its slot n (the
# word at [bp-2n]): the skill levels 296E read from the unit and keeps - 枪 (+102h) at [bp-2], 魔法 (+10Eh) at [bp-4],
# COMP (+11Ah) at [bp-6]; the gear sums in place (words 2 3 4 5 8 9 16 of [bp-36h]: hit, attack, evasion, defence, gun
# hit, gun attack, and the magic evasion of 能力值修复); and what DERIVE puts below the frame first - 剑's level (+F6h,
# which 296E keeps in di), the effective attributes (+E0h: 直感 精神力 魔力 知力 加护 力量 体力 敏捷性 器用 魅力 命运),
# the sword's magic hit and attack (25CA:E8D4 / E92C), magic defence (25CA:E80E(unit, 3)), the level (+6Bh), the
# leadership L (the protagonist's 魅力 for one of the player's demons, roster 1..31 at DS:9973, when the protagonist has
# the COMP awakening - one of its slots +42h..+44h holds 3 -, the redesign's 「主角有 COMP 觉醒时」; else 0),
# 器用 again for a human with a gun in its slot, and the gun-level bonus (2 x (gun level + 5) from 1). Only humans
# carry skill levels (ov02:1324 raises those of the awakening slots by skill EXP; scripts set them through 1603:A354):
# a demon's four words are 0 (every demon record found in 209 test states, in the roster and elsewhere). Per value
# the table holds its place (index of the word from +F6h; 40h: times the leadership boost) and its terms, each the
# source's slot (40h: the last term) and a coefficient x40. One set of gear weights serves every unit - humans and
# demons, the party and the enemies (the user, 2026-10-02: 「武器的攻击力只算 15%——不过这也太低了，应该至少算30%；最好
# 对人类和恶魔、敌我都一样」): the weapon's attack x0.3, its hit x0.8, evasion x0.5, defence x0.75, gun attack x0.5. Each
# skill level adds to its own attack (「要定下限，每级至少 0.25」): 剑 0.25 to the sword attack, 枪 0.5 to the gun
# attack, 魔法 0.5 to the magic attack, COMP 0.75 to the programs' attack.
# Value = sum x (2000 + L) / 2000 when boosted, / 40, rounded half up once and held to 1..999 (the sum is signed:
# below 1 counts as 1). The COMP programs' hit and attack go into the COMP block's hit and attack words (+11Eh,
# +120h), which the game sets to 1 and no code reads. The levels at +F6h +102h +10Eh +11Ah are left as 296E read
# them. The four blocks' second words, which nothing reads (the battle copy at +126h.. neither: tools/run callers),
# now carry what the battle code needs: +F8h L, +104h the gun terms x4 (20 x 器用 of a human with a gun + 2 Lv + 2 x the
# gun level), +110h the gear's gun attack (word 9, gun and bullet) as it is; +11Ch stays 1.
W1_TAIL = 0x2B46                        # les bx, ptr [bp - 0x3a] - the tail's first instruction
W1_START, W1_END = 0x263A, 0x296E       # the helpers' room
ATTRS = ("直感", "精神力", "魔力", "知力", "加护", "力量", "体力", "敏捷性", "器用", "魅力", "命运")
ATTR_AT = -0x58                         # the effective attributes, [bp-58h]..[bp-44h]
# the sources' places in the frame (displacement from bp)
SOURCES = {**{a: ATTR_AT + 2 * k for k, a in enumerate(ATTRS)},
           "gear_hit": -0x32, "gear_atk": -0x30, "gear_eva": -0x2E, "gear_def": -0x2C, "gear_ghit": -0x26,
           "gear_gatk": -0x24, "mgear_eva": -0x16, "gun_lv": -0x02,
           "mgear_hit": -0x5A, "mgear_atk": -0x5C, "mgear_def": -0x5E, "lv": -0x60, "lead": -0x62, "dex_gun": -0x64,
           "gun_bonus": -0x66, "sw_lv": -0x6E, "mg_lv": -0x04, "cp_lv": -0x06}
LAST = 0x40
BOOST = 0x40
# (name, place, boosted, [(source, coefficient x40)])
FORMULAS = [
    ("s_hit", 0xFA, False, [("敏捷性", 40), ("器用", 20), ("直感", 10), ("知力", 5), ("gear_hit", 32), ("lead", 10)]),
    ("s_atk", 0xFC, True, [("力量", 80), ("gear_atk", 12), ("lv", 20), ("sw_lv", 10)]),
    ("s_eva", 0xFE, False, [("敏捷性", 40), ("直感", 40), ("知力", 20), ("gear_eva", 20), ("lead", 10)]),
    ("s_def", 0x100, False, [("体力", 40), ("加护", 16), ("gear_def", 30)]),
    ("g_hit", 0x106, False, [("器用", 40), ("直感", 8), ("知力", 4), ("gear_ghit", 40), ("gun_bonus", 40), ("lead", 10)]),
    ("g_full", 0x108, True, [("gear_gatk", 20), ("dex_gun", 200), ("lv", 20), ("gun_lv", 20)]),
    ("g_eva", 0x10A, False, [("直感", 36), ("知力", 18), ("加护", 16), ("gear_eva", 40), ("lead", 10)]),
    ("m_hit", 0x112, False, [("知力", 30), ("魔力", 10), ("mgear_hit", 40), ("lead", 10)]),
    ("m_atk", 0x114, True, [("魔力", 70), ("mgear_atk", 40), ("lv", 20), ("mg_lv", 20)]),
    ("m_eva", 0x116, False, [("知力", 10), ("加护", 20), ("精神力", 20), ("mgear_eva", 40), ("lead", 10)]),
    ("m_def", 0x118, False, [("精神力", 32), ("加护", 16), ("mgear_def", 40)]),
    ("c_hit", 0x11E, False, [("知力", 30), ("魅力", 10), ("mgear_hit", 40), ("lead", 10)]),
    ("c_atk", 0x120, True, [("知力", 40), ("魅力", 50), ("mgear_atk", 40), ("lv", 40), ("cp_lv", 30)]),
]


def w1_table():
    out = bytearray()
    for _name, place, boosted, terms in FORMULAS:
        out.append(((place - 0xF6) // 2) | (BOOST if boosted else 0))
        for k, (src, coef) in enumerate(terms):
            out += bytes([-SOURCES[src] // 2 | (LAST if k == len(terms) - 1 else 0), coef])
    out.append(0xFF)
    return bytes(out)


def w1_source():
    table = ", ".join(str(b) for b in w1_table())
    return f"""
derive:                                 ; jumped to from 296E's tail, in its frame: [bp-3Ah] the unit, di 剑's level
    lea sp, [bp - 0x74]
    mov word ptr [bp - 0x6e], di
    mov ax, cs
    sub ax, 0xfc4
    mov word ptr [bp - 0x70], ax        ; [bp-72h]: a far pointer into 25CA
    les bx, ptr [bp - 0x3a]
    xor si, si
d_attr:                                 ; the effective attributes to [bp-58h]..[bp-44h]
    mov ax, word ptr es:[bx + si + 0xe0]
    mov word ptr [bp + si - 0x58], ax
    inc si
    inc si
    cmp si, 22
    jb d_attr
    mov ax, word ptr es:[bx + 0x1b6]    ; the sword's magic hit and attack
    shl ax, 5
    sar ax, 5
    push ax
    push ax
    mov word ptr [bp - 0x72], 0xe8d4
    lcall [bp - 0x72]
    mov word ptr [bp - 0x5a], ax
    mov word ptr [bp - 0x72], 0xe92c
    lcall [bp - 0x72]
    mov word ptr [bp - 0x5c], ax
    push word ptr [bp - 0x38]           ; magic defence
    push word ptr [bp - 0x3a]
    push 3
    mov word ptr [bp - 0x72], 0xe80e
    lcall [bp - 0x72]
    mov word ptr [bp - 0x5e], ax
    les bx, ptr [bp - 0x3a]
    mov al, byte ptr es:[bx + 0x6b]     ; the level
    xor ah, ah
    mov word ptr [bp - 0x60], ax
    xor cx, cx                          ; the gun-level bonus
    mov ax, word ptr [bp - 2]
    or ax, ax
    jle d_gb
    add ax, 5
    add ax, ax
    xchg ax, cx
d_gb:
    mov word ptr [bp - 0x66], cx
    xor ax, ax                          ; the leadership L
    xor dx, dx                          ; dl: a demon
    cmp word ptr es:[bx], 0x20
    jl d_lead
    inc dx
    mov si, 0x9977                      ; the roster's members 1..31
d_scan:
    cmp word ptr [si], bx
    jne d_next
    mov cx, es
    cmp word ptr [si + 2], cx
    je d_found
d_next:
    add si, 4
    cmp si, 0x99f3
    jb d_scan
    jmp short d_lead
d_found:                                ; member 0, the protagonist: its 魅力 when one of its awakening slots (+42h..+44h,
    push es                             ; a negative byte empty) holds COMP (low bits 3)
    push bx
    les bx, ptr [0x9973]
    xor di, di
d_comp:
    mov cl, byte ptr es:[bx + di + 0x42]
    or cl, cl
    js d_cn
    and cl, 3
    cmp cl, 3
    jne d_cn
    mov ax, word ptr es:[bx + 0xf2]
d_cn:
    inc di
    cmp di, 3
    jb d_comp
    pop bx
    pop es
d_lead:
    mov word ptr [bp - 0x62], ax
    xor ax, ax                          ; 器用 again for a human with a gun in its slot
    or dx, dx
    jne d_gun
    mov cx, word ptr es:[bx + 0x1ba]
    and cx, 0x7ff
    je d_gun
    cmp cx, 0x7ff
    je d_gun
    mov ax, word ptr es:[bx + 0xf0]
d_gun:
    mov word ptr [bp - 0x64], ax
    mov si, w1_table
d_formula:
    mov al, byte ptr cs:[si]
    inc si
    cmp al, 0xff
    jne d_go
    jmp near w1_finish
d_go:
    mov byte ptr [bp - 0x6c], al
    xor ax, ax
    mov word ptr [bp - 0x6a], ax        ; the sum, [bp-6Ah] low, [bp-68h] high
    mov word ptr [bp - 0x68], ax
d_term:
    mov ax, word ptr cs:[si]            ; al: the source's slot, ah: the coefficient
    inc si
    inc si
    mov bl, al
    mov cl, ah
    xor ch, ch
    and ax, 0x3f
    add ax, ax
    neg ax
    mov di, ax
    mov ax, cx
    imul word ptr [bp + di]
    add word ptr [bp - 0x6a], ax
    adc word ptr [bp - 0x68], dx
    test bl, 0x40
    je d_term
    mov ax, word ptr [bp - 0x6a]
    mov dx, word ptr [bp - 0x68]
    mov cx, 1
    or dx, dx
    js d_store
    mov cx, 999
    jne d_store
    cmp ax, 39980
    jae d_store
    mov cx, 2000
    test byte ptr [bp - 0x6c], 0x40
    je d_mul
    add cx, word ptr [bp - 0x62]
d_mul:
    mul cx
    add ax, 40000
    adc dx, 0
    mov cx, 2000
    div cx
    xor dx, dx
    mov cx, 40
    div cx
    xchg ax, cx
    or cx, cx
    jne d_hi
    inc cx
d_hi:
    cmp cx, 999
    jbe d_store
    mov cx, 999
d_store:
    mov bl, byte ptr [bp - 0x6c]
    and bx, 0x1f
    add bx, bx
    les di, ptr [bp - 0x3a]
    mov word ptr es:[di + bx + 0xf6], cx
    jmp d_formula
w1_table:
    db {table}
"""


W1_FINISH = """
w1_finish:                              ; DERIVE's end: the words beside the values, then 296E's epilogue
    les bx, ptr [bp - 0x3a]
    mov ax, word ptr es:[bx + 0x100]    ; gun defence = sword defence, as the game had it
    mov word ptr es:[bx + 0x10c], ax
    mov ax, word ptr [bp - 0x62]        ; +F8h: the leadership L
    mov word ptr es:[bx + 0xf8], ax
    imul ax, word ptr [bp - 0x64], 20   ; +104h: the gun terms x4
    add ax, word ptr [bp - 0x60]
    add ax, word ptr [bp - 0x60]
    add ax, word ptr [bp - 2]
    add ax, word ptr [bp - 2]
    mov word ptr es:[bx + 0x104], ax
    mov ax, word ptr [bp - 0x24]        ; +110h: the gear's gun attack as it is
    mov word ptr es:[bx + 0x110], ax
    mov ax, 1                           ; the COMP block's other words, as the game had them
    mov word ptr es:[bx + 0x11c], ax
    mov word ptr es:[bx + 0x122], ax
    mov word ptr es:[bx + 0x124], ax
    lea sp, [bp - 0x42]
    pop si
    pop di
    leave
    retf 4
"""

# ---- W2 max HP, W10 heals, W11's and W12's 358E parts: routines that move into the tail W1 left dead --------------
# W12 a summon costs the COMP holder a turn (the lab's sim3.SUMMON_TURN): the COMP's CALL (ov04:0044, state 4: field
# and battle alike) swaps a demon in with ov04:0101's far call of 358E:4B30, whose offset now names SUMMON_SWAP: the
# same swap, then 255 added to the countdown (+17Fh) of the COMP holder (the protagonist, else 英美 (0Bh), in the
# party and able to act; 25CA:5986 also names 山瀬 (0Ah), who never joins - the user), unless its own action is under
# way (+17Eh not 0). A member waiting for a command (countdown 0) so leaves the list until a turn has passed; one
# counting down waits a turn longer. The party's countdowns are set to 0 at the start of every battle (ov16:1590), so
# a summon outside battle costs nothing.
# Max HP (358E:4314, party units; an enemy keeps its data HP): 5 + 加护 + 命运 + Lv (0.99 + 0.297 体力 + 0.198 Lv) in
# place of Lv x 体力 x 0.5 + 加护 + 命运 + 5; the game's x2 states and its 9999 cap after it as before. Heals (358E:0252,
# skills and items, the user's 魔力): power + 0.75 魔力 + sqrt(魔力), the game's U(80..120)% after it. W11's 体力
# point: FBC_VIT (see the growth part below). The luck point of ov02:01D8 is LU358 now, as the game gives it, so that
# its room in ov02 holds the growth part's stubs.
CAVE358 = (0x2B49, 0x2CEE)              # the rest of 296E's dead tail (its four relocated words jumped over)
HP_AT, HEAL_AT = 0x4320, 0x02DA
CAVE358_SRC = W1_FINISH + f"""
hp_new:                                 ; 358E:4320, es:si the unit: [bp-8] = 5 + 加护 + 命运 + Lv (0.99 + 0.297 体力 + 0.198 Lv)
    mov al, byte ptr es:[si + 0x6b]
    sub ah, ah
    mov word ptr [bp - 0x12], ax
    fild word ptr [bp - 0x12]
    fld st(0)
    fmul qword ptr cs:[c_198]
    fild word ptr es:[si + 0xec]
    fmul qword ptr cs:[c_297]
    faddp st(1)
    fadd qword ptr cs:[c_099]
    fmulp st(1)
    mov ax, word ptr es:[si + 0xe8]
    add ax, word ptr es:[si + 0xf4]
    add ax, 5
    mov word ptr [bp - 0x12], ax
    fiadd word ptr [bp - 0x12]
    fstp qword ptr [bp - 8]
    fwait
    jmp near 0x435d
heal_new:                               ; 358E:02DA: [bp-8] = sqrt(魔力) (as the game has it) + the power + 0.75 魔力
    fild word ptr [bp + 0xc]
    fadd qword ptr [bp - 8]
    les bx, ptr [bp + 8]
    fild word ptr es:[bx + 0xe4]
    fmul qword ptr cs:[c_075]
    faddp st(1)
    fstp qword ptr [bp - 8]
    fwait
    jmp near 0x2e8
lu358:                                  ; far (unit) -> ax 1 when 命运 rose: ov02:01D8's luck point, as the game gives it
    push bp
    mov bp, sp
    push si
    les si, ptr [bp + 6]
    mov al, byte ptr es:[si + 0x6b]
    sub ah, ah
    cmp word ptr es:[si], 0x20
    jge lu_d
    test al, 1
    je lu_l
    jmp short lu_0
lu_d:
    mov cl, 3
    div cl
    or ah, ah
    jne lu_0
lu_l:
    mov ax, word ptr es:[si + 0x9c]
    inc ax
    push ax
    push cs
    call 0x2320
    les si, ptr [bp + 6]
    mov word ptr es:[si + 0x9c], ax
    mov ax, 1
    jmp short lu_out
lu_0:
    xor ax, ax
lu_out:
    pop si
    pop bp
    retf 4
summon_swap:                            ; far, as 358E:4B30 (slot, demon): the COMP's summon, then the holder's turn
    push bp
    mov bp, sp
    push word ptr [bp + 8]
    push word ptr [bp + 6]
    push cs
    call 0x4b30
    push ax
    push si
    xor si, si
ht_next:                                ; the COMP holder: the protagonist, else 英美 (25CA:5986 also names 山瀬, who never joins)
    mov al, byte ptr cs:[si + ht_ids]
    cbw
    push ax
    push cs
    call 0x5236
    mov cx, dx
    or cx, ax
    je ht_skip
    push dx
    push ax
    add ax, 0x156
    push dx
    push ax
    push cs
    call 0x3d36
    pop bx
    pop es
    or ax, ax
    jne ht_skip
    cmp byte ptr es:[bx + 0x17e], 0     ; not in the middle of its own action
    jne ht_done
    add word ptr es:[bx + 0x17f], 255   ; one turn: a member waiting for its command gets it a turn later, a running clock runs a turn longer
    jmp short ht_done
ht_skip:
    inc si
    cmp si, 2
    jb ht_next
ht_done:
    pop si
    pop ax
    pop bp
    retf 4
ht_ids:
    db 0, 0xb
c_198:
    {dbl(0.198)}
c_297:
    {dbl(0.297)}
c_099:
    {dbl(0.99)}
c_075:
    {dbl(0.75)}
"""

# ---- the battle (overlay 16) --------------------------------------------------------------------------------------
# W6 crits and instant kills (sword 0964, gun 3556; same frame: [bp+6] the code, [bp+8] 1 for the party on a ＠ボス戦
# enemy, [bp+0Ah] the target, [bp+0Eh] the actor). The moon gate is drawn as before (U(0..255) < ((age + 13) % 14 +
# 1)^2 / 4) but now holds back only the instant kill: inside it, an enemy in a ＠ボス戦 fight rolls the game's own
# (the block at 09E7 / 35D9, kept), the party never kills a ＠ボス戦 enemy, everyone else kills with chance 0.3 x
# clip(Ka / Kt - 1, 0, 1), K = (直感 + 0.5 知力) / 2 + 命运. Then, every entry, a crit with chance clip(0.03 + 0.04
# (直感 + 0.5 知力 of the actor - 加护 of the target) + 0.0025 B0, 0, 0.35) (B0: ov16:0000, the weapon's crit less
# the target's armour). Chances are rolled as U(0..65535) < 65536 p (two draws of the game's 8-bit generator).
# W4 the hit roll (sword 0B40, gun 3732), from the point where the game has its hit and evasion with its own
# modifiers (blindness, position): hit with 1 / (1 + (0.4 E / H)^2) held to 0.05..0.97, a miss grazes half the time.
# W5 damage (sword 0D04, gun 390E): 0.5227 A^2 / (A + D), D at least 1, x2.5 on a crit (in place of + Lv + 5); a
# plain sword attack's second and later swings x0.5 (07BC counts them in [29D2], which the action's setup sets to 1
# and only skills used); the game's multipliers after it as before (x1.2 a target that cannot act, position, a graze
# x0.25, x100, the code's 2R/100, the moon, U(80..120)%).
# W13 the gun attack (390E, A of 3ECA): DS:864E - a plain attack's burst, or a gun skill's panel less its bullet,
# which 攻击技能修复's GUNPANEL now takes from the raw panel (+110h's battle copy +140h) - through the redesign's gun
# terms: (raw x 0.5, the gear's weight for every unit, + T) x (2000 + L) / 2000 (+134h T x4, +128h L: W1), for a
# skill x0.4 (マシンガン x0.35), held to 1..999, plus the panel's カジャ shift (+138h - +108h), held again; without 864E
# the panel +138h itself (W1's value).
# W7 the magic hit (2E22), from the point where it has S = (hit byte + H) (1 - f) and V (x100, with its modifiers):
# hit with 1 / (1 + (0.8 V / S')^2) held to 0.05..0.97, S' = S x R / 50 (a code below 0 rolls as R 50, 0 misses).
# W8 magic damage (3070): S = (0.5 power + attack) (1 - f) (25CA:928A on power + 2 x attack, halved), 1.9008 S^2 / (S +
# M), M at least 1; the game's multipliers after it.
# W15 a COMP program (ET0004 type 3) aims with the COMP hit (+14Eh) and strikes with the COMP attack (+150h): 2E22's
# and 323E's hit (25CA:9286 otherwise), 3070's attack.
MACHINEGUN = None                       # the ET0004 id of マシンガン, set below


def _machinegun():
    (chunk,) = tables.chunks_of(open(os.path.join(SRC, "ET0004.BIN"), "rb").read())[:1]
    ids = [i for i, e in enumerate(tables.string_table(chunk))
           if len(e) > 20 and bytes(e[20:]).split(b"\0")[0].decode("cp932", "replace") == "マシンガン"]
    if len(ids) != 1:
        raise RebalanceError(f"ET0004 里的マシンガン：{ids}")
    return ids[0]


MACHINEGUN = _machinegun()
OV16 = ("ov", 16)


def _crit_blocks(p, old, stop, kill_exit, done):
    """Sword (p = "s") or gun ("g") crit / instant kill: the prologue (up to the game's own instant-kill block `old`)
    and the crit roll (up to the epilogue `stop`); `kill_exit` sets +186h to 5, `done` stores ax into [98FC] and
    returns."""
    head = f"""
{p}_ck:                                   ; the crit / instant-kill roll, as the game calls it
    enter 0x10, 0
    push di
    push si
    call near h_ckhead
    cmp ax, 1
    jb {p}_ckn
    je {p}_cko
    cmp ax, 3
    jne {p}_ckc
    xor ax, ax
    jmp near {stop:#x}
{p}_ckn:
    jmp near {p}_kill
{p}_cko:
    jmp near {old:#x}
{p}_ckc:
    jmp near {p}_crit
"""
    tail = f"""
{p}_crit:                                 ; every entry not killed: the crit roll, no moon gate
    call near h_crit16
    call near h_roll
    mov es, word ptr [bp + 0x10]
    jae {p}_none
    mov al, byte ptr es:[si + 0x186]
    and al, 0x84
    or al, 4
    mov byte ptr es:[si + 0x186], al
    mov ax, 4
    jmp near {done:#x}
{p}_none:
    and byte ptr es:[si + 0x186], 0x80
    xor ax, ax
    jmp near {done:#x}
{p}_kill:                                 ; the redesign's instant kill, inside the moon gate
    call near h_kill16
    call near h_roll
    jae {p}_crit
    jmp near {kill_exit:#x}
"""
    return head, tail


def _hit_block(p, h, e, hit_exit, ret1, ret0):
    """The hit roll's tail: H at [bp-h], E at [bp-e] (longs); a hit goes to `hit_exit` (+186h = 3), a graze sets 2 and
    returns 1 by `ret1`, a miss returns 0 by `ret0` (the epilogue)."""
    return f"""
{p}_hit:                                  ; H at [bp-{h:#x}], E at [bp-{e:#x}] (longs, with the game's modifiers)
    push word ptr [bp - {e - 2:#x}]
    push word ptr [bp - {e:#x}]
    push word ptr [bp - {h - 2:#x}]
    push word ptr [bp - {h:#x}]
    call near h_phys
    mov es, word ptr [bp + 0xe]
    cmp ax, 1
    jne {p}_hg
    jmp near {hit_exit:#x}
{p}_hg:
    jb {p}_hm
    mov al, byte ptr es:[si + 0x186]
    and al, 0x82
    or al, 2
    mov byte ptr es:[si + 0x186], al
    mov word ptr [0x98fc], 2
    jmp near {ret1:#x}
{p}_hm:
    and byte ptr es:[si + 0x186], 0x80
    xor ax, ax
    mov word ptr [0x98fc], ax
    jmp near {ret0:#x}
"""


S_CK, S_CRIT = _crit_blocks("s", 0x9E7, 0xB3A, 0xA9E, 0xAB2)
# The gun's crit / instant-kill routine (3556) is the sword's (0964) byte for byte but for its own copies of the
# constants 0.5 and 0.01 (DS:6328 / 6330 for 6296 / 629E) and the call's relative offset: it now jumps there, and its
# room holds helpers.
G_CK = """
g_ck:                                   ; ov16:3556, as the sword's
    jmp near 0x964
"""
# The battle's start (ov16:1590, through 07B1:007E from the FIGHT button, 25CA:5C4D / 5CE9) zeroes the party's
# countdowns; before that every roster member is now worked out again by 358E:18D8 - its values, max HP, max MP and
# speed - as levelling up and changing equipment do: a save written by a build without 再平衡 (or the other way) holds
# the values of its own formulas, and the game reworks them only at the end of a battle (358E:1B6A, without max HP
# and speed).
BS_HOOK = f"""
bs_hook:                                ; ov16:1590's `push di / push si / xor si, si`, first the roster
    push di
    push si
    xor si, si
bs_r:
    push si
    mov dx, {DS_TO[0x358E]:#x}
    mov ax, 0x507e
    call near h_far
    mov cx, dx
    or cx, ax
    je bs_n
    push dx
    push ax
    mov dx, {DS_TO[0x358E]:#x}
    mov ax, 0x18d8
    call near h_far
bs_n:
    inc si
    cmp si, 32
    jb bs_r
    xor si, si
    jmp near 0x1594
"""

H_PHYS = """
h_phys:                                 ; (H, E: longs) -> ax: 1 hit, 2 graze, 0 miss
    push bp
    mov bp, sp
    fild dword ptr [bp + 8]
    fild dword ptr [bp + 4]
    mov bx, c_04
    call near h_odds
    call near h_roll
    mov ax, 1
    jb hp_out
    call near h_rand8
    cmp ax, 128
    mov ax, 2
    jb hp_out
    xor ax, ax
hp_out:
    pop bp
    ret 8
"""
H_ODDS = """
h_odds:                                 ; st(0) = H, st(1) = E, cs:[bx] = k, both popped -> ax = 65536 / (1 + (k E / H)^2) in 3277..63570
    call near h_atleast1
    fxch st(1)
    call near h_atleast1
    fdivrp st(1)
    fmul dword ptr cs:[bx]
    fld st(0)
    fmulp st(1)
    fld1
    faddp st(1)
    fdivr dword ptr cs:[c_65536]
    sub sp, 4
    mov bx, sp
    fistp dword ptr ss:[bx]
    fwait
    pop ax
    pop dx
    or dx, dx
    jne ho_hi
    cmp ax, 63570
    jbe ho_lo
ho_hi:
    mov ax, 63570
ho_lo:
    cmp ax, 3277
    jae ho_out
    mov ax, 3277
ho_out:
    ret
h_atleast1:                             ; st(0) at least 1
    fld1
    fcomp st(1)
    fnstsw ax
    sahf
    jbe ha_out
    fstp st(0)
    fld1
ha_out:
    ret
"""
H_RAND = f"""
h_roll:                                 ; CF (jb) with chance ax / 65536: U(0..65535) < ax
    push ax
    call near h_rand16
    pop cx
    cmp ax, cx
    ret
h_rand16:                               ; ax = U(0..65535): two draws, the first the high byte
    call near h_rand8
    push ax
    call near h_rand8
    pop dx
    mov ah, dl
    ret
h_rand8:                                ; ax = U(0..255): the game's generator, 1603:410E(255)
    push bx
    push cx
    push dx
    push es
    push 0xff
    mov dx, {DS_TO[0x1603]:#x}
    mov ax, 0x410e
    call near h_far
    pop es
    pop dx
    pop cx
    pop bx
    ret
h_far:                                  ; a far call of (DGROUP - dx):ax, its arguments pushed before the near call here
    pop cx
    push cs
    push cx
    mov cx, ds
    sub cx, dx
    push cx
    push ax
    retf
h_gate:                                 ; ax = -1 when the moon gate opens, else 0
    mov al, byte ptr [0x98ea]
    xor ah, ah
    add ax, 13
    mov cl, 14
    div cl
    mov al, ah
    inc al
    mul al
    shr ax, 2
    push ax
    call near h_rand8
    pop cx
    cmp ax, cx
    sbb ax, ax
    ret
"""
H_CKHEAD = """
h_ckhead:                               ; the crit roll's frame: the gate, the code, B0 -> ax: 0 the redesign's instant-kill
    call near h_gate                    ; roll, 1 the game's, 2 none (the crit roll only), 3 nothing (the code 0 or -6)
    mov word ptr [bp - 4], ax
    mov dx, word ptr [bp + 6]
    mov ax, 3
    or dx, dx
    je hh_out
    cmp dx, -6
    je hh_out
    mov di, word ptr [bp + 0xa]
    mov si, word ptr [bp + 0xe]
    push word ptr [bp + 0x10]
    push si
    push word ptr [bp + 0xc]
    push di
    push cs
    call 0
    mov word ptr [bp - 0xe], ax
    mov ax, 2
    cmp word ptr [bp - 4], 0
    je hh_out
    cmp word ptr [bp + 8], 0
    jne hh_out
    dec ax
    cmp word ptr [0x9a0a], 0
    jl hh_new
    cmp word ptr [0x2ef8], 1
    jge hh_out
hh_new:
    xor ax, ax
hh_out:
    ret
"""
H_K4 = """
h_k4:                                   ; ax = 2 直感 + 知力 + 4 命运 of es:bx (4 K)
    mov ax, word ptr es:[bx + 0xf4]
    shl ax, 2
    add ax, word ptr es:[bx + 0xe6]
    add ax, word ptr es:[bx + 0xe0]
    add ax, word ptr es:[bx + 0xe0]
    ret
"""
H_KILL = """
h_kill16:                               ; the crit roll's frame -> ax = 65536 x 0.3 x clip(Ka / Kt - 1, 0, 1)
    les bx, ptr [bp + 0xa]
    call near h_k4
    cmp ax, 1
    jge hk_t
    mov ax, 1
hk_t:
    mov cx, ax
    les bx, ptr [bp + 0xe]
    call near h_k4
    sub ax, cx
    jg hk_d
    xor ax, ax
    ret
hk_d:
    cmp ax, cx
    jbe hk_m
    mov ax, cx
hk_m:
    mov dx, 49152
    mul dx
    shl ax, 1
    rcl dx, 1
    mov bx, cx
    shl cx, 2
    add cx, bx
    div cx
    ret
"""
H_CRIT = """
h_crit16:                               ; the crit roll's frame -> ax = 65536 x clip((12 + 8 (2 直感 + 知力 - 2 加护) + B0) / 400, 0, 0.35)
    les bx, ptr [bp + 0xe]
    mov ax, word ptr es:[bx + 0xe0]
    add ax, ax
    add ax, word ptr es:[bx + 0xe6]
    les bx, ptr [bp + 0xa]
    sub ax, word ptr es:[bx + 0xe8]
    sub ax, word ptr es:[bx + 0xe8]
    shl ax, 3
    add ax, 12
    add ax, word ptr [bp - 0xe]
    jg hc_p
    xor ax, ax
    ret
hc_p:
    cmp ax, 140
    jle hc_m
    mov ax, 140
hc_m:
    mov dx, 4096
    mul dx
    mov cx, 25
    div cx
    ret
"""
S_DMG = """
s_dmg:                                  ; 0D04 from here: A at [bp-8] (the game's x2 states kept), D the sword defence
    les bx, ptr [bp + 8]
    mov ax, word ptr es:[bx + 0x130]
    call near h_pdmg
    les bx, ptr [bp + 0xc]
    cmp byte ptr es:[bx + 0x181], 1
    jne s_dd
    cmp word ptr [0x29d2], 3
    jl s_dd
    fld qword ptr [bp - 8]
    fmul dword ptr cs:[c_05]
    fstp qword ptr [bp - 8]
    fwait
s_dd:
    jmp near 0xe26
h_swing:                                ; 07BC's `mov word ptr [0x9b3e], ax` (ax = 0), then a plain attack's entry count
    mov word ptr [0x9b3e], ax
    mov es, word ptr [bp + 0xe]
    cmp byte ptr es:[si + 0x181], 1
    jne hw_out
    inc word ptr [0x29d2]
hw_out:
    ret
h_pdmg:                                 ; [bp-8] = 0.5227 A^2 / (A + D), A at [bp-8], D in ax (at least 1); x2.5 when [bp+6] = 4
    cmp ax, 1
    jge hd_d
    mov ax, 1
hd_d:
    push ax
    mov bx, sp
    fild word ptr ss:[bx]
    fadd qword ptr [bp - 8]
    pop ax
    fld qword ptr [bp - 8]
    fmul qword ptr [bp - 8]
    fdivrp st(1)
    fmul dword ptr cs:[c_kp]
    cmp word ptr [bp + 6], 4
    jne hd_s
    fmul dword ptr cs:[c_25]
hd_s:
    fstp qword ptr [bp - 8]
    fwait
    ret
"""
G_DMG = f"""
g_dmg:                                  ; 390E from here: the attack of this gun entry, then the formula on the gun defence
    call near h_gatk
    les bx, ptr [bp + 8]
    mov ax, word ptr es:[bx + 0x13c]
    call near h_pdmg
    jmp near 0x39f8
h_gatk:                                 ; 390E's frame: [bp-8] = the attack (W13)
    les bx, ptr [bp + 0xc]
    mov ax, word ptr [0x864e]
    or ax, ax
    jne ga_q
    fild word ptr es:[bx + 0x138]
    jmp near ga_st
ga_q:
    mov word ptr [bp - 0x24], ax
    fild word ptr [bp - 0x24]
    fmul dword ptr cs:[c_05]
    fild word ptr es:[bx + 0x134]
    fmul qword ptr [0x61f4]
    faddp st(1)
    fild word ptr es:[bx + 0x128]
    fadd dword ptr cs:[c_2000]
    fmulp st(1)
    fdiv dword ptr cs:[c_2000]
    cmp byte ptr es:[bx + 0x181], 2
    je ga_c
    mov ax, word ptr es:[bx + 0x182]
    and ax, 0x7fff
    cmp ax, {MACHINEGUN}
    jne ga_g
    fmul dword ptr cs:[c_mg]
    jmp short ga_c
ga_g:
    fmul dword ptr cs:[c_04]
ga_c:
    call near h_clamp
    mov ax, word ptr es:[bx + 0x138]
    sub ax, word ptr es:[bx + 0x108]
    mov word ptr [bp - 0x24], ax
    fiadd word ptr [bp - 0x24]
    call near h_clamp
ga_st:
    fstp qword ptr [bp - 8]
    fwait
    ret
h_clamp:                                ; st(0) held to 1..999
    fcom dword ptr cs:[c_999]
    fnstsw ax
    sahf
    jbe hl_lo
    fstp st(0)
    fld dword ptr cs:[c_999]
    ret
hl_lo:
    jmp near h_atleast1
"""
M_HIT = f"""
m_hit:                                  ; 2E22 from here: S at [bp-8], V at [bp-0xc] (longs, x100); the code [2F22]
    mov ax, word ptr [0x2f22]
    or ax, ax
    jge mh_r
    mov ax, 50
mh_r:
    je mh_miss
    push ax
    mov bx, sp
    fild word ptr ss:[bx]
    fild dword ptr [bp - 8]
    fmulp st(1)
    pop ax
    fmul qword ptr [0x629e]             ; 0.01, twice: / 50
    fadd st(0)
    fild dword ptr [bp - 0xc]
    fxch st(1)
    mov bx, c_08
    call near h_odds
    call near h_roll
    jae mh_miss
    jmp near 0x2ea0
mh_miss:
    jmp near 0x305c
h_mhit2e:                               ; 2ECE's `lcall 25CA:9286`
    les bx, ptr [bp + 0xc]
    call near h_mhit
    jmp near 0x2ed3
h_mhit32:                               ; 32FD's `lcall 25CA:9286`
    les bx, ptr [bp + 0xe]
    call near h_mhit
    jmp near 0x3302
h_mhit:                                 ; es:bx the actor -> ax: the COMP hit (+14Eh) for a COMP program, else 25CA:9286
    push es
    push bx
    mov ax, word ptr es:[bx + 0x182]
    add ax, ax
    sar ax, 1
    push ax
    mov dx, {DS_TO[0x25CA]:#x}
    mov ax, 0x8f0e
    call near h_far
    mov es, dx
    mov bx, ax
    mov cl, byte ptr es:[bx]
    pop bx
    pop es
    and cl, 0xc0
    cmp cl, 0xc0
    jne hmh_m
    mov ax, word ptr es:[bx + 0x14e]
    ret
hmh_m:
    mov dx, {DS_TO[0x25CA]:#x}
    mov ax, 0x9286
    jmp near h_far
"""
M_DMG = """
m_dmg:                                  ; 3070 from here: ax = (power + 2 x attack) (1 - f); [bp-8] = 1.9008 S^2 / (S + M)
    mov word ptr [bp - 0x10], ax
    fild word ptr [bp - 0x10]
    fmul qword ptr [0x6296]             ; 0.5: S
    les bx, ptr [bp + 8]
    mov ax, word ptr es:[bx + 0x148]
    cmp ax, 1
    jge md_m
    mov ax, 1
md_m:
    mov word ptr [bp - 0x10], ax
    fild word ptr [bp - 0x10]
    fadd st(1)
    fld st(1)
    fmul st(2)
    fdivrp st(1)
    fmul dword ptr cs:[c_km]
    fstp qword ptr [bp - 8]
    fstp st(0)
    fwait
    jmp near 0x3122
h_mdsum:                                ; 309C: ax = the power, es:bx the skill -> push power + 2 x the actor's attack
    mov cl, byte ptr es:[bx]
    les bx, ptr [bp + 0xc]
    mov dx, word ptr es:[bx + 0x144]
    and cl, 0xc0
    cmp cl, 0xc0
    jne hs_m
    mov dx, word ptr es:[bx + 0x150]
hs_m:
    add dx, dx
    add ax, dx
    push ax
    jmp near 0x30a5
"""
OV16_CONSTS = f"""
c_04:
    {flt(0.4)}
c_05:
    {flt(0.5)}
c_08:
    {flt(0.8)}
c_65536:
    {flt(65536.0)}
c_kp:
    {flt(0.5227)}
c_25:
    {flt(2.5)}
c_2000:
    {flt(2000.0)}
c_mg:
    {flt(0.35)}
c_999:
    {flt(999.0)}
c_km:
    {flt(1.9008)}
"""
OV16_BLOCKS = [
    ("剑会心与即死(前段)", OV16, 0x0964, 0x09E7, S_CK + H_KILL),
    ("剑会心与即死(后段)", OV16, 0x0AB8, 0x0B3A, S_CRIT + H_K4 + OV16_CONSTS),
    ("剑命中", OV16, 0x0C44, 0x0CFE, _hit_block("s", 4, 0xC, 0xB5F, 0xB73, 0xCFE) + H_ODDS),
    ("剑伤害", OV16, 0x0D6A, 0x0E26, S_DMG + H_PHYS),
    ("剑连击计数", OV16, 0x07CA, 0x07CD, "    call near h_swing"),
    ("枪会心与即死", OV16, 0x3556, 0x3732, G_CK + H_CKHEAD + H_CRIT + BS_HOOK),
    ("战斗开始", OV16, 0x1590, 0x1593, "    jmp near bs_hook"),
    ("枪命中", OV16, 0x384E, 0x3908, _hit_block("g", 4, 8, 0x3751, 0x3765, 0x3908) + H_RAND),
    ("枪伤害", OV16, 0x3920, 0x39F8, G_DMG),
    ("魔法命中值", OV16, 0x2ECE, 0x2ED1, "    jmp near h_mhit2e"),
    ("魔法命中", OV16, 0x2FBD, 0x305C, M_HIT),
    ("魔法攻击值", OV16, 0x309C, 0x30A5, "    jmp near h_mdsum"),
    ("魔法伤害", OV16, 0x30AA, 0x3122, M_DMG),
    ("魔法附加异常的命中值", OV16, 0x32FD, 0x3300, "    jmp near h_mhit32"),
]

# ---- 25CA: W9 the moon, W14 カジャ ----------------------------------------------------------------------------------
# The moon (25CA:8E68, damage x the attacker's multiplier, all three damage routines): sqrt(v / 50) in place of 2v / 100,
# v = ET0003 (the attacker's row, today's age, 25CA:8E4A, which the gate and the talks read raw as before). カジャ /
# ンダ (25CA:AE66): the six sets now from a table, the same values as before, and sets 3 and 5 (magic attack and hit)
# move the COMP attack and hit (+150h, +14Eh) by the same step, as the lab's sim3 does; those two are kept out of the
# sum 25CA:B0FA tests for "no effect".
SEG25 = ("main", 0x25CA)
KJ = f"""
kj_sets:                                ; 25CA:AF8F: ax = the set (0..5); si the target, [bp+8] its segment, di the step
    mov bx, ax
    mov bl, byte ptr cs:[bx + kj_at]
    add bx, kj_lists
kj_next:
    mov al, byte ptr cs:[bx]
    inc bx
    cmp al, 0xff
    je kj_end
    push bx
    push ax
    and ax, 0x7f
    add ax, ax
    add ax, 0xf6
    mov bx, ax
    mov dx, word ptr [bp + 8]
    lea ax, [bx + si + 0x30]
    push dx
    push ax
    push di
    mov es, dx
    push word ptr es:[bx + si]
    call 0xb120
    pop cx
    pop bx
    test cl, 0x80
    jne kj_next
    cwd
    add word ptr [bp - 4], ax
    adc word ptr [bp - 2], dx
    jmp short kj_next
kj_end:
    jmp near 0xb0fa
kj_at:
    db 0, 3, 6, 9, 14, 17
kj_lists:                               ; (offset - F6h) / 2 of each value (its battle copy 30h above); 80h: not summed
    db 3, 9, 0xff
    db 2, 8, 0xff
    db 5, 0xb, 0xff
    db 0xf, 0x95, 0xe, 0x94, 0xff
    db 0x10, 0x11, 0xff
    db 0xf, 0x95, 0xe, 0x94, 0x10, 0x11, 0xff
moon_new:                               ; 25CA:8E68(x long, row, k): x times sqrt(v / 50), v = ET0003 (row, today's age)
    push bp
    mov bp, sp
    push word ptr [bp + 8]
    mov al, byte ptr [0x98ea]
    sub ah, ah
    push ax
    push cs
    call 0x8e4a
    mov word ptr [bp + 6], ax
    fild word ptr [bp + 6]
    fmul qword ptr [0x629e]             ; 0.01, twice: / 50
    fadd st(0)
    fsqrt
    fild dword ptr [bp + 0xa]
    fmulp st(1)
    fistp dword ptr [bp + 0xa]
    fwait
    mov ax, word ptr [bp + 0xa]
    mov dx, word ptr [bp + 0xc]
    pop bp
    retf 8
"""
SEG25_BLOCKS = [
    ("カジャ的六组数值", SEG25, 0xAF8F, 0xB0FA, KJ),
    ("月相倍率", SEG25, 0x8E68, 0x8E6B, "    jmp near moon_new"),
]

SEG358 = ("main", 0x358E)
SEG358_BLOCKS = [
    ("剩余的派生值例程", SEG358, CAVE358[0], CAVE358[1], CAVE358_SRC),
    ("最大HP", SEG358, HP_AT, HP_AT + 3, "    jmp near hp_new"),
    ("回复量", SEG358, HEAL_AT, HEAL_AT + 3, "    jmp near heal_new"),
]

# ---- W11 growth: the redirected points go to the lowest attribute; a human's 体力 point on every third level ---------
# ov02:0272 draws a redirected point's attribute with 1603:4120(0, 9, 0); its pushes now hand the unit (segment,
# offset, 0) and the call's offset names LOWEST in 1603's unreachable cluster (4F20-53A0, past 等级差经验's code), the
# relocated segment word as it is. A capped pick is redrawn at random as before; for the lowest attribute that happens
# only when all ten are at 100 (358E:2320's cap), and then 0272 gives no point at all.
# The 体力 point (the user: on every level divisible by 3, and shown on the level-up screen) is one more growth point.
# 0FBC lists a level's tendency points at DS:9514 for both of a human's level-ups - the level-up screen (ov02:0617,
# which applies [9514]..[9518] one at a time, each shown) and the automatic one of a story command or a fusion
# (ov02:0A7D: four points, its own fourth at [951A]) - and now ends at VIT_END in 01D8's room, which far-calls FBC_VIT
# (after LOWEST, up to the cluster's end at 53A0, where no relocated word lies): on a human's level divisible by 3 it
# sets [951A] (the screen's fourth point) and [951C] (the automatic one's fifth)
# to 6, 体力, and the loops' bounds, [9524] the screen's count (0631 compares with it through VIT_CMP) and [9526] the
# automatic one's end (0ABE). Such a point goes through 0272 like the others (capped: redrawn at random).
SEG16 = ("main", 0x1603)
LOWEST = """
lowest:                                 ; far (unit segment, offset, 0) -> ax = its lowest attribute (+88h..+9Ah), the first on a tie
    push bp
    mov bp, sp
    push si
    les bx, ptr [bp + 8]
    xor ax, ax
    mov cx, word ptr es:[bx + 0x88]
    mov si, 2
lw_next:
    mov dx, word ptr es:[bx + si + 0x88]
    cmp dx, cx
    jge lw_skip
    mov cx, dx
    mov ax, si
    shr ax, 1
lw_skip:
    inc si
    inc si
    cmp si, 20
    jb lw_next
    pop si
    pop bp
    retf 6
fbc_vit:                                ; far, from ov02:0FBC's end (its frame at bp: [bp+2] the caller, [bp+4] the level
    xor cx, cx                          ; it was given, [bp+0Ah] the unit): a human's 体力 point on a level divisible by 3
    les bx, ptr [bp + 0xa]
    cmp word ptr es:[bx], 0x20
    jge fv_set
    mov ax, word ptr [bp + 4]           ; the screen (ov02:0617) gives the level being reached
    cmp word ptr [bp + 2], 0xa80        ; the automatic level-up (ov02:0A7D) raises the level after the points
    jne fv_lv
    mov al, byte ptr es:[bx + 0x6b]
    xor ah, ah
    inc ax
fv_lv:
    mov dl, 3
    div dl
    or ah, ah
    jne fv_set
    inc cx
    mov ax, 6                           ; 体力: the screen's fourth point, the automatic level-up's fifth
    mov word ptr [0x951a], ax
    mov word ptr [0x951c], ax
fv_set:
    mov ax, cx                          ; the bounds: [9524h] the screen's count, [9526h] the automatic one's end
    add ax, 3
    mov word ptr [0x9524], ax
    shl cx, 1
    add cx, 0x951c
    mov word ptr [0x9526], cx
    retf
"""
# W16 negotiation (the user, 2026-10-02: 「COMP 等级还应该对恶魔会话起到帮助」, and the rule they approved): the script
# VM's checks, commands 010-017 (and 105-10C, the same routine with the two sides swapped), all run 1603:8844, which
# reads the kind (si: 0-10 the attributes from +E0h, 11 the level, 12-14 the other side's mood bytes and its species
# value), has 9B50 put the protagonist's value S at [bp-0Ch] (a dword, its high word at [bp-0Ah]) and the other at
# [bp-8], then at 886B starts the result's default ([bp-2] = 0) before the kind's threshold and the compare at 8A31.
# 886B now calls COMP_TALK, in 1603's dead list helper 4DC2-4E31 (no caller, jump, pointer or relocated word reaches
# it), which does that and, while a negotiation record runs (the VM's selector word es:[58h], es = [61A0h], at
# E0h-EFh: the demon's pack; the record number at es:[0CEAh], es = [61A2h]; both set on every goto, call and return)
# and the sides are not swapped, raises S by the protagonist's COMP level C (roster member 0's +11Ah): S x (100 + C)
# / 100 for 直感 魔力 知力 敏捷性 器用 魅力 命运 (the kinds where a higher value mostly helps the talk; 精神力 力量
# 体力 加护 more often scare the demon off), S x (200 + C) / 200 for the level only in the join gate (MS6000 EC:44, the
# one record that lets a demon join: the protagonist's level against the demon's x 110-125%); the other checks and
# the demon's own values as they were.
COMP_TALK = """
comp_talk:                              ; near, from 8844's 886B (its frame): the default it replaces, then the COMP bonus
    mov word ptr [bp - 2], 0
    cmp word ptr [bp + 6], 0            ; 105-10C: S holds the other side's value
    jne ct_done
    cmp word ptr [bp - 0xa], 0
    jne ct_done
    mov es, word ptr [0x61a0]
    mov ax, word ptr es:[0x58]          ; the running record's selector
    sub ax, 0xe0
    cmp ax, 0xf
    ja ct_done
    cmp si, 11
    je ct_lv
    ja ct_done
    mov ax, 0x78d                       ; kinds 0 2 3 7 8 9 10: 直感 魔力 知力 敏捷性 器用 魅力 命运
    mov cx, si
    shr ax, cl
    test al, 1
    je ct_done
    mov cx, 100
    jmp short ct_apply
ct_lv:
    cmp word ptr es:[0x58], 0xec        ; the level: only in the join gate, EC:44
    jne ct_done
    mov es, word ptr [0x61a2]
    cmp word ptr es:[0xcea], 0x44
    jne ct_done
    mov cx, 200
ct_apply:                               ; S x (cx + C) / cx, C the protagonist's COMP level
    les bx, ptr [0x9973]
    mov ax, word ptr es:[bx + 0x11a]
    add ax, cx
    mul word ptr [bp - 0xc]
    div cx
    mov word ptr [bp - 0xc], ax
ct_done:
    ret
"""
TALK_CHECK_AT = 0x886B                  # 1603:8844's `mov word ptr [bp - 2], 0`
SEG16_BLOCKS = [("最低属性与体力点", SEG16, 0x52B9, 0x53A0, LOWEST), ("会话的COMP加成", SEG16, 0x4DC2, 0x4E32, COMP_TALK)]
OV02 = ("ov", 2)
PICK_AT, PICKCALL_AT, LUCK_AT, LUCK_END, LUCK_CALL = 0x0291, 0x0298, 0x01D8, 0x021D, 0x0208
FBC_END, SCREEN_COUNT, AUTO_END = 0x117B, 0x0631, 0x0ABE    # 0FBC's epilogue, 062C's loop compare, 0A94's loop end
OV04 = ("ov", 4)
SUMMON_CALL = 0x0101                    # ov04: lcall 358E:4B30 in the COMP's CALL


def _ov02_sites(lowest, lu358, fbc_vit):
    """ov02: 0272's pushes and its call's offset; 01D8 rewritten around its relocated word (the lcall at 0208) as a
    far call of LU358, its room holding VIT_FAR (a far call of 1603:bx), VIT_END and VIT_CMP; 0FBC's epilogue, the
    level-up screen's loop compare and the automatic level-up's loop end turned to them."""
    fixed = PROG["fixed"]
    push = Asm("push word ptr [bp + 8]\npush di\npush 0", PICK_AT).build()
    if len(push) != 6:
        raise RebalanceError("0272 的参数不是 6 字节")
    room = Asm(f"""
    push bp
    mov bp, sp
    push word ptr [bp + 6]
    push word ptr [bp + 4]
    jmp short {LUCK_CALL:#x}
vit_far:                                ; a far call of 1603:bx, with no relocated word
    pop cx
    push cs
    push cx
    mov cx, ds
    sub cx, {DS_TO[0x1603]:#x}
    push cx
    push bx
    retf
vit_end:                                ; 0FBC's end: FBC_VIT, then 0FBC's epilogue
    push ax
    mov bx, {fbc_vit:#x}
    call near vit_far
    pop ax
    pop si
    pop di
    leave
    ret 0xa
vit_cmp:                                ; the level-up screen's loop (0631): its count from FBC_VIT
    cmp ax, word ptr [0x9524]
    ret
""", LUCK_AT)
    head = room.build()
    if LUCK_AT + len(head) > LUCK_CALL:
        raise RebalanceError(f"ov02:01D8 的空间放不下 {len(head)} 字节")
    tail = Asm("pop bp\nret 4", LUCK_CALL + 5).build()
    if holes_in(OV02, LUCK_AT, LUCK_END) != [LUCK_CALL + 3] or holes_in(OV02, PICK_AT, PICK_AT + 6):
        raise RebalanceError("ov02 的重定位字不在原处")
    o = file_off(OV02, LUCK_CALL + 3)
    luck = (head + b"\xcc" * (LUCK_CALL - LUCK_AT - len(head)) + bytes([0x9A]) + struct.pack("<H", lu358)
            + fixed[o:o + 2] + tail)
    luck += b"\xcc" * (LUCK_END - LUCK_AT - len(luck))
    ends = [(FBC_END, "5e5fc9c20a00", Asm(f"jmp near {room.labels['vit_end']:#x}", FBC_END).build() + b"\xcc" * 3),
            (SCREEN_COUNT, "3d0300", Asm(f"call near {room.labels['vit_cmp']:#x}", SCREEN_COUNT).build()),
            (AUTO_END, "81ff1c95", Asm("cmp di, word ptr [0x9526]", AUTO_END).build())]
    sites = [(file_off(OV02, PICK_AT), push), (file_off(OV02, PICKCALL_AT), struct.pack("<H", lowest)),
             (file_off(OV02, LUCK_AT), luck)]
    for at, was, new in ends:
        o = file_off(OV02, at)
        if fixed[o:o + len(was) // 2] != bytes.fromhex(was) or len(new) != len(was) // 2 or \
                holes_in(OV02, at, at + len(new)):
            raise RebalanceError(f"ov02:{at:04X} 不是预期的代码")
        sites.append((o, new))
    return sites


# ---- W13's 攻击技能修复 part: GUNPANEL takes the raw panel --------------------------------------------------------------
# GUNPANEL (25CA:E43F, tools/skillfix.py) gives a gun skill the panel less its bullet; the panel +138h is W1's gun
# attack now, so it reads +140h, the battle copy of the raw gear word W1 keeps at +110h.
def _gunpanel_site():
    fixed = PROG["fixed"]
    lo, hi = file_off(SEG25, skillfix.CAVE), file_off(SEG25, skillfix.CAVE2_END)
    want = bytes.fromhex("268b853801")      # mov ax, word ptr es:[di + 0x138]
    at = fixed.find(want, lo, hi)
    if at < 0 or fixed.find(want, at + 1, hi) >= 0:
        raise RebalanceError("GUNPANEL 里找不到唯一的 es:[di + 0x138]")
    return at + 3, b"\x40"


# W3 speed (358E:1992): 4 sqrt(敏捷性) - 0.25 armour / max(1, sqrt(carry)), carry 力量 (+EAh) in place of 体力 (+ECh):
# the displacement byte of 19F8's `fild word ptr es:[bx + 0xec]` (CD 3C DF 87 EC 00). The floor of 1 as a signed
# compare is 能力值修复's (tools/statfix.py).
SPEED_AT = 0x19FC


def _need(off, n):
    """The toggle a site's starting bytes come from: None (as shipped), 能力值修复 or 攻击技能修复."""
    fixed = PROG["fixed"][off:off + n]
    if fixed == PROG["shipped"][off:off + n]:
        return None
    if fixed == PROG["stat"][off:off + n]:
        return statfix.NAME
    if fixed == PROG["skill"][off:off + n]:
        return skillfix.NAME
    raise RebalanceError(f"{EXE_NAME} 第 {off:#x} 字节起同时有两项修复的改动")


def _sites():
    """[(file offset, as the build has it before 再平衡, as changed, need)] and every block's labels."""
    fixed = PROG["fixed"]
    labels = {}
    pieces = []
    w1 = link([("派生值", SEG358, W1_START, W1_END, w1_source())] + SEG358_BLOCKS)
    for name, (code, labs) in w1.items():
        labels.update(labs)
    jump = Asm(f"jmp near {labels['derive']:#x}", W1_TAIL).build()
    pieces.append((file_off(SEG358, W1_TAIL), jump))
    for name, place, start, _end, _src in [("派生值", SEG358, W1_START, W1_END, "")] + SEG358_BLOCKS:
        pieces.append((file_off(place, start), w1[name][0]))
    if PROG["fixed"][file_off(SEG358, SPEED_AT) - 4:file_off(SEG358, SPEED_AT) + 2] != bytes.fromhex("cd3cdf87ec00"):
        raise RebalanceError("358E:1992 不是预期的代码")
    pieces.append((file_off(SEG358, SPEED_AT), b"\xea"))
    for blocks in (OV16_BLOCKS, SEG25_BLOCKS, SEG16_BLOCKS):
        linked = link(blocks)
        for name, place, start, _end, _src in blocks:
            code, labs = linked[name]
            labels.update(labs)
            pieces.append((file_off(place, start), code))
    pieces += _ov02_sites(labels["lowest"], labels["lu358"], labels["fbc_vit"])
    o = file_off(OV04, SUMMON_CALL)
    if PROG["fixed"][o:o + 3] != bytes.fromhex("9a304b") or holes_in(OV04, SUMMON_CALL, SUMMON_CALL + 5) != \
            [SUMMON_CALL + 3]:
        raise RebalanceError("ov04:0101 不是 lcall 358E:4B30")
    pieces.append((o + 1, struct.pack("<H", labels["summon_swap"])))
    pieces.append(_gunpanel_site())
    o = file_off(SEG16, TALK_CHECK_AT)
    if PROG["fixed"][o:o + 5] != bytes.fromhex("c746fe0000"):
        raise RebalanceError("1603:886B 不是 mov word ptr [bp - 2], 0")
    pieces.append((o, Asm(f"call near {labels['comp_talk']:#x}\nnop\nnop", TALK_CHECK_AT).build()))
    sites = []
    for off, new in pieces:
        sites.append((off, fixed[off:off + len(new)], new, _need(off, len(new))))
    return sites, labels


# DDS98.EXE (file offset = image address + 3800h): (offset, as shipped, as changed, the toggle it needs or None)
EXE_SITES, LABELS = _sites()


def table():
    """The bosses' table (tools/balance.py's form); balance.json, 难度调整, is in both packages."""
    return balance.load(REDESIGN_PATH)


def files(src_dir=SRC):
    """[(name under DDS98\\, label, as shipped, as changed)]: the learning pools."""
    return [poolfix.edit(src_dir)]


def exe():
    """The program's sites for tools/mkpatchbat.py."""
    return {"name": EXE_NAME, "label": EXE_LABEL, "sites": EXE_SITES}


def mend_exe(blob, revert=False):
    """DDS98.EXE with the sites in (or out). A site holding neither form stops everything."""
    out = bytearray(blob)
    for site in EXE_SITES:
        off, orig, fixed = site[:3]
        now = bytes(out[off:off + len(orig)])
        if now not in (orig, fixed):
            raise RebalanceError(f"{EXE_NAME} 第 {off:#x} 字节起既不是原版也不是再平衡后的内容")
        out[off:off + len(orig)] = orig if revert else fixed
    return bytes(out)


def apply_to(built, src_dir=SRC):
    """Write the tables and the whole files into a build's {file name: bytes} (a file the build has not written comes
    from src_dir). -> the names of the records written."""
    plains = {}

    def plain_of(stem):
        if stem not in plains:
            plains[stem] = records.plain_of(built.get(stem + ".BIN")
                                            or open(os.path.join(src_dir, stem + ".BIN"), "rb").read())
        return plains[stem]

    wrote, _stems = balance.apply_table(table(), plain_of)
    for stem, plain in plains.items():
        built[stem + ".BIN"] = records.encode(plain)
    for name, _label, a, b in files(src_dir):
        now = built.get(name) or open(os.path.join(src_dir, name), "rb").read()
        if now != a:
            raise RebalanceError(f"DDS98\\{name} 不是原版内容")
        built[name] = b
    return wrote


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = table()
    print(f"「{data['title']}」 {len(data['edits'])} 条记录")
    for target, entry in data["edits"].items():
        print(f"  {target} 「{entry.get('name', target)}」 {len(balance.edits(entry, target))} 个数值")
    for name, label, a, b in files():
        print(f"  「{label}」 DDS98\\{name} {len(a)} → {len(b)} 字节")
    needs = {}
    for site in EXE_SITES:
        needs[site[3]] = needs.get(site[3], 0) + 1
    print(f"  「{EXE_LABEL}」 {EXE_NAME} {len(EXE_SITES)} 处，" + "，".join(
        f"{k or '不依赖修复'} {v} 处" for k, v in needs.items()))


if __name__ == "__main__":
    main()
