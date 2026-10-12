#!/usr/bin/env python3
"""The 12 bytes of near heap every script run leaves behind, given back.

1603:58EE runs one script record: it makes a context node with 1603:73D6 (m_calloc(1, 12), 0871:79F0: a tag
word, the data pointer, the call-frame depth and two more words), makes it the current context (1603:7372 ->
7438, the far pointer at 4827:08E2), runs the record, takes the node back (1603:7468) and tidies it with 1603:73BE
(pop the call frames still on it, 579A; then C324). The node itself is never freed. Every other maker of these
nodes (1603:A883 / AA62 / ACF7, ov16:4501 / 4594, ov32:0481, ov34:00D2) ends with 1603:7416 instead, which is 73BE
followed by m_free of the node (0871:7ABA). Those callers leave the current-context pointer on the freed node as
well; the next run sets a new one before anything reads it, and neither caller of 58EE (58C6, 25CA:88F8) reads the
context after the call.

Every battle message and every action that runs a script goes through 58EE, so a long fight loses a node per
script run. The near heap lives in DGROUP: in play it holds 70-170 blocks, and the extra nodes push it past what
DGROUP has left - the user's long session had 306 live blocks and had grown the heap to DS:DFFE. Then small
requests fall to the far heap, and when that is spent too, 0871:79F0 asserts at s:\\iodrv\\m_alloc.c line 119
(both heaps failed) and the game exits - after hours of unattended battles.

The fix calls 7416 there: 1603:592C `call 73BE` (e8 8f 1a) becomes `call 7416` (e8 e7 1a). The node is freed the
way the other makers free theirs. Both routines take the node as their only argument and return with retf 4. The
window checked is the routine's tail from the call that takes the node back to its return; only the call's
displacement changes and no relocation lies in it. It goes into every build, with no switch: it changes nothing
but the memory that is given back.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NAME = "剧本内存泄漏修复"
FILE = "DDS98.EXE"
HDR = 0x3800                            # DDS98.EXE's header: file offset = HDR + segment * 16 + offset
SEG, OFF = 0x1603, 0x5923
AT = HDR + SEG * 16 + OFF
# 5923 push cs / call 7468 (take the node back), push dx / push ax, push cs / call 73BE, mov ax,si / pop si /
# leave / retf 6
ORIG = bytes.fromhex("90 0e e8 40 1b 52 50 90 0e e8 8f 1a 8b c6 5e c9 ca 06 00")
FIXED = ORIG[:10] + bytes.fromhex("e7 1a") + ORIG[12:]


class CtxFreeError(ValueError):
    pass


def state(blob):
    """'orig' or 'fixed'."""
    now = bytes(blob[AT:AT + len(ORIG)])
    if now == ORIG:
        return "orig"
    if now == FIXED:
        return "fixed"
    raise CtxFreeError(f"{FILE} 第 {AT:#x} 字节起既不是原版也不是修复后的内容")


def apply_to(blob, revert=False):
    """DDS98.EXE with the context node freed (or leaked again)."""
    state(blob)
    out = bytearray(blob)
    out[AT:AT + len(ORIG)] = ORIG if revert else FIXED
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
    except CtxFreeError as e:
        raise SystemExit(f"{NAME}：{e}")
    open(a.exe, "wb").write(out)
    print(f"{a.exe}: {before} -> {state(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
