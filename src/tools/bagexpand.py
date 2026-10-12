#!/usr/bin/env python3
"""The item bag from 48 slots to 111.

The bag is DS:866E, 64 entries of 4 bytes: a word with the item number in its low 11 bits (7FFh = empty) and a
fitted gem's number in the top 5, a count byte, and a byte whose bit 7 marks a fitted gem. Slots 0-47 take every
ordinary item (the add loop 25CA:D7F8 stops at 30h); slots 48-63 are kept for the 恋人の部位 (kind 10, 25CA:D716;
an overflow there is the fatal 「シナリオアイテムバッファが一杯です」). Swords, guns and armour take a slot each, so
48 slots fill up; then every item gained opens 25CA:F50A, which makes the player throw a whole slot away. Gems sit
in their own table (DS:886E, 16) and are not touched here.

The new bag has 127 entries: slots 0-110 ordinary, 111-126 the 恋人の部位. It lives at DS:9B50 in room the MZ
header's SP makes: the C start-up puts the stack at SP + 9B4Eh (DS:9B50 = _end, the stack's bottom) and starts the
near heap right above the stack's top, so a larger SP (1000h -> 1700h, minalloc 440h -> 4B0h) moves the stack and
the heap up by 700h and leaves DS:9B50-A24F free. The stack keeps its size, so a call chain that fitted before
stays above DS:A150 (the two list frames below grow by 7Eh each); the near heap's room shrinks by 700h. The free
room holds:

    9B50  the bag, 127 x 4
    9D4C  slots 48-110 of the bag copy command 2E6 (＠所持アイテム移動) keeps, 63 x 4 (see below)
    9E48  ov12's list of slots with equippable items, 111 words (was DS:8054, 48 words)
    9F26  ov12's list of single items with their counts, 111 x 4 (was DS:80B4, 48 x 4)

Every address of the old bag moves (the module 25CA:CE00-DF00 is the only code that touches it, apart from the
new-game init ov08:1474), and every bound moves with it: 30h (the ordinary slots) to 6Fh, 2Fh to 6Eh, 40h (all)
to 7Fh, 3Fh to 7Eh, the scenario part's start 872Eh to 9D0Ch. Outside the module the bounds and buffers of the
callers that walk the bag by slot number follow: the shop's sell list (ov01:0416, D86E over 30h slots), the field
item list (ov11:0000 and 25CA:F260, D86E over 40h), the discard list (25CA:F50A, 40h words on its stack), command
2F1 ＠アイテム配列確保 (1603:D934, 40h words on its stack) and ov12's two equipment lists.

Saves: the original writes the bag as one block of 64 entries (25CA:DBE4 / DC04, at file offset 444h, between
07B1:081C's section and the gem table's, 25CA:DE24). That block keeps its place and its form - slots 0-47 and then the 16 scenario slots - so the original game
still loads a new save (it only loses slots 48-110), and slots 48-110 go to the end of the file, after the last
section (358E:9E6C / 9EC4): ov03's two calls of those are pointed at entries here that call them and then write
or read the 63 entries. A save without that tail (one the original made) leaves slots 48-110 empty. The original
loader checks only the version byte and reads the sections in order, so trailing bytes do not disturb it.

Command 2E6 (MS0016 r12/r13, MS005F r06, MS0062 r06, MS006C r0A: the party's items are taken and given back) copies
the bag and the gem table into the script variables at 4827:08E6 (saved with them, 1603:8326); index 17h puts the
bag at 4827:0982, 64 entries. Its routine 25CA:D96E now copies slots 0-47 and the scenario slots there as before and
slots 48-110 to DS:9D4C, and back the same way; DS:9D4C goes to the end of a save as well.

New code goes where nothing calls: 25CA:D270 (first free slot of a part), 25CA:D322 (count in the slot holding an
item), 25CA:D6C8 (move a slot to the front) - no call, jump or pointer reaches any of them - and the dead parts of
25CA:DBE4 / DC04 after their new entries. Far calls go through words the loader already relocates: the fwrite and
fread calls left in place at 25CA:DBF5 / DC15 serve as far pointers, and 25CA:F555's call of 358E:0BFE gives 358E's
segment. No relocation is added.
"""
import os
import struct
import sys

