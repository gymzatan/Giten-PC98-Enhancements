#!/usr/bin/env python3
"""The game's virtual memory swaps through XMS instead of the file DDS98\\VM\\V0000.BUF.

DDS98 keeps its pictures, scripts and lists in a virtual memory of its own (0871, started by 0871:1AF2(7, 1100h,
FFFh) with its pages in XMS when the machine has it, [970C] set, the XMS block's size in KB at [9710] and the
driver's entry at [974C]). When an allocation or a lock fails, the callback 0871:7258 counts the failures of that
kind; from the fourth on it runs the recovery 0871:94C4, which defragments by way of a file:

    unlock every handle; fopen("vm\\v0000.buf", "wb"); for every handle in use: lock its block, fwrite it, free
    it; fclose; shut the memory down (0871:12FC) and start it afresh (0871:1AF2(7, 1100h, FFFh)); fopen(.., "rb");
    for every handle in use: allocate a block of its size (0871:5DAE), lock it, fread it back; fclose.

A failing step prints 「VM double fault(...)」 (fwopen, recover-r, dsk, init, fropen, recover-w, size) and ends
the program. The folder VM is made once, at start-up (0871:9144, mkdir "vm"); nothing else creates or removes it.
In a session started the normal way the swap finds it and works: ../Giten.hdi, the old Japanese install, holds a
747,894-byte V0000.BUF, and long sessions of both editions swap now and then (the Windows art sooner, its pictures
being larger). It fails when the running program's DOS no longer matches the disk: a DOSBox-X save state remounts
the image at the path it recorded and carries DOS's and SMARTDRV's disk caches with it, so a state loaded after a
fresh release image was unpacked over that path runs on a disk with no VM folder - the next swap ends the game with
「VM double fault(fwopen)」 (a tester's crash at the 惠比寿花园 elevator, reproduced exactly) - and the swap's
megabyte of writes goes through the old disk's directory and FAT.

The fix keeps the swap in XMS. The file part of 94C4, 956C-9753 (from the first fopen to the second fclose), is
written anew; the start (the unlocking, the caller's handle, the relock of [10D0]'s block) and the end at 9754
(the caller's pointer, the relock, [10D6]) stay as they are:

    if the memory keeps its pages in XMS ([970C]): allocate an XMS block of [9710] + 1 KB - the memory's own block
    holds every page, so every block fits -, else 「VM double fault(fwopen)」 as before. For every handle in use, in
    the same order as before: lock (recover-r on failure), move the block into the XMS block at the running
    position (XMS 0Bh; dsk on failure), free it. Shut down and start afresh (init on failure). For every handle in
    use: allocate, lock (recover-w), move the block back (size). Free the XMS block, go on at 9754.

A block's length goes to XMS rounded up to even (XMS moves even lengths): the allocator rounds every block up to
an even size before it adds its 6-byte header (0871:14E0, 1511-1517), so the extra byte is the block's own. An
empty block moves nothing. The XMS handle lives in [bp-2], which 94C4 never uses; the position in [bp-0Ah] /
[bp-8], the words that held the FILE pointer. 「fropen」 can no longer happen. All the messages go out through the
game's own printf / exit pair that printed 「fwopen」 (958D / 9597), which now takes the message in AX (958B:
push ds / push ax). The 20 relocated words in 956C-9753 keep their bytes and the code jumps over them, so the
relocation table is untouched; nothing outside 956C-9753 changes. The folder VM is still made at start-up but
nothing goes into it any more.

It goes into every build and the 汉化补丁 (which writes the whole program), with no switch; the Windows art
patch leaves it out, like ctxfree and bagexpand. tools/vmswap_test.py runs the original and the new recovery side by
side on an emulated CPU.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from asm86 import Asm  # noqa: E402
from mz import MZ  # noqa: E402

NAME = "换页改用内存"
FILE = "DDS98.EXE"
SRC = os.path.join(os.path.dirname(HERE), "files", "DDS98", FILE)
HDR = 0x3800                            # DDS98.EXE's header: file offset = HDR + segment * 16 + offset
SEG = 0x0871
START, END = 0x956C, 0x9754             # the file part of the recovery 94C4; 9754 is its unchanged end
ERR, ERR_END = 0x958B, 0x959F           # push ds / push ax, then the game's printf (958D) and exit (9597)
MSG = {"fwopen": 0x114F, "recover-r": 0x1168, "dsk": 0x1184, "init": 0x119A, "recover-w": 0x11CD,
       "size": 0x11E9}                  # DGROUP offsets of 「VM double fault(...)」
FILL = 0xCC

# 956C, where the first part of 94C4 goes on (9548, 955A), up to the error exit, which a_fwopen runs into: laid
# out by hand around the relocated word at 957A
SRC_A = f"""
    cmp byte ptr [0x970c], 0        ; the memory keeps its pages in XMS
    je a_fwopen
    mov dx, word ptr [0x9710]       ; its XMS block in KB, which holds every block
    inc dx
    jmp short a_alloc
    resb 2                          ; 957A, a relocated word
