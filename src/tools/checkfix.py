#!/usr/bin/env python3
"""The story checks the game's scripts get wrong, and the edits that mend them (剧情检定修复).

    checkfix.py [FILE…]     what each fix writes into files/DDS98

Threshold overwritten (command 1F5)
    Seven checks draw a threshold with 1F4 (lo + the average of k+1 draws in lo..hi, 1603:4120) and
    then run 1F5 on the same variable, whose handler (1603:7D98) stores the C library's rand()
    (0:15CC, 0..32767) over it - an attribute is at most 100, so each check all but always fails:
    merging with バール (MS002B r02, 精神力 against U(5..15) or U(15..30): at most 0.31%), the DB
    practical exam (MS0057: 敏捷性 against U(0..3)+5 to pick up the gun, then 器用 and 命运 against
    U(0..10)×2), 英美's voice in the prologue (MS0022, 精神力 against U(0..10)) and 泪's food visit
    (MS005F r05, 魅力 against U(0..10), which moves the two affection counters). 1F5 appears nowhere
    else. Its handler now reads its operand and returns: the far call of rand() becomes a retf, so
    the variable keeps the threshold 1F4 drew.

Affection that falls through
    The two hidden affection counters (4827:08E6 + 4n: counter 2 由宇香, counter 3 泪; 2DF reads,
    2DE writes) move by two in two places, and both times the block runs on into the other answer's
    -1/+1 with no jump in between: 泪's 「私を殺せる？」 はい (MS0020 r3F, 由宇香 -2 泪 +2, then
    +1/-1) and her 「私は恋人の代わり？」 「そんな事はない」 (MS0032 r26, the same, then the other
    answer's -1/+1 and the shared ending). Both nets are +1/-1 instead of +2/-2. The two steps of 2
    are now 3, so what the answer leaves is +2/-2; the other answer, which the block runs on into,
    keeps its -1/+1, and every line of text stays where it was.

Experience the script cannot write
    Command 23A sets a field of a character record through a table of handlers (1603:A398, entry =
    field - 0Ah); field 50h, experience (the dword at +6Eh, which 1E8 reads through the value reader
    1603:A1C4), has no handler and lands on the exit 1603:A718 - the only field scripts write that
    has none. Its one user is MS0008 r2B, the record ウエンディー, ミランダ and ジョセフィーヌ share
    after their scenes: it reads a character's experience into a local (locals are dwords,
    1603:B62E), adds 20, 30 or - ジョセフィーヌ, the first time only - 3000, and writes it back; the
    gift never arrives. Field 50h's entry now leads to a handler
    that writes the dword, the same four instructions as the Macca (0Ah) and MAG (0Ch) handlers at
    +6Eh instead of +72h/+76h. It sits in the unused head of the far helper at 1603:47F4 (no call,
    pointer or relocation reaches it; the whole-program trace never enters it). Levels are only
    settled where experience is awarded (ov02), so a gift that crosses a threshold makes the level
    at the next award; the status screen shows NEXT 0 meanwhile (ov11:0729 clamps it).

A fix is a storyfix.Fix (same-length operands, found by what they hold) or a site of DDS98.EXE; every
build carries them, with no switch; tools/checkfix_test.py runs 23A's dispatch, original and mended, on an
emulated CPU.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm86 import assemble  # noqa: E402
from storyfix import Fix, StoryFixError, record_edits  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98")
EXE = "DDS98.EXE"
NAME = "剧情检定修复"

# var23 (bank 3, index 17h) -= / += a byte value: the operands of 14F / 14E end [03 17][00 nn]
FIXES = [
    Fix("MS0020", 0, 0x3F, 0x14F, b"\x03\x17\x00\x02", b"\x03\x17\x00\x03",
        why="泪「你杀得了我吗？」答「是」：由宇香 -2（原来落进另一个答案，净 -1）"),
    Fix("MS0020", 0, 0x3F, 0x14E, b"\x03\x17\x00\x02", b"\x03\x17\x00\x03",
        why="同上：泪 +2（原来净 +1）"),
    Fix("MS0032", 0, 0x26, 0x14F, b"\x03\x17\x00\x02", b"\x03\x17\x00\x03",
        why="泪「我是恋人的替身吗？」答「没那回事」：由宇香 -2（原来净 -1）"),
    Fix("MS0032", 0, 0x26, 0x14E, b"\x03\x17\x00\x02", b"\x03\x17\x00\x03",
        why="同上：泪 +2（原来净 +1）"),
]

# DDS98.EXE, as file offsets (image + 3800h): the same in the Japanese executable and this build's.
# 1603:7D98 is 1F5's handler - push cs / call 78EE (its operand), then the far call of rand(); the
# site holds the call of 78EE as well, so it is recognised by more than the one byte it changes.
HDR, SEG16 = 0x3800, 0x16030
EXP_ENTRY = 0xA424                      # 23A's table 1603:A398 + 2 * (50h - 0Ah)
EXP_AT = 0x47F4                         # 1603:47F4-4804, the head of an unused far helper
EXP_ORIG = bytes.fromhex("c8 06 00 00 56 8b 4e 06 c7 46 fa 00 00 0b c9 74 3b")
SET_EXP = """
set_exp:                        ; 23A, field 50h: si = record, [bp-6] its segment, dx:[bp-4] the value
    mov ax, word ptr [bp - 4]
    mov es, word ptr [bp - 6]
    mov word ptr es:[si + 0x6e], ax
    mov word ptr es:[si + 0x70], dx
    jmp near 0xa718
