#!/usr/bin/env python3
"""The moon changes every 300 game minutes, about 60 dungeon steps, instead of every 1520 (月相加速).

    moonfast.py [DDS98.EXE]     the state of every site, and the edit of コアシールド's description

The clock
    25CA:8A08(m) is the only thing that moves game time on: a dungeon step adds 3-7 minutes (358E:8597),
    a move on the world map 5 per tile (ov42:029A), a script its own count (1603:C830), the main loop one
    per 600 idle passes. It hands m to 25CA:8A66, which carries minutes into hours and days and, apart
    from that, adds m to the minutes into the current phase (DS:98E8); every 1520 there the moon's age
    (DS:98EA, 0-27, shown as 1/28-28/28) moves on one. A phase lasts 25h20m of game time, about 300
    steps, and a month 29.6 days. When a phase begins, 8A08 calls 25CA:8B56 for the per-phase work.

The fix
    8A66 divides by 300 (25CA:8ACE), and 25CA:8DC8 - the minutes until a given age, for ＠月齢計算:
    時だましの香 (MS003F) and the story's skip to the full moon (MS0064) - multiplies by 300 (25CA:8DDC),
    so both still land at the start of the phase they aim for. Everything that reads the age comes round
    about five times as often: damage ×2v/100, the crit and instant-death gate, negotiation, the full-moon
    events and the ornate boxes' night. A phase is still long enough for what the story times by one:
    after the skip to the full moon (MS0064) the werewolf's door in 御田急ハルク (M000D section 4 (9,2),
    live only while 00:23 is 0) is 27 steps from where the party lands by the shortest way through the
    building's walls, stairs and lifts - 189 minutes at most.

What keeps the original's pace
    Three things of 8B56's are an allowance per phase or per month, and five times as many phases would
    give them five times as often:
      07:FD    コアシールド (one in the game, used up) keeps barrier and element floors from hurting the
               party until the moon changes (358E:7C25); every phase change clears it
      07:FE/FF ソーマの杯 and 櫛名田の酒甕 can each be used once until the next full moon; a phase change
               landing on age 14 clears them
      ET0019   fifteen treasure boxes - thirteen gem boxes that open only at 15/28, 520 マッカ, four
               エンゼルヘアー - whose "emptied" flags a phase change landing on age 15 clears (25CA:8B08)
    Short jumps take the three out of 8B56 (25CA:8B65, 8C38, 8C57), leaving the relocated far calls they
    skip as they are, and 8A08's call of 8B56 (25CA:8A45) goes to a new routine that calls it and then
    keeps the original moon. That moon is a function of the game's total minutes T = 25CA:8DFE() =
    days·1440 + hours·60 + minutes: a new game zeroes both clocks (25CA:8954) and 8A66 gives both the
    same minutes, so the original moon has changed ⌊T/1520⌋ times and stands at age ⌊T/1520⌋ mod 28, and
    a call of 8A08 has begun an original phase when T mod 1520 < m. Then, as in the original and at the
    same minutes, コアシールド ends, and when that phase is age 15 the boxes are full again. When it is age
    14 the cup and the jar become due, and they fill at the next visible full moon: in the first call
    that ends in one or passes through its start - the minutes since the visible moon last turned full,
    (age − 14 mod 28)·300 + DS:98E8, fewer than the call's - so a rest that sleeps through the full moon
    fills them too. Every original month thus gives them once, as the original does, at the first
    visible full moon from the original's moment on - at most 28 visible phases, 8400 minutes, later -
    and so at a full moon, as the game says. What is due is kept in a
    flag that no script, map, table or code refers to, 07:F0, 0 while due; a new game sets it to 1, as it
    does every flag of the group, so every save made without this fix holds 1 there too. The routine
    sits in 25CA:8D60-8DC7, an unused timer setter and its countdown: no near or far call, jump or
    pointer reaches it - in the segment, in DGROUP or in any overlay - no relocation lies in it, and the
    segment makes no indirect call or jump. Dried-up body parts keep their own time (25CA:F424:
    28·1520 minutes after they are taken).

Saves
    A save holds the minutes into the phase. One made without the fix can hold up to 1519, so a load
    (25CA:8C86) now keeps them modulo 300 (25CA:8CB7): the moon stays at the age it was saved at, and
    ＠月齢計算 cannot go below zero. A save made with the fix holds less than 300, which the original
    reads as it is.

コアシールド's description says it lasts until the moon changes; its first words become 「效力至多约一天，」
in this build and 「最長で約一日の間、」 in the Japanese original, the same number of bytes each.

tools/mkfixbat.py writes the fix out as 「启用 / 关闭 月相加速.bat」; tools/moonfast_test.py runs the clock
of both programs on an emulated CPU and compares them.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm86 import assemble  # noqa: E402
from tables import ITEM_HEADER, chunks_bytes, chunks_of, string_table  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98")
NAME = "月相加速"
EXE = "DDS98.EXE"
TABLE = "ET0001"
HDR, SEG25 = 0x3800, 0x25CA0            # DDS98.EXE: file offset = HDR + SEG25 + offset in 25CA
PHASE, FAST = 1520, 300                 # minutes a phase lasts, in the original and with the fix
FLAGS = 0x79E2                          # DS: 32 bytes a group, the first flag of a byte its bit 7
DUE = FLAGS + 7 * 32 + 0xF0 // 8        # 07:F0 (80h): 0 while the cup and the jar are due
MONTHLY = FLAGS + 7 * 32 + 0xFD // 8    # 07:FD (04h) コアシールド, 07:FE (02h) and 07:FF (01h) the cup, the jar
CAVE, CAVE_END = 0x8D60, 0x8DC8         # 25CA:8D60-8DC7; 8DC8 is live
ENTRY, KIND = 113, 5                    # ET0001: コアシールド, an item of kind 5
DESC_JP = ("月が変化するまで、", "最長で約一日の間、")
DESC_CN = ("在月相变化之前，", "效力至多约一天，")
CHARS = set(DESC_CN[1])                 # what a build must give codes and glyphs to

ROUTINE = f"""
moon:                           ; 8A45: in place of 8B56(bits); si = 8A66's bits, di = the minutes
    push si
    call 0x8b56                 ; the visible moon's per-phase work, less the three below
    push si
    push di
    push cs
    call 0x8dfe                 ; dx:ax = T, the minutes since the new game, these included
    mov cx, {PHASE}
    div cx                      ; ax = the original moon's changes, dx = the minutes into this phase
    cmp dx, di
    jae moon_give               ; this call began no original phase
    and byte ptr [{MONTHLY:#x}], 0xfb   ; 07:FD: コアシールド ends
    xor dx, dx
    mov cx, 28
    div cx                      ; dx = the age the original moon has come to
    sub dl, 14
    jne moon_15
    and byte ptr [{DUE:#x}], 0x7f       ; 14: 07:F0 = 0, the cup and the jar are due
moon_15:
    dec dl
    jne moon_give
    call 0x8b08                 ; 15: the boxes of ET0019 are full again
moon_give:
    test byte ptr [{DUE:#x}], 0x80
    jne moon_done               ; the cup and the jar are not due
    mov al, byte ptr [0x98ea]   ; the visible moon
    sub al, 14
    je moon_fill                ; full now
    jae moon_since
    add al, 28
moon_since:                     ; al = the phases since it was last full, 1-27
    cbw
    imul ax, ax, {FAST}
    add ax, word ptr [0x98e8]   ; the minutes since it turned full
    cmp ax, di
    jae moon_done               ; before this call
moon_fill:
    or byte ptr [{DUE:#x}], 0x80
    and byte ptr [{MONTHLY:#x}], 0xfc   ; 07:FE, 07:FF: the cup and the jar are full again
moon_done:
    pop di
    pop si
    ret

moon_load:                      ; 8CB7, a save being loaded: ax = its minutes into the phase
    xor dx, dx
    mov cx, {FAST}
    div cx
    mov word ptr [0x98e8], dx
    ret
"""


class MoonFixError(ValueError):
    pass


CODE, AT = assemble(ROUTINE, org=CAVE)
if CAVE + len(CODE) > CAVE_END:
    raise MoonFixError(f"新例程 {len(CODE)} 字节，超出了 25CA:{CAVE:04X}-{CAVE_END - 1:04X}")


def _near(org, text):
    return assemble(text, org=org)[0]


def _orig(off, n):
    blob = open(os.path.join(SRC, EXE), "rb").read()
    return blob[HDR + SEG25 + off:HDR + SEG25 + off + n]


# (offset in 25CA, the original's bytes, the fix's, why)
_SITES = [
    (0x8ACE, bytes.fromhex("b9f005"), _near(0x8ACE, f"mov cx, {FAST}"),
     f"25CA:8A66 的月相长度：{PHASE} 分钟 → {FAST} 分钟"),
    (0x8DDC, bytes.fromhex("69c3f005"), _near(0x8DDC, f"imul ax, bx, {FAST}"),
     f"25CA:8DC8（到某月龄还要多少分钟，时之香与剧情跳到满月用）按 {FAST} 分钟一相计算"),
    (0x8A45, bytes.fromhex("56e80d01"), _near(0x8A45, f"nop\ncall {AT['moon']:#x}"),
     "25CA:8A08 在月相变化时不再直接调用 8B56，改调新例程"),
    (0x8B65, bytes.fromhex("6a07"), _near(0x8B65, "jmp 0x8b71"),
     "8B56 不再在每次月相变化时解除核心护盾（07:FD），交给新例程按原版节奏处理"),
    (0x8C38, bytes.fromhex("803e"), _near(0x8C38, "jmp 0x8c57"),
     "8B56 不再在满月时让苏摩之杯、栉名田之酒瓮可以再用（07:FE、07:FF），交给新例程"),
    (0x8C57, bytes.fromhex("803e"), _near(0x8C57, "jmp 0x8c61"),
     "8B56 不再在满月次日补满 ET0019 的宝箱，交给新例程按原版节奏处理"),
    (0x8CB7, bytes.fromhex("a3e898"), _near(0x8CB7, f"call {AT['moon_load']:#x}"),
     f"读档时把本相已过的分钟数取 {FAST} 的余数（原版存档可到 {PHASE - 1}）"),
    (CAVE, _orig(CAVE, len(CODE)), CODE,
     "新例程：按总分钟数推算原版的月相，核心护盾、杯与酒瓮、宝箱照原版节奏（放在未使用的 25CA:8D60）"),
]
for _off, _a, _b, _why in _SITES:
    if len(_a) != len(_b):
        raise MoonFixError(f"25CA:{_off:04X} 改后的字节数与原来不同")
EXE_SITES = [(HDR + SEG25 + off, a, b, why) for off, a, b, why in _SITES]


def mend_exe(blob, revert=False):
    """DDS98.EXE with the fix in (or out). A site holding neither form stops everything."""
    out = bytearray(blob)
    for off, orig, fixed, _why in EXE_SITES:
        now = bytes(out[off:off + len(orig)])
        if now not in (orig, fixed):
            raise MoonFixError(f"{EXE} 第 {off:#x} 字节起既不是原版也不是修复后的内容")
        out[off:off + len(orig)] = orig if revert else fixed
    return bytes(out)


def exe_state(blob):
    """'orig' or 'fixed' - every site has to be in the same one."""
    seen = set()
    for off, orig, fixed, _why in EXE_SITES:
        now = bytes(blob[off:off + len(orig)])
        if now not in (orig, fixed):
            raise MoonFixError(f"{EXE} 第 {off:#x} 字节起既不是原版也不是修复后的内容")
        seen.add("orig" if now == orig else "fixed")
    if len(seen) != 1:
        raise MoonFixError(f"{EXE} 只改了一部分")
    return seen.pop()


def desc_forms(charmap=None, english=False):
    """(original, new) bytes of the head of コアシールド's description, one pair per version: the Japanese
    original's always, this build's when its charmap is given - the Chinese is known only to a build."""
    forms = [tuple(t.encode("cp932") for t in DESC_JP)]
    if english:
        forms = [(b"Negates all environment damage until the next full moon.",
                  b"Negates environment damage for up to 3000 game minutes. ")]
    if charmap is not None:
        from textbuild import encode_plain
        forms.append(tuple(encode_plain(t, charmap) for t in DESC_CN))
    for a, b in forms:
        if len(a) != len(b):
            raise MoonFixError("核心护盾说明改后的字节数与原来不同")
    return forms


def desc_at(plain):
    """(start of コアシールド's description, end of its entry) in ET0001's plaintext: after the kind's
    header and the name."""
    entries = string_table(plain)
    e = entries[ENTRY]
    if len(e) <= 4 or e[4] != KIND:
        raise MoonFixError(f"{TABLE} 第 {ENTRY} 条不是第 {KIND} 类物品")
    name_end = e.find(b"\0", ITEM_HEADER[KIND])
    if name_end < 0:
        raise MoonFixError(f"{TABLE} 第 {ENTRY} 条没有名字的结尾")
    at = struct.unpack_from("<H", plain, 2 + 2 * ENTRY)[0]
    return at + name_end + 1, at + len(e)


def mend_table(blob, forms, revert=False):
    """ET0001.BIN with コアシールド's description in the wanted form: its head rewritten where it stands
    and the chunk encrypted again, as the .bat does it (the file keeps its length). Exactly one of the
    forms has to be there, in either state."""
    (plain,) = chunks_of(blob)
    start, end = desc_at(plain)
    hits = [(a, b) for a, b in forms if start + len(a) <= end and plain[start:start + len(a)] in (a, b)]
    if len(hits) != 1:
        raise MoonFixError(f"{TABLE} 第 {ENTRY} 条（核心护盾）的说明既不是原版也不是修复后的内容")
    a, b = hits[0]
    out = bytearray(plain)
    out[start:start + len(a)] = a if revert else b
    return chunks_bytes([bytes(out)])


def main(argv):
    exe = argv[0] if argv else os.path.join(SRC, EXE)
    blob = open(exe, "rb").read()
    print(f"{exe}：{'已修复' if exe_state(blob) == 'fixed' else '原版'}")
    for off, orig, fixed, why in EXE_SITES:
        print(f"  文件 {off:#07x}（{len(orig)} 字节）{why}")
        if len(orig) <= 16:
            print(f"      {orig.hex(' ')}\n   -> {fixed.hex(' ')}")
    print(f"  新例程 25CA:{CAVE:04X}-{CAVE + len(CODE) - 1:04X}，{len(CODE)} 字节（可用 {CAVE_END - CAVE}）")
    print(f"{TABLE} 第 {ENTRY} 条（核心护盾）的说明开头：「{DESC_JP[0]}」→「{DESC_JP[1]}」，"
          f"汉化版「{DESC_CN[0]}」→「{DESC_CN[1]}」")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