import capstone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm86 import assemble  # noqa: E402
import mz  # noqa: E402

NAME = "道具栏扩容"
FILE = "DDS98.EXE"
HDR = 0x3800                            # DDS98.EXE's header: file offset = HDR + segment * 16 + offset
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98", FILE)
SEG25, SEG16 = 0x25CA, 0x1603

# The room the larger SP leaves at the stack's old bottom (DGROUP offsets)
RESERVE = 0x700
SP_ORIG, SP_NEW = 0x1000, 0x1000 + RESERVE
MINALLOC_ORIG, MINALLOC_NEW = 0x440, 0x4B0
BAG = 0x9B50
NORMAL, TOTAL = 111, 127
SCEN = BAG + 4 * NORMAL                 # 9D0C, slot 111: the 恋人の部位
END = BAG + 4 * TOTAL                   # 9D4C
OLD_NORMAL = 48
BAG_EXT = BAG + 4 * OLD_NORMAL          # 9C10, slot 48: what the original's 64 entries have no room for
EXT_N = NORMAL - OLD_NORMAL             # 63
EXTBK = END                             # 9D4C: command 2E6's copy of slots 48-110
EXTBK_END = EXTBK + 4 * EXT_N           # 9E48
LIST1 = EXTBK_END                       # 9E48: ov12's equippable slots, a word each
LIST2 = LIST1 + 2 * NORMAL              # 9F26: ov12's single items, slot and count
SPACE_END = LIST2 + 4 * NORMAL          # A0E2
FRAME_GROWTH = 2 * (TOTAL - 64)         # 7Eh: F50A's and 1603:D934's word lists on the stack

# relocated far pointers and words in 25CA (left in place)
FWRITE = 0xDBF6                         # DBF5 lcall 0000:0570, fwrite
FREAD = 0xDC16                          # DC15 lcall 0000:03FC, fread
SEG358 = 0xF558                         # F555 lcall 358E:0BFE: 358E's segment
SAVE_LAST, LOAD_LAST = 0x9E6C, 0x9EC4   # 358E: the last section of a save, written / read

# the old bag's addresses and slot counts, and what they become
A_MAP = {0x866E: BAG, 0x866F: BAG + 1, 0x8670: BAG + 2, 0x8671: BAG + 3,
         0x872A: SCEN - 4, 0x872E: SCEN, 0x876A: END - 4, 0x876E: END, 0x8770: END + 2}
COUNT_MAP = {0x2F: NORMAL - 1, 0x30: NORMAL, 0x3F: TOTAL - 1, 0x40: TOTAL}