a_alloc:
    mov ah, 9                       ; XMS: allocate dx KB
    lcall [0x974c]
    dec ax
    jne a_fwopen
    jmp short main
    nop
a_fwopen:
    mov ax, {MSG['fwopen']:#x}
"""

# 959F, after the error exit, up to 9754
SRC_B = f"""
main:
    mov word ptr [bp - 2], dx       ; the XMS block's handle
    xor ax, ax
    mov word ptr [bp - 0xa], ax     ; the position in it
    mov word ptr [bp - 8], ax
    mov si, 1                       ; every handle, its size at [616A]:di
    mov di, 0xa
w_next:
    push si
    call 0x979a                     ; in use?
    or ax, ax
    je w_skip
    push si
    call 0x97d8
    push dx
    push ax
    push 0
    push cs
    call 0x1e0c                     ; lock
    mov word ptr [bp - 6], ax
    mov word ptr [bp - 4], dx
    or dx, ax
    jne w_locked
    mov ax, {MSG['recover-r']:#x}
    jmp err
w_locked:
    mov es, word ptr [0x616a]
    mov ax, word ptr es:[di]
    mov cl, 1
    call xmove                      ; out to XMS
    dec ax
    je w_moved
    mov ax, {MSG['dsk']:#x}
    jmp err
w_moved:
    push si
    call 0x97d8
    push dx
    push ax
    push cs
    call 0x5fc8                     ; free
w_skip:
    inc si
    add di, 8
    cmp di, 0x2002
    jb w_next
    push cs
    call 0x12fc                     ; shut down
    push 0xfff
    push 0x1100
    push 7
    push cs
    call 0x1af2                     ; and start afresh
    or ax, ax
    jne r_start
    mov ax, {MSG['init']:#x}
    jmp err
r_start:
    xor ax, ax
    mov word ptr [bp - 0xa], ax
    mov word ptr [bp - 8], ax
    mov di, 1                       ; every handle, its size at [616A]:si
    mov si, 0xa
r_next:
    push di
    call 0x979a                     ; in use?
    or ax, ax
    je r_skip
    mov es, word ptr [0x616a]
    push 0
    push word ptr es:[si]
    push cs
    call 0x5dae                     ; a block of its size
    mov es, word ptr [0x616a]
    mov word ptr es:[si + 2], ax
    mov word ptr es:[si + 4], dx
    push di
    call 0x97d8
    push dx
    push ax
    push 1
    push cs
    call 0x1e0c                     ; lock
    mov word ptr [bp - 6], ax
    mov word ptr [bp - 4], dx
    or dx, ax
    jne r_locked
    mov ax, {MSG['recover-w']:#x}
    jmp err
r_locked:
    mov es, word ptr [0x616a]
    mov ax, word ptr es:[si]
    mov cl, 0
    call xmove                      ; back from XMS
    dec ax
    je r_skip
    mov ax, {MSG['size']:#x}
    jmp err
r_skip:
    inc di
    add si, 8
    cmp si, 0x2002
    jb r_next
    mov dx, word ptr [bp - 2]
    mov ah, 0xa                     ; XMS: free the block
    lcall [0x974c]
    jmp tail
xmove:                              ; ax = the block's size, cl = 1 out / 0 back -> ax = 1 when moved
    push si
    inc ax
    and al, 0xfe
    xchg ax, bx                     ; the length, even
    mov ax, 1
    or bx, bx
    je xm_done
    or cl, cl
    je xm_back
    push word ptr [bp - 8]          ; to the XMS block at the position
    push word ptr [bp - 0xa]
    push word ptr [bp - 2]
    push word ptr [bp - 4]          ; from the locked block
    push word ptr [bp - 6]
    push 0
    jmp xm_go
xm_back:
    push word ptr [bp - 4]          ; to the locked block
    push word ptr [bp - 6]
    push 0
    push word ptr [bp - 8]          ; from the XMS block at the position
    push word ptr [bp - 0xa]
    push word ptr [bp - 2]
xm_go:
    push 0
    push bx
    add word ptr [bp - 0xa], bx
    adc word ptr [bp - 8], 0
    mov si, sp                      ; the move structure, on the stack
    push ds
    push ds
    pop es
    push ss
    pop ds
    mov ah, 0xb                     ; XMS: move
    lcall es:[0x974c]
    pop ds
    add sp, 0x10
xm_done:
    pop si
    ret
"""


class VmSwapError(ValueError):
    pass


def holes():
    """The relocated words in START..END of the original program (offsets in SEG)."""
    base = SEG * 16
    return sorted(p - base for p in MZ(SRC).reloc_set if base + START <= p < base + END)


def pack(source, start, end, gaps, consts):
    """Assemble `source` at `start` to fit [start, end) around `gaps` (relocated words, two bytes each, which keep
    their own bytes): a short jmp over each, put in ahead of the last statement that leaves room for it, unless the
    word already sits in a `resb`. -> (code, labels); the gaps' bytes in `code` are filler."""
    lines = source.strip("\n").split("\n")
    for k in range(len(gaps) + 1):
        a = Asm("\n".join(lines), start, consts)
        code = a.build()
        bad = None
        for n, (addr, blob, st) in enumerate(a.listing):
            if st.text.strip().startswith("resb"):
                continue
            if blob and any(addr < g + 2 and addr + len(blob) > g for g in gaps):
                bad = n
                break
        if bad is None:
            if start + len(code) > end:
                raise VmSwapError(f"{start:04X}-{end:04X}: {len(code)} bytes do not fit")
            return code, a.labels
        addr, _blob, _st = a.listing[bad]
        g = next(g for g in gaps if addr < g + 2 and addr + len(a.listing[bad][1]) > g)
        j = bad
        while a.listing[j][0] > g - 2:
            j -= 1
            if j < 0:
                raise VmSwapError(f"{g:04X}: no room for a jump ahead of the relocated word")
        at, _b, st_j = a.listing[j]
        line = st_j.line - 1
        while line > 0 and lines[line - 1].strip().endswith(":"):
            line -= 1
        lines[line:line] = [f"    jmp short __hop{k}", f"    resb {g + 2 - (at + 2)}", f"__hop{k}:"]
    raise VmSwapError(f"{start:04X}-{end:04X}: the jumps over the relocated words do not settle")


def at(off):
    return HDR + SEG * 16 + off


def original():
    blob = open(SRC, "rb").read()
    return blob[at(START):at(END)]


def fixed():
    """The new bytes of START..END."""
    orig = original()
    gaps = holes()
    consts = {"err": ERR, "tail": END}
    code_b, labels = pack(SRC_B, ERR_END, END, [g for g in gaps if g >= ERR_END], consts)
    code_a, _ = pack(SRC_A, START, ERR, [g for g in gaps if g < ERR], {**consts, "main": labels["main"]})
    if len(code_a) != ERR - START:
        raise VmSwapError(f"{START:04X}-{ERR:04X}: {len(code_a)} bytes, not up to the error exit")
    room = bytearray([FILL]) * (END - START)
    room[:len(code_a)] = code_a
    room[ERR - START:ERR - START + 2] = b"\x1e\x50"                     # push ds / push ax
    room[ERR + 2 - START:ERR_END - START] = orig[ERR + 2 - START:ERR_END - START]
    room[ERR_END - START:ERR_END - START + len(code_b)] = code_b
    for g in gaps:
        room[g - START:g - START + 2] = orig[g - START:g - START + 2]
    return bytes(room)


def state(blob):
    """'orig' or 'fixed'."""
    now = bytes(blob[at(START):at(END)])
    if now == original():
        return "orig"
    if now == fixed():
        return "fixed"
    raise VmSwapError(f"{FILE} 第 {at(START):#x}-{at(END):#x} 字节既不是原版也不是修复后的内容")


def apply_to(blob, revert=False):
    """DDS98.EXE with the swap in XMS (or the game's own back)."""
    state(blob)
    out = bytearray(blob)
    out[at(START):at(END)] = original() if revert else fixed()
    return bytes(out)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exe")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    data = open(a.exe, "rb").read()
    print(f"{a.exe}: {state(data)}")
    out = apply_to(data, revert=a.revert)
    if out != data:
        open(a.exe, "wb").write(out)
        print(f"{a.exe}: {state(out)}")


if __name__ == "__main__":
    main()
