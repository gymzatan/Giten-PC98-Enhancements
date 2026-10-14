#!/usr/bin/env python3
"""A battle line on screen for its own hold, a click from before a hold that does not end it, and the command
panel's short notices up as long as the game's other ones.

How a battle line reaches the screen. 25CA:88DC(file, record, count) clears the message window [1BBA] (25CA:8782:
the text rows emptied, the text cursor home), sets [1CEA] to 1, runs the record into the window (1603:58EE, the
text going into the window's rows), sets [1CEA] back and only then draws the window (25CA:87C8 -> 882E ->
25CA:3D0C mode -2, which paints its rows) and leaves it up for `count` main-loop passes (25CA:8850; below 1, 15).
Script command 210 (1603:C1EA) sets its wait up through 25CA:84B0 and, while [1CEA] is 1, waits where it stands
(1603:C248, a vsync frame and the wait's check 25CA:8444 per pass) - before the window has been drawn. So a hold
shows whatever was on screen before the run: the line before it, or the line of the run before. The game's own
holds sit at the start of a run (the pause ahead of a defeat line: the damage line stays), and each line the
translation's holds (tools/holds.py) hold was seen only during the next run's holds; a line followed by a run
without any - the defeat line before the summary, 敌人逃跑了 - stayed up for the window's 15 passes.

A wait of mode 2 (a count a click cuts short) has the mask FFFF (1603:C1F3), and 25CA:8444 ends it when the mask
allows a held left button (bit 0), a left press this frame (bit 1) or the right button is held ([98F8] bits 0, 2,
4, kept per vsync by 0871:5142). The click that picked a target is still held when the first line of the action
starts its hold (the action begins a frame later), so that line's hold ended at once.

The command panel's notices - [ITEM] nobody can use it, [DDS] / [MAPPING] the device is missing, [FIGHT] / [TALK]
nobody to fight or talk to - go up through 25CA:8758(text, -1): 15 passes. Every other notice the game puts up
that way (the doors, the DAS, the battle's action names) asks for 60.

The change, two call sites, two blocks and five counts:

  1603:C240  the blocking path's first far call, to 25CA:8090 (the game state), goes to 358E:4174 (DRAW): when
             the window [1BBA] is open and its text cursor is off its home - the record has written to it since
             it was cleared - 25CA:882E draws it, then on to 8090. A hold ahead of any text (the game's own pause
             at the start of a defeat line) leaves the screen as it is.
  1603:C22F  the wait's setup, 25CA:84B0, is reached through 358E:4148 (SETUP): when the left button is held as
             the wait is set up, the mask's bit 0 is cleared on the stack, so a button held from before the wait
             does not end it; a new press does, and the right button held still does. Waits whose mask lacks
             bit 0 (a click wait, mode 1, has 2) are unchanged.
  358E:4148-415A and 358E:4174-41AD  the two blocks, in three status wrappers (4148, 4174, 418A; 41A0's first
             bytes) nothing can enter: no near branch lands in 4148-415D or 4174-41B5, no far pointer, far call
             or relocation names 358E:4148, 4174, 418A or 41A0, and no instruction carries 4174, 418A or 41A0
             (4148 only as a string offset pushed with DS in segment 0871). The add-on of tools/targetprompt.py
             keeps 411C-4147 and 415E, between them. Each block goes on to its 25CA routine with a far return,
             25CA being CS - 0FC4h, so no relocation is added; the call sites keep their relocations and change
             only their offsets.
  25CA:5B57, 5BB3, 5C26, 5CAA, 5D5B  the notices' `push -1` (6A FF) -> `push 60` (6A 3C).

All of it goes into every build with the holds, with no switch. 汉化补丁.html brings an older Chinese image up to it
(tools/cnretouch.py pace). The user (2026-10-13): 「"没有战斗对象""没有会话对象"还是闪过得太快了，战斗消息里面打倒了
某敌方单位的消息也闪过得太快」, then 「能否都统一显示 1 秒」 and 「不需要汉化节奏.bat了…从发布包里删掉」.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm86 import assemble  # noqa: E402

NAME = "战斗消息停顿显示"
FILE = "DDS98.EXE"
HDR = 0x3800                            # DDS98.EXE's header: file offset = HDR + segment * 16 + offset
SEG = 0x358E
WINDOW_SEG = 0x25CA
SETUP_AT, SETUP_END = 0x4148, 0x415E    # 358E:4148-415D, the third status wrapper
DRAW_AT, DRAW_END = 0x4174, 0x41B6      # 358E:4174-41B5, the fifth to seventh
WRAPPERS = bytes.fromhex(
    "558becff7608ff76066a196a0d900ee8eefec9ca0400"      # 4148 (4048 with 19, 0D)
    "55"                                                # 415E: the target prompt's flag, kept
    "8becff7608ff76066a1d6a1e900ee8d8fec9ca0400"        # 415F-4173
    "558becff7608ff76066a0e6a12900ee8c2fec9ca0400"      # 4174 (4048 with 0E, 12)
    "558becff7608ff76066a0f6a20900ee810ffc9ca0400"      # 418A (40AC with 0F, 20)
    "558becff7608ff76066a156a06900ee8fafec9ca0400")     # 41A0 (40AC with 15, 06)
WRAP_AT = SETUP_AT

DRAW_SRC = f"""
draw:                                   ; far-called from 1603:C240 in place of 25CA:8090
    mov bx, word ptr [0x1bba]           ; the message window
    cmp bx, -1
    je state
    imul bx, bx, 0x34                   ; its record, DS:6E30 + 34h x window
    xor ax, ax
    test byte ptr [bx + 0x6e4e], 1      ; +1Eh bit 0: the home row is +10h, else 0 (25CA:2DCE)
    je home
    mov ax, word ptr [bx + 0x6e40]
