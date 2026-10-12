#!/usr/bin/env python3
"""What the end-of-battle summary says each member gained (经验值显示修复).

    expshow.py              what the fix writes into files/DDS98

How the game shares experience out
    Every enemy defeated adds its experience (+6Eh of its record) to the dword DS:9B0C (25CA:A942). The
    summary MS00DD 59 prints that sum through record 52: "〈一行〉获得了X点ＥＸＰ", the value 4F0002 of
    the reader 1603:A71C. The payout comes after it (the battle overlay's next state, ov16:242C): ov02:0362
    hands the sum to ov02:0000, which doubles it, divides it by 358E:4B7C(1) - the members in the six
    party slots whose status has none of 灰 死 瀕死 昏倒 石化 麻痺 凍結 (DS:2426) - with the C run-time's
    long division (0:19CC -> 0:1860), and adds the quotient to each of those members below level 99.
    So a member gains 2X÷N: twice what the summary says with the hero alone, the same with two, a third
    with six.

The fix
    Record 52 prints 4F0004 instead: the reader's index 4, which the game leaves at 0, now gives exactly
    what ov02:0000 adds to each member - twice DS:9B0C over 358E:4B7C(1), through the same division; 0
    when nobody can take a share. The summary's own reads of 4F0002 (MS00DD 59 at 0000 and 004B, which
    tell a won fight from one the enemy left, and skip the line when nothing was gained) keep the sum,
    so it runs as before. The line's wording says it is per member: 「获得了」 -> 「各获得」 in the Chinese
    build, 「の経験を積んだ」 -> 「ずつ獲得した」 in the Japanese original, the same number of bytes.

    The new code sits in the dead rest of the unused far helper at 1603:47F4 (tools/checkfix.py uses its
    first 17 bytes, 47F4-4804): no branch from outside the helper, far call, relocation or pointer reaches
    4805-4847, and the whole-program trace never enters it. It reaches the head count and the division
    in their own segments by pushing a return address and the target and doing a retf, so it needs no
    relocation: 358E is CS + 1F8Bh, the run-time's segment CS - 1603h.

The other place the game would show a sum of experience - a demon leaving some after a talk (MS00DF 2,
1603:E1A2 with kind 2) - is never reached: only command 16A asks for it, and no script holds 16A; the
talk outcomes (1603:DEFC) never pick it.

tools/mkfixbat.py writes the fix out as 「启用 / 关闭 经验值显示修复.bat」; tools/expshow_test.py runs the
reader and the payout on an emulated CPU and compares them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm86 import assemble  # noqa: E402
from storyfix import Fix, StoryFixError, record_edits, tokenize  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98")
EXE = "DDS98.EXE"
NAME = "经验值显示修复"
STEM, CHUNK, RECORD = "MS00DD", 0, 0x52          # 「〈一行〉获得了X点ＥＸＰ」

# DDS98.EXE as file offsets (image + 3800h), the same in the Japanese executable and this build's.
HDR, SEG16 = 0x3800, 0x16030
DEFAULT_AT = 0xA72C                     # A71C's fourth test, then its default: an index above 3 gives 0
DEFAULT_ORIG = bytes.fromhex("48 74 23 33 c0 eb 22 90")
SHARE_AT = 0x4805                       # 4805-4847, the dead rest of the helper at 47F4
SHARE = """
share:                          ; A71C, index above 3: ax = index - 3, bp = A71C's frame
    dec ax
    jne share_none
    push 1                      ; 358E:4B7C(1): the members who take a share
    push cs
    push share_n
    mov ax, cs
    add ax, 0x1f8b
    push ax
    push 0x4b7c
    retf
share_n:
    or ax, ax
    je share_none
    cwd                         ; the divisor, as ov02:0000 has it
    push dx
    push ax
    mov ax, word ptr [0x9b0c]   ; twice the summary's sum
    mov dx, word ptr [0x9b0e]
    shl ax, 1
    rcl dx, 1
    push dx
    push ax
    push cs                     ; 0:1860, long division; it takes its eight bytes off the stack
    push share_q
    mov ax, cs
    sub ax, 0x1603
    push ax
    push 0x1860
    retf
share_q:
    jmp near 0xa756             ; leave, ret 2
share_none:
    xor ax, ax
    jmp near 0xa755             ; cdq, leave, ret 2