# 25CA: every instruction of the module that names the old bag or one of its slot counts
MODULE = (
    0xD128,                                                     # D116 (command 21C): D86E's count
    0xD256, 0xD260,                                             # D24C: slot -> pointer
    0xD2CF, 0xD2D2, 0xD2E8, 0xD2F4, 0xD2F7, 0xD30D,             # D2C2: last slot holding an item, by part
    0xD352, 0xD36E,                                             # D34C: count of an item
    0xD38D, 0xD397, 0xD3AA, 0xD3B3, 0xD3B7, 0xD3C1, 0xD3C6, 0xD3CE,     # D37A: set a slot
    0xD3ED,                                                     # D3DA: add to a slot's count
    0xD425,                                                     # D414: take from a slot's count
    0xD462,                                                     # D458: add to a slot
    0xD4D3, 0xD535, 0xD540, 0xD58F, 0xD59A, 0xD5AD, 0xD5B7, 0xD5CC, 0xD5DF,
    0xD605, 0xD609, 0xD612, 0xD618, 0xD61D, 0xD629, 0xD632, 0xD681,       # D4AE: merge, pack, scenario part
    0xD691, 0xD694, 0xD6B8,                                     # D68C: take an item, last slot first
    0xD727, 0xD72A, 0xD75B,                                     # D716: add a 恋人の部位
    0xD78D, 0xD7A5, 0xD7B9,                                     # D784 / D79C / D7AE: a slot's item, address, count
    0xD7C8, 0xD7D2, 0xD7E4,                                     # D7C2: next used slot
    0xD83E,                                                     # D7F8: add an item, ordinary slots
    0xD852, 0xD863,                                             # D84C: used slots
    0xD89E, 0xD8A3, 0xD8C2,                                     # D86E: list of the used slots
    0xD938,                                                     # D914: a list back into the bag
    0xDA05, 0xDA1B, 0xDA25, 0xDA37, 0xDA45, 0xDA49, 0xDA5D, 0xDA69,     # D9F8: pack the ordinary slots
    0xDA7F,                                                     # DA74: take from a slot
    0xDAC8, 0xDADD, 0xDB09,                                     # DAA6: a slot as an equipment word
    0xDB22, 0xDB38,                                             # DB16: a slot's gem
    0xDB5F, 0xDB64,                                             # DB46: take a slot's gem out
    0xDB92, 0xDB9B, 0xDB9F,                                     # DB72: fit a gem
    0xDBB5,                                                     # DBAC: a slot's byte 3
    0xDBC9, 0xDBDB,                                             # DBC0: set it
)

# outside the module: (where, offset, {old operand value: new}, why)
OUTSIDE = (
    ("25CA", 0xF268, {0x40: TOTAL}, "25CA:F260 的道具列表窗口：D86E 取全部格子"),
    ("25CA", 0xF548, {0x40: TOTAL}, "25CA:F50A 背包满时的丢弃列表：逐格检查到最后一格"),
    ("1603", 0xD9D4, {0x40: TOTAL}, "命令 2F1 ＠アイテム配列確保（1603:D934）：逐格检查到最后一格"),
    ("ov01", 0x0438, {0x30: NORMAL}, "商店卖出列表（ov01:0416）：取全部普通格"),
    ("ov01", 0x0451, {0x30: NORMAL}, "商店卖出列表（ov01:0416）：取全部普通格"),
    ("ov08", 0x1474, {0x8670: BAG + 2}, "新游戏清空背包（ov08:1474）：新背包"),
    ("ov08", 0x1487, {0x8770: END + 2}, "新游戏清空背包（ov08:1474）：清到最后一格"),
    ("ov11", 0x008B, {0x40: TOTAL}, "野外道具菜单（ov11:0000）：D86E 取全部格子"),
    ("ov12", 0x0713, {0x8054: LIST1}, "装备菜单：可装备道具的格子列表移到新空间"),
    ("ov12", 0x0786, {0x8054: LIST1}, "装备菜单：可装备道具的格子列表移到新空间"),
    ("ov12", 0x07EF, {0x30: NORMAL}, "装备菜单：可装备道具逐格检查到最后一个普通格"),
    ("ov12", 0x08C1, {0x8054: LIST1}, "装备菜单：可装备道具的格子列表移到新空间"),
    ("ov12", 0x1389, {0x80B4: LIST2}, "装备菜单：单件道具列表移到新空间"),
    ("ov12", 0x14E8, {0x80B4: LIST2}, "装备菜单：单件道具列表移到新空间"),
    ("ov12", 0x1520, {0x30: NORMAL}, "装备菜单：单件道具逐格检查到最后一个普通格"),
    ("ov12", 0x1570, {0x80B6: LIST2 + 2}, "装备菜单：单件道具列表移到新空间"),
    ("ov12", 0x1574, {0x80B4: LIST2}, "装备菜单：单件道具列表移到新空间"),
    ("ov12", 0x1585, {0x80B4: LIST2}, "装备菜单：单件道具列表移到新空间"),
    ("ov12", 0x15BE, {0x80B4: LIST2}, "装备菜单：单件道具列表移到新空间"),
)

