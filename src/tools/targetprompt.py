#!/usr/bin/env python3
"""An add-on: the battle's target pick stops the clock and the battle message window asks 「对谁使用？」.

How a command is entered. ov16:198E runs the command input as a state machine in [2ED6]: 0 takes a member waiting
for a command (07B1:05FA), 1 is the command menu (ov16:10A2), 2 the skill or item menu (ov16:3F6E), 3 the target
(ov16:1A8C: ov16:2A90 every frame, mode 3 for an enemy, 4 / 5 / 6 for skills whose target flags are 11h / 10h /
30h; it returns -1 for a cancel and 1 or more once a target is clicked; skills that hit everyone or the user go
on to state 4 without it), 4 the command given. The battle clock moves only on a frame whose tick flag [97D2] is
set (0871:7306 from 25CA:89AA, once a main-loop pass; the enemies' countdowns ov32:03C4, the party's 358E:47D4).
States 1 and 2 clear the flag on every frame, so the menus stop the clock; state 3 clears it only when the
skill's target flags [bp-2] are nonzero (ov16:1C18 `cmp word [bp-2],0 / je 1C24`): a pick among the party stops
it, a pick among the enemies - every sword and gun attack, every attack skill - lets it run, and nothing on the
screen says a target is wanted.

A battle message is a script record put up by 25CA:88DC(file, record, count): it runs the record of file
「ms%.4x.bin」 into the message window [1BBA] and returns at once; [1BBC] is how many main-loop passes the window
then stays (a count below 1 gives 15), counted down by 25CA:8850, and the next message writes over it.

The add-on, in DDS98.EXE (six sites) and a file of its own:

  ov16:1C18  `cmp word [bp-2],0 / je 1C24` -> `mov word [1BBC],15`: the flag is cleared on every frame of a pick
             (the `mov word [97D2],0` after it now always runs), and the message window's count is kept full,
             so the question stays up until the target is picked
  ov16:2A9D  the pick's first call (358E:5236, the member's unit) goes to 358E:411C, which on a pick's first
             frame puts record 0 of MS00D9.BIN up - 25CA:88DC(D9h, 0, -1), reached with a far return because
             25CA is CS - 0FC4h - and then goes on to 5236
  ov16:19F2  states 1 and 2's call of 358E:5236 goes to 358E:413F, which clears the shown flag and goes on to
  ov16:1A52  5236, so the next pick asks again
  358E:411C-4147  the two entries, in two status wrappers nothing can enter
  358E:415E  the shown flag, the first byte of a third such wrapper, cleared (no near branch lands in
             358E:411C-41B5, no far call or relocation names it, and none of 411C, 4132, 415E occurs as a word
             anywhere in the file); the flag lives in the program's own segment, so the add-on needs no other
             patch
  MS00D9.BIN a file the game does not have: one chunk, record 0 the question and a line end (in the build's
             Chinese, the Japanese game's encoding, or the English translation's), so no file the game, a
             translation or an option of the patch page writes changes. Not E0h or above: 1603:857E takes file numbers
             E0h-FFh as the slots of the negotiation pack in use, never as files

Only the call sites' offsets change, so ov16's relocations still give 358E its segment; no relocation falls inside
a site. A pick after a cancel asks again (the menus clear the flag); a picked target's action line writes over the
question; a cancel leaves the window to close after its count. The user (2026-10-13): every command that waits for
a target, one wording, an add-on the patch page offers (not built in), and an English patch of its own.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NAME = "选择对象时暂停"
FILE = "DDS98.EXE"
DIR = "DDS98"
HDR = 0x3800                            # DDS98.EXE's header: file offset = HDR + segment * 16 + offset
SEG = 0x358E
MSG_NO, RECORD = 0xD9, 0x00
MSG_FILE = f"MS{MSG_NO:04X}.BIN"        # the game's 「ms%.4x.bin」
CAVE = 0x411C                           # 358E:411C-4147
CLEAR = CAVE + 0x23                     # 413F: the menus' entry
GO = CAVE + 0x29                        # 4145: on to 5236
FLAG = 0x415E                           # 358E:415E
UNIT = 0x5236                           # 358E:5236, the member's unit
SHOW = 0x88DC                           # 25CA:88DC
TEXTS = {"zh": "对谁使用？", "jp": "誰に使いますか？", "en": "Use on whom?"}
CHARS = set(TEXTS["zh"])

CAVE_ORIG = bytes.fromhex(
    "558becff7608ff76066a0f6a20900ee81affc9ca0400"      # 411C: a status wrapper (4048 with 0F, 20)
    "558becff7608ff76066a156a06900ee804ffc9ca0400")     # 4132: another (4048 with 15, 06)


def cave_code():
    flag = struct.pack("<H", FLAG)
    c = bytearray()
    c += b"\x2e\x80\x3e" + flag + b"\x00"                                   # cmp byte cs:[flag], 0
    c += bytes([0x75, GO - (CAVE + len(c) + 2)])                            # jne go
    c += b"\x2e\xc6\x06" + flag + b"\x01"                                   # mov byte cs:[flag], 1
    c += b"\x68" + struct.pack("<H", MSG_NO) + bytes([0x6A, RECORD]) + b"\x6a\xff"  # push D9h / 0 / -1
    c += b"\x0e" + b"\x68" + struct.pack("<H", GO)                          # push cs / push go: the return
    c += b"\x8c\xc8" + b"\x2d" + struct.pack("<H", SEG - 0x25CA)            # mov ax,cs / sub ax,0FC4h
    c += b"\x50" + b"\x68" + struct.pack("<H", SHOW) + b"\xcb"             # push ax / push 88DCh / retf
    assert CAVE + len(c) == CLEAR
    c += b"\x2e\xc6\x06" + flag + b"\x00"                                   # clear: mov byte cs:[flag], 0
    assert CAVE + len(c) == GO
    c += b"\xe9" + struct.pack("<h", UNIT - (GO + 3))                       # go: jmp 5236
    assert len(c) == len(CAVE_ORIG)
    return bytes(c)


def far_to(off):
    return b"\x9a" + struct.pack("<H", off) + struct.pack("<H", SEG)


# (where, offset, original, fixed, why); where "ov16" is an offset in overlay 16's image
SITES = [
    ("ov16", 0x1C18, bytes.fromhex("837efe007406"), bytes.fromhex("c706bc1b0f00"),
     "选对象的每一帧都停表（原来只在对我方时停），并让消息窗口一直开着"),
    ("ov16", 0x2A9D, far_to(UNIT), far_to(CAVE), "选对象的第一帧显示「对谁使用？」"),
    ("ov16", 0x19F2, far_to(UNIT), far_to(CLEAR), "指令菜单：下次选对象再显示"),
    ("ov16", 0x1A52, far_to(UNIT), far_to(CLEAR), "技能 / 道具菜单：下次选对象再显示"),
    ("main", SEG * 16 + CAVE, CAVE_ORIG, cave_code(), "358E:411C 的两个入口"),
    ("main", SEG * 16 + FLAG, b"\x55", b"\x00", "358E:415E 的标志"),
]


class TargetPromptError(ValueError):
    pass


def ov_offset(blob, number=16):
    """File offset of overlay `number`'s image (MS LINK overlays: MZ chunks after the main image)."""
    cblp, cp = struct.unpack_from("<HH", blob, 2)
    pos = (((cp - 1) * 512 + (cblp or 512)) + 511) & ~511
    while pos + 0x20 < len(blob):
        if blob[pos:pos + 2] == b"MZ":
            o_cblp, o_cp, _crlc, o_par = struct.unpack_from("<4H", blob, pos + 2)
            if struct.unpack_from("<H", blob, pos + 0x1A)[0] == number:
                return pos + o_par * 16
            pos = (pos + (o_cp - 1) * 512 + (o_cblp or 512) + 511) & ~511
        else:
            pos += 512
    raise TargetPromptError(f"{FILE} 里找不到覆盖段 {number}")