"""
SHARE_CODE = assemble(SHARE, org=SHARE_AT)[0]
JUMP = assemble(f"jmp near {SHARE_AT:#x}", org=DEFAULT_AT + 3)[0]       # in place of xor ax, ax / jmp A755
DEFAULT_FIXED = DEFAULT_ORIG[:3] + JUMP + DEFAULT_ORIG[3 + len(JUMP):]


def _share_orig():
    blob = open(os.path.join(SRC, EXE), "rb").read()
    return blob[HDR + SEG16 + SHARE_AT:HDR + SEG16 + SHARE_AT + len(SHARE_CODE)]


SHARE_ORIG = _share_orig()
if SHARE_AT + len(SHARE_CODE) > 0x4848:
    raise StoryFixError("经验值份额例程超出了 1603:4805-4847")
if len(DEFAULT_FIXED) != len(DEFAULT_ORIG):
    raise StoryFixError("A71C 的跳转与原来的字节长度不同")
EXE_SITES = [
    (HDR + SEG16 + DEFAULT_AT, DEFAULT_ORIG, DEFAULT_FIXED,
     "读取 4F 类数值的 1603:A71C：序号大于 3 时转到新例程，不再直接给 0"),
    (HDR + SEG16 + SHARE_AT, SHARE_ORIG, SHARE_CODE,
     "新例程：序号 4 给每人实得的经验值 = 2×DS:9B0C÷358E:4B7C(1)，与发放用同一个除法（放在未使用的 1603:4805）"),
]


class Wording:
    """A stretch of a record's bytes rewritten to the same length, in whichever of its versions the
    record holds: forms are (original, new) pairs, one per version, and exactly one of the originals
    has to be in the record, once, beginning and ending where tokens do."""

    def __init__(self, stem, chunk, rid, forms, why=""):
        self.stem, self.chunk, self.rid, self.forms, self.why = stem, chunk, rid, forms, why
        if any(len(a) != len(b) for a, b in forms):
            raise StoryFixError(f"{self}: 原文与改后的字节数不同")

    def __str__(self):
        return f"{self.stem}/{self.chunk}/{self.rid:02X} 文字"

    def edits(self, payload, _end):
        found = [(payload.find(a), a, b) for a, b in self.forms if payload.count(a) == 1]
        if len(found) != 1 or any(payload.count(a) > 1 for a, _b in self.forms):
            raise StoryFixError(f"{self}: 记录里找不到唯一一处要改的原文")
        at, a, b = found[0]
        bounds = {t.start for t in tokenize(payload)} | {len(payload)}
        if at not in bounds or at + len(a) not in bounds:
            raise StoryFixError(f"{self}: 要改的原文没有落在命令边界上")
        return [(at, a, b)], b""


def by_file(charmap=None, english=False):
    """The script edits. The Chinese wording is encoded with the build's charmap, so it is known only
    to a build; without one only the Japanese original's can be found."""
    forms = [("の経験を積".encode("cp932") + b"\x08\x5f",           # dict7[95]「んだ」
              "ずつ獲得した".encode("cp932"))]
    if english:
        forms = [(b"\x04\x19 gained ", b"Each gets ")]
    if charmap is not None:
        from textbuild import encode_plain
        forms.append((encode_plain("获得了", charmap), encode_plain("各获得", charmap)))
    return {STEM: [
        Fix(STEM, CHUNK, RECORD, 0x102, b"\x4f\x00\x02", b"\x4f\x00\x04",
            why="结算的经验值那一行改印 4F0004（每人实得）"),
        Wording(STEM, CHUNK, RECORD, forms, why="「获得了」→「各获得」／「の経験を積んだ」→「ずつ獲得した」"),
    ]}


def apply_to(parsed, fixes):
    """Mend a parsed file as the game ships it. -> the edits made, as storyfix.record_edits() gives
    them."""
    edits = record_edits(parsed, fixes)
    for (ci, pos), (sites, _block) in edits.items():
        out = bytearray(parsed[ci][pos].payload)
        for off, orig, fixed in sites:
            if bytes(out[off:off + len(orig)]) != orig:
                raise StoryFixError(f"第 {off} 字节起不是原版的 {orig.hex(' ')}")
            out[off:off + len(orig)] = fixed
        parsed[ci][pos].payload = bytes(out)
    return edits


def mend_exe(blob, revert=False):
    """DDS98.EXE with the fix in (or out). A site holding neither form stops everything."""
    out = bytearray(blob)
    for off, orig, fixed, _why in EXE_SITES:
        now = bytes(out[off:off + len(orig)])
        if now not in (orig, fixed):
            raise StoryFixError(f"{EXE} 第 {off:#x} 字节起既不是原版也不是修复后的内容")
        out[off:off + len(orig)] = orig if revert else fixed
    return bytes(out)


def main(argv):
    import ddsfile
    parsed = ddsfile.parse(open(os.path.join(SRC, STEM + ".BIN"), "rb").read())
    for (ci, pos), (sites, _block) in sorted(record_edits(parsed, by_file()[STEM]).items()):
        print(f"{STEM}/{ci}/{parsed[ci][pos].rid:02X}")
        for off, orig, fixed in sites:
            print(f"    @{off:04X} {orig.hex(' ')} -> {fixed.hex(' ')}")
    for off, orig, fixed, why in EXE_SITES:
        print(f"{EXE} {off:#07x} ({len(orig)} 字节) {why}")
        print(f"    {orig.hex(' ')}\n -> {fixed.hex(' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