# the two word lists on the stack: (where, offset, the frame's size before, after) for enter / lea / push
FRAMES = (
    ("25CA", 0xF50A, 0x86), ("25CA", 0xF515, 0x86), ("25CA", 0xF56C, 0x86), ("25CA", 0xF5CA, 0x86),
    ("1603", 0xD934, 0x9A), ("1603", 0xD95E, 0x9A), ("1603", 0xDA20, 0x9A),
)

CAP = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
CAP.detail = True


class BagError(ValueError):
    pass


def _original():
    return open(SRC, "rb").read()


_OVS = mz.overlays(SRC)


def _file(where, off):
    if where.startswith("ov"):
        ov = _OVS[int(where[2:])]
        return ov.file_off + ov.hdr + off
    return HDR + int(where, 16) * 16 + off


def _decode(blob, at):
    ins = next(CAP.disasm(bytes(blob[at:at + 15]), 0), None)
    if ins is None:
        raise BagError(f"{at:#x} 处解码失败")
    return ins


def _subst(blob, at, vmap, where):
    """The instruction at file offset at with its immediate / displacement values in vmap replaced: (old, new)."""
    ins = _decode(blob, at)
    old = bytes(ins.bytes)
    new = bytearray(old)
    done = 0
    for off_name, size_name in (("imm_offset", "imm_size"), ("disp_offset", "disp_size")):
        o, n = getattr(ins, off_name), getattr(ins, size_name)
        if not n:
            continue
        raw = int.from_bytes(old[o:o + n], "little")
        if raw in vmap:
            v = vmap[raw]
            if n == 1 and not (0 <= v <= 0x7F):
                raise BagError(f"{where} 的单字节操作数放不下 {v:#x}")
            new[o:o + n] = v.to_bytes(n, "little")
            done += 1
    if done != 1:
        raise BagError(f"{where}（{ins.mnemonic} {ins.op_str}）应恰有一个操作数要改，实际 {done} 个")
    return old, bytes(new)


def _frame(blob, at, before, where):
    """enter (size before -> + FRAME_GROWTH) or lea / push with the list's displacement -before."""
    ins = _decode(blob, at)
    old = bytes(ins.bytes)
    after = before + FRAME_GROWTH
    if ins.mnemonic == "enter":
        if old != bytes([0xC8]) + before.to_bytes(2, "little") + b"\x00":
            raise BagError(f"{where} 不是 enter {before:#x}, 0")
        return old, bytes([0xC8]) + after.to_bytes(2, "little") + b"\x00"
    o, n = ins.disp_offset, ins.disp_size
    if n != 2 or int.from_bytes(old[o:o + 2], "little", signed=True) != -before:
        raise BagError(f"{where}（{ins.mnemonic} {ins.op_str}）的位移不是 -{before:#x}")
    new = bytearray(old)
    new[o:o + 2] = (-after).to_bytes(2, "little", signed=True)
    return old, bytes(new)


# ---- new code ------------------------------------------------------------------------------------------------------

STORE_AT, RESTORE_AT, COPY_DONE = 0xD992, 0xD9BC, 0xD9EC     # inside D96E; D96E-D991 and D9EC- stay
STORE = f"""
    mov word ptr [bp + 8], si       ; the copy (allocated above when none was given)
    mov es, word ptr [bp + 0xa]
    mov di, si
    mov si, {BAG:#x}
    mov cx, {OLD_NORMAL * 2:#x}
    cld
    rep movsw                       ; slots 0-47
    mov si, {SCEN:#x}
    mov cx, {16 * 2:#x}
    rep movsw                       ; the 恋人の部位: the copy is the original's 64 entries
    push ds
    pop es
    mov si, {BAG_EXT:#x}
    mov di, {EXTBK:#x}
    mov cx, {EXT_N * 2:#x}
    rep movsw                       ; slots 48-110 to DS:9D4C
    jmp {COPY_DONE:#x}
"""
RESTORE = f"""
    mov si, word ptr [bp + 8]
    mov ax, word ptr [bp + 0xa]
    or ax, si
    je {COPY_DONE:#x}
    push ds
    pop es
    mov di, {BAG:#x}
    mov cx, {OLD_NORMAL * 2:#x}
    cld
    push ds
    mov ds, word ptr [bp + 0xa]
    rep movsw                       ; slots 0-47
    mov di, {SCEN:#x}
    mov cx, {16 * 2:#x}
    rep movsw                       ; the 恋人の部位
    pop ds
    mov si, {EXTBK:#x}
    mov di, {BAG_EXT:#x}
    mov cx, {EXT_N * 2:#x}
    rep movsw                       ; slots 48-110 from DS:9D4C
"""