def where(blob, kind, off):
    return (ov_offset(blob) if kind == "ov16" else HDR) + off


def sites(blob):
    """[(file offset, original, fixed)] in this program."""
    return [(where(blob, kind, off), orig, fixed) for kind, off, orig, fixed, _why in SITES]


def state(blob):
    """'orig' or 'fixed' - every site in the same form, else TargetPromptError."""
    forms = set()
    for at, orig, fixed in sites(blob):
        now = bytes(blob[at:at + len(orig)])
        if now == orig:
            forms.add("orig")
        elif now == fixed:
            forms.add("fixed")
        else:
            raise TargetPromptError(f"{FILE} 第 {at:#x} 字节起既不是原版也不是本项改动后的内容")
    if len(forms) != 1:
        raise TargetPromptError(f"{FILE} 里本项的各处改动不一致（有的打了，有的没打）")
    return forms.pop()


def apply_to(blob, revert=False):
    """DDS98.EXE with the change in (or out)."""
    state(blob)
    out = bytearray(blob)
    for at, orig, fixed in sites(blob):
        out[at:at + len(orig)] = orig if revert else fixed
    return bytes(out)


def payload(charmap=None, english=False):
    """Record 0: the question and a line end. charmap: a Chinese build's; None for the game's own encoding (the
    Japanese text, or the English with english)."""
    if english:
        return TEXTS["en"].encode("ascii") + b"\x0a\x00"
    if charmap is None:
        return TEXTS["jp"].encode("cp932") + b"\x0a\x00"
    from textbuild import encode_unit
    return encode_unit(TEXTS["zh"] + "\n", charmap) + b"\x00"


def message_file(charmap=None, english=False):
    """MS00D9.BIN: one chunk holding record 0."""
    import ddsfile
    return ddsfile.build([[ddsfile.Record(RECORD, None, payload(charmap, english))]])


# ---- on an image's files (tools/addons.py): the program's sites and the message file, in or out together
def read(fs, path):
    e = fs.find(path)
    return None if e is None else bytes(fs.read_chain(e["cluster"], e["size"]))


def installed(fs):
    """Whether the image has the add-on: the program's sites and MS00D9.BIN agree, else TargetPromptError."""
    exe = read(fs, f"{DIR}/{FILE}")
    if exe is None:
        raise TargetPromptError(f"镜像里没有 {DIR}\\{FILE}，这不是本作的镜像")
    form = state(exe)
    have = fs.find(f"{DIR}/{MSG_FILE}") is not None
    if (form == "fixed") != have:
        raise TargetPromptError(f"镜像里{NAME}只打了一半（{FILE} 和 {MSG_FILE} 对不上）")
    return have


def install(fs, msg):
    """The add-on into an image without it: the program's sites, and msg as MS00D9.BIN."""
    if installed(fs):
        raise TargetPromptError(f"镜像里已经有{NAME}")
    fs.replace(f"{DIR}/{FILE}", apply_to(read(fs, f"{DIR}/{FILE}")))
    fs.create(DIR, MSG_FILE, msg)


def remove(fs):
    """The add-on out of an image that has it."""
    if not installed(fs):
        raise TargetPromptError(f"镜像里没有{NAME}")
    fs.replace(f"{DIR}/{FILE}", apply_to(read(fs, f"{DIR}/{FILE}"), revert=True))
    fs.remove(f"{DIR}/{MSG_FILE}")