home:
    cmp word ptr [bx + 0x6e3c], ax      ; +0Ch the cursor's row
    jne paint
    cmp word ptr [bx + 0x6e3e], 0       ; +0Eh its column
    je state
paint:
    push cs                             ; 25CA:882E draws the window and returns here
    push state
    mov bx, 0x882e
    jmp far25
state:
    mov bx, 0x8090                      ; on to 25CA:8090, which returns to 1603:C245
far25:                                  ; a far jump to 25CA:bx
    mov ax, cs
    sub ax, {SEG - WINDOW_SEG:#x}
    push ax
    push bx
    retf
"""


def blocks():
    """{start offset in 358E: bytes} - the two blocks, each followed by what was there."""
    draw, labels = assemble(DRAW_SRC, org=DRAW_AT)
    setup, _ = assemble(f"""
setup:                                  ; far-called from 1603:C22F in place of 25CA:84B0(arg, count, mask, mode)
    test byte ptr [0x98f8], 1           ; the left button held as the wait is set up
    je go
    mov bx, sp
    and byte ptr ss:[bx + 8], 0xfe      ; the mask: a held left button no longer ends this wait
go:
    mov bx, 0x84b0
    jmp {labels['far25']:#x}
""", org=SETUP_AT)
    if SETUP_AT + len(setup) > SETUP_END or DRAW_AT + len(draw) > DRAW_END:
        raise ValueError("the blocks do not fit the wrappers")
    return {SETUP_AT: setup, DRAW_AT: draw}


def far(off, seg):
    return b"\x9a" + struct.pack("<HH", off, seg)


def at(seg, off):
    return HDR + seg * 16 + off


# the command panel's notices: (the build's wording, 25CA offset of the push of the count, 6A FF / 6A 3C)
NOTICES = [("[ITEM] 没有能使用的人", 0x5B57), ("[DDS] 未持有DDS", 0x5BB3), ("[FIGHT] 没有战斗对象", 0x5C26),
           ("[TALK] 没有会话对象", 0x5CAA), ("[MAPPING] 未持有AMS", 0x5D5B)]
NOTICE_ORIG, NOTICE_FIXED = b"\x6a\xff", b"\x6a\x3c"


def sites():
    """[(name, file offset, original, changed)]: the call sites, the blocks (the wrappers, with the blocks written
    over their start and the target prompt's flag byte left out of both) and the notices' counts."""
    out = [("停顿前先画出消息窗口", at(0x1603, 0xC240), far(0x8090, WINDOW_SEG), far(DRAW_AT, SEG)),
           ("等待开始时已按住的左键不算", at(0x1603, 0xC22F), far(0x84B0, WINDOW_SEG), far(SETUP_AT, SEG))]
    for start, code in blocks().items():
        lo = start - WRAP_AT
        out.append((f"358E:{start:04X} 的新增例程", at(SEG, start), WRAPPERS[lo:lo + len(code)], code))
    for name, off in NOTICES:
        out.append((name, at(WINDOW_SEG, off), NOTICE_ORIG, NOTICE_FIXED))
    return out


class HoldShowError(ValueError):
    pass


def state(blob):
    """'orig' or 'fixed' - every site in the same form, else HoldShowError."""
    forms = set()
    for name, o, a, b in sites():
        now = bytes(blob[o:o + len(a)])
        if now == a:
            forms.add("orig")
        elif now == b:
            forms.add("fixed")
        else:
            raise HoldShowError(f"{FILE} 第 {o:#x} 字节起（{name}）既不是原版也不是本项改动后的内容")
    if len(forms) != 1:
        raise HoldShowError(f"{FILE} 里本项的各处改动不一致（有的打了，有的没打）")
    return forms.pop()


def apply_to(blob, revert=False):
    """DDS98.EXE with the change in (or out)."""
    state(blob)
    out = bytearray(blob)
    for _name, o, a, b in sites():
        out[o:o + len(a)] = a if revert else b
    return bytes(out)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exe")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    blob = open(a.exe, "rb").read()
    try:
        before = state(blob)
        out = apply_to(blob, a.revert)
    except HoldShowError as e:
        raise SystemExit(f"{NAME}：{e}")
    open(a.exe, "wb").write(out)
    print(f"{a.exe}: {before} -> {state(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