CAVE_EXT, CAVE_EXT_END = 0xD6C8, 0xD716       # ext_common, xfer
CAVE_BAG, CAVE_BAG_END = 0xD270, 0xD2C2       # bag_io, clear
CAVE_BLK, CAVE_BLK_END = 0xD322, 0xD34C       # ext_block
EXT_SRC = f"""
ext_common:                         ; ax = the last section's routine in 358E, dx = FWRITE / FREAD
    push bp
    mov bp, sp
    push si
    push di
    mov di, dx
    push word ptr [bp + 8]
    push word ptr [bp + 6]
    push cs
    push ext_back
    push word ptr cs:[{SEG358:#x}]
    push ax
    retf                            ; 358E:9E6C / 9EC4 (FILE far *) as before; it returns here
ext_back:
    mov si, ax
    mov ax, {BAG_EXT:#x}
    mov dx, {SCEN:#x}
    call {CAVE_BLK:#x}              ; slots 48-110
    mov ax, {EXTBK:#x}
    mov dx, {EXTBK_END:#x}
    call {CAVE_BLK:#x}              ; command 2E6's copy of them
    mov ax, si
    pop di
    pop si
    leave
    retf 4
xfer:                               ; bx = FWRITE / FREAD, ax = DS address, cx = entries; the caller's [bp+6] = FILE
    push word ptr [bp + 8]
    push word ptr [bp + 6]
    push cx
    push 4
    push ds
    push ax
    lcall cs:[bx]
    add sp, 0xc
    ret
"""


def _bag_src(xfer):
    return f"""
bag_io:                             ; bx = FWRITE / FREAD: the original's 64 entries, in its place in the file
    push bp
    mov bp, sp
    push si
    push bx
    mov ax, {BAG:#x}
    mov cx, {OLD_NORMAL:#x}
    call {xfer:#x}
    mov si, ax
    pop bx
    push bx
    mov ax, {SCEN:#x}
    mov cx, 16
    call {xfer:#x}
    add si, ax
    pop bx
    cmp bx, {FREAD:#x}
    jne bag_io_done
    mov bx, {BAG_EXT:#x}
    mov dx, {SCEN:#x}
    call clear                      ; slots 48-110 come from the file's end, or stay empty
bag_io_done:
    mov ax, 64
    sub ax, si
    pop si
    leave
    retf 4
clear:                              ; bx = first entry, dx = end: every entry empty
    mov word ptr [bx], 0x7ff
    mov word ptr [bx + 2], 0
    add bx, 4
    cmp bx, dx
    jb clear
    ret
"""


def _blk_src(xfer, clear):
    return f"""
ext_block:                          ; ax = first entry, dx = end (63 entries); di = FWRITE / FREAD; si = the result
    push ax
    push dx
    mov bx, di
    mov cx, {EXT_N:#x}
    call {xfer:#x}
    pop dx
    pop bx
    cmp ax, {EXT_N:#x}
    je ext_block_done
    cmp di, {FWRITE:#x}
    je ext_block_err
    jmp near {clear:#x}             ; a save without the tail (an older one): the block stays empty
ext_block_err:
    or si, 1                        ; a short write, reported like the other sections'
ext_block_done:
    ret
"""