"""
SET_EXP_CODE = assemble(SET_EXP, org=EXP_AT)[0]
if len(SET_EXP_CODE) != len(EXP_ORIG):
    raise StoryFixError("23A 经验值例程与所占位置长度不同")
# the entry with the three before and after it (fields 4Ch-53h): 4Ch-51h exit at A718, 52h-53h go to A63C
EXP_TABLE_ORIG = bytes.fromhex("18 a7 18 a7 18 a7 18 a7 18 a7 18 a7 3c a6 3c a6")
EXP_TABLE_FIXED = EXP_TABLE_ORIG[:8] + EXP_AT.to_bytes(2, "little") + EXP_TABLE_ORIG[10:]
EXE_SITES = [
    (0x215C8, bytes.fromhex("90 0e e8 51 fb 9a cc 15 00 00"), bytes.fromhex("90 0e e8 51 fb cb cc 15 00 00"),
     "命令 1F5 读完操作数就返回，不再用 rand() 覆盖检定阈值"),
    (HDR + SEG16 + EXP_ENTRY - 8, EXP_TABLE_ORIG, EXP_TABLE_FIXED,
     "命令 23A 的字段 50h（经验值）转到新例程，不再直接退出"),
    (HDR + SEG16 + EXP_AT, EXP_ORIG, SET_EXP_CODE,
     "新例程：把数值写进角色记录 +6Eh 的经验值（放在未使用的 1603:47F4）"),
]


def by_file():
    out = {}
    for f in FIXES:
        out.setdefault(f.stem, []).append(f)
    return out


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
    wanted = [a.upper() for a in argv]
    for stem, fixes in sorted(by_file().items()):
        if wanted and stem not in wanted:
            continue
        parsed = ddsfile.parse(open(os.path.join(SRC, stem + ".BIN"), "rb").read())
        for (ci, pos), (sites, _block) in sorted(record_edits(parsed, fixes).items()):
            print(f"{stem}/{ci}/{parsed[ci][pos].rid:02X}")
            for off, orig, fixed in sites:
                print(f"    @{off:04X} {orig.hex(' ')} -> {fixed.hex(' ')}")
        for f in fixes:
            print(f"    {f}  {f.why}")
    if not wanted or EXE in wanted:
        blob = open(os.path.join(SRC, EXE), "rb").read()
        for off, orig, fixed, why in EXE_SITES:
            now = blob[off:off + len(orig)]
            state = "原版" if now == orig else "修复后" if now == fixed else "都不是"
            print(f"{EXE} @{off:#x}（{state}）  {why}\n    {orig.hex(' ')} -> {fixed.hex(' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