ENTRIES = (                             # 25CA: the entries ov03 calls, with the far pointers' bytes after them kept
    (0xDBE4, 0xDBF5, f"mov bx, {FWRITE:#x}\njmp near {CAVE_BAG:#x}", "存档写背包（ov03 调用 DBE4）"),
    (0xDBFA, 0xDC04, f"mov ax, {SAVE_LAST:#x}\nmov dx, {FWRITE:#x}\njmp near {CAVE_EXT:#x}", "存档最后一节之后写扩展格"),
    (0xDC04, 0xDC15, f"mov bx, {FREAD:#x}\njmp near {CAVE_BAG:#x}", "读档读背包（ov03 调用 DC04）"),
    (0xDC1A, 0xDC24, f"mov ax, {LOAD_LAST:#x}\nmov dx, {FREAD:#x}\njmp near {CAVE_EXT:#x}", "读档最后一节之后读扩展格"),
)
OV03_CALLS = (                          # ov03: the calls of the last section, through the entries above
    (0x0A2C, SAVE_LAST, 0xDBFA, "存档：最后一节（358E:9E6C）改由 25CA:DBFA 调用，再写扩展格"),
    (0x0B29, LOAD_LAST, 0xDC1A, "读档：最后一节（358E:9EC4）改由 25CA:DC1A 调用，再读扩展格"),
)


def _asm(src, org, end, what):
    code, labels = assemble(src, org=org)
    if org + len(code) > end:
        raise BagError(f"{what} {len(code)} 字节，超出了 {org:#x}-{end - 1:#x}")
    return code, labels


def _code_sites(orig):
    ext, lab_e = _asm(EXT_SRC, CAVE_EXT, CAVE_EXT_END, "扩展格例程")
    if lab_e["ext_common"] != CAVE_EXT:
        raise BagError("ext_common 不在洞口")
    bag, lab_b = _asm(_bag_src(lab_e["xfer"]), CAVE_BAG, CAVE_BAG_END, "背包读写例程")
    blk, _ = _asm(_blk_src(lab_e["xfer"], lab_b["clear"]), CAVE_BLK, CAVE_BLK_END, "扩展块例程")
    store, _ = _asm(STORE, STORE_AT, RESTORE_AT, "命令 2E6 的保存")
    restore, _ = _asm(RESTORE, RESTORE_AT, COPY_DONE, "命令 2E6 的恢复")
    blocks = [(CAVE_EXT, ext, CAVE_EXT_END, "新例程：扩展格的写读（放在没有入口的 25CA:D6C8）"),
              (CAVE_BAG, bag, CAVE_BAG_END, "新例程：原位置的 64 格写读（放在没有入口的 25CA:D270）"),
              (CAVE_BLK, blk, CAVE_BLK_END, "新例程：扩展块（放在没有入口的 25CA:D322）"),
              (STORE_AT, store, RESTORE_AT, "命令 2E6 保存背包：原 64 格照旧，48-110 格存到 DS:9D4C"),
              (RESTORE_AT, restore, COPY_DONE, "命令 2E6 恢复背包：原 64 格照旧，48-110 格从 DS:9D4C 取回")]
    for at, stop, src, why in ENTRIES:
        code, _ = _asm(src, at, stop, why)
        blocks.append((at, code, at + len(code), why))
    out = []
    for at, code, stop, why in blocks:
        fo = HDR + SEG25 * 16 + at
        n = len(code) if stop - at < len(code) else stop - at
        pad = code + b"\x90" * (n - len(code))
        out.append((why, fo, orig[fo:fo + n], pad))
    for at, last, entry, why in OV03_CALLS:
        fo = _file("ov03", at)
        old = bytes([0x9A]) + last.to_bytes(2, "little") + (0x358E).to_bytes(2, "little")
        if orig[fo:fo + 5] != old:
            raise BagError(f"ov03:{at:04X} 不是 lcall 358E:{last:04X}")
        out.append((why, fo, old, bytes([0x9A]) + entry.to_bytes(2, "little") + SEG25.to_bytes(2, "little")))
    return out


def _check_relocations():
    m = mz.MZ(SRC)
    for word, what in ((FWRITE + 2, "fwrite"), (FREAD + 2, "fread"), (SEG358, "358E")):
        if SEG25 * 16 + word not in m.reloc_set:
            raise BagError(f"25CA:{word:04X}（{what} 的段）不在重定位表里")
    ov3 = _OVS[3]
    for at, _last, _entry, _why in OV03_CALLS:
        if at + 3 not in ov3.relocs:
            raise BagError(f"ov03:{at + 3:04X} 不在覆盖段的重定位表里")


def _sites():
    orig = _original()
    sites = []
    for off in MODULE:
        fo = HDR + SEG25 * 16 + off
        old, new = _subst(orig, fo, {**A_MAP, **COUNT_MAP} if off in _COUNT_SITES else A_MAP, f"25CA:{off:04X}")
        sites.append((f"背包模块 25CA:{off:04X}", fo, old, new))
    for where, off, vmap, why in OUTSIDE:
        fo = _file(where, off)
        old, new = _subst(orig, fo, vmap, f"{where}:{off:04X}")
        sites.append((why, fo, old, new))
    for where, off, before in FRAMES:
        fo = _file(where, off)
        old, new = _frame(orig, fo, before, f"{where}:{off:04X}")
        sites.append((f"{where}:{off:04X} 栈上的格号列表放得下 {TOTAL} 项", fo, old, new))
    sites += _code_sites(orig)
    sites.append(("MZ 头：minalloc（栈和近堆上移后的内存）", 0x0A, struct.pack("<H", MINALLOC_ORIG),
                  struct.pack("<H", MINALLOC_NEW)))
    sites.append(("MZ 头：SP（栈和近堆上移 700h，空出 DS:9B50 起的新空间）", 0x10, struct.pack("<H", SP_ORIG),
                  struct.pack("<H", SP_NEW)))
    sites.sort(key=lambda s: s[1])
    for (_, a, x, _y), (_, b, _x2, _y2) in zip(sites, sites[1:]):
        if a + len(x) > b:
            raise BagError(f"改动 {a:#x} 与 {b:#x} 重叠")
    for why, fo, old, new in sites:
        if orig[fo:fo + len(old)] != old or len(old) != len(new):
            raise BagError(f"{why}：原字节或长度不对")
    return sites


# the module sites whose small immediate is a slot count (the rest name addresses only)
_COUNT_SITES = {0xD128, 0xD256, 0xD2CF, 0xD2F4, 0xD5AD, 0xD691, 0xD727, 0xD7C8, 0xD83E, 0xD89E, 0xD8A3, 0xDA1B,
                0xDA5D}
if SPACE_END > BAG + RESERVE - FRAME_GROWTH:
    raise BagError("新空间放不下")
_check_relocations()
SITES = _sites()


def state(blob):
    """'orig' or 'fixed' - every site has to be in the same one."""
    seen = set()
    for why, fo, old, new in SITES:
        now = bytes(blob[fo:fo + len(old)])
        if now == old:
            seen.add("orig")
        elif now == new:
            seen.add("fixed")
        else:
            raise BagError(f"{why}（{FILE} 第 {fo:#x} 字节起）既不是原版也不是扩容后的内容")
    if len(seen) != 1:
        raise BagError(f"{FILE} 只有一部分改成了扩容后的内容")
    return seen.pop()


def apply_to(blob, revert=False):
    """DDS98.EXE with the 111-slot bag (or the original 48 again)."""
    state(blob)
    out = bytearray(blob)
    for _why, fo, old, new in SITES:
        out[fo:fo + len(old)] = old if revert else new
    return bytes(out)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exe")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--list", action="store_true", help="print every site")
    a = ap.parse_args()
    blob = open(a.exe, "rb").read()
    try:
        before = state(blob)
        if a.list:
            for why, fo, old, new in SITES:
                print(f"{fo:#07x}  {old.hex(' '):<30} -> {new.hex(' '):<30} {why}")
            return 0
        out = apply_to(blob, a.revert)
    except BagError as e:
        raise SystemExit(f"{NAME}：{e}")
    open(a.exe, "wb").write(out)
    print(f"{a.exe}: {before} -> {state(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
