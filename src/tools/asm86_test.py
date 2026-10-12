#!/usr/bin/env python3
"""Self-test for asm86: every encoder path, known encodings, relaxation, errors."""
import sys

from asm86 import Asm, AsmError, assemble

# (source line, bytes the game's own code uses for it or the shortest encoding)
KNOWN = [
    ("mov ax, word ptr [bp - 0xe]", "8b46f2"),
    ("mov word ptr [bp - 0xe], ax", "8946f2"),
    ("mov word ptr [bp - 0xe], 3", "c746f20300"),
    ("mov byte ptr es:[bx], 2", "26c60702"),
    ("mov al, byte ptr [bx + si + 0x68c]", "8a808c06"),
    ("mov al, byte ptr es:[bx + di]", "268a01"),
    ("les bx, ptr [bp + 6]", "c45e06"),
    ("lds si, ptr [bp + 6]", "c57606"),
    ("lea cx, [bx - 0x7e]", "8d4f82"),
    ("test byte ptr [bx + 0x4deb], 4", "f687eb4d04"),
    ("test byte ptr [bp + 7], 0x80", "f6460780"),
    ("cmp ah, 0x80", "80fc80"),
    ("cmp ax, 0x7e7e", "3d7e7e"),
    ("cmp word ptr [bp + 6], 1", "837e0601"),
    ("and di, 0xff", "81e7ff00"),
    ("and ax, 1", "250100"),
    ("add word ptr [bp + 0xc], 0x280", "81460c8002"),
    ("add byte ptr [bp + 0xd], 5", "80460d05"),
    ("shl di, 4", "c1e704"),
    ("shl ax, cl", "d3e0"),
    ("shr al, 4", "c0e804"),
    ("sub ah, ah", "28e4"),              # the game's 2ae4 is the equivalent r, r/m form
    ("xor ax, ax", "31c0"),
    ("push 0x33", "6a33"),
    ("push 0x6c64", "68646c"),
    ("push -1", "6aff"),
    ("push ss", "16"),
    ("pop ds", "1f"),
    ("push word ptr [bp + 0xa]", "ff760a"),
    ("mov es, word ptr [bp + 8]", "8e4608"),
    ("mov dx, ds", "8cda"),
    ("mov ax, word ptr [0x6da]", "a1da06"),
    ("mov ax, word ptr es:[0x6da]", "26a1da06"),
    ("mov word ptr cs:[0x104], bx", "2e891e0401"),
    ("mov ax, word ptr [bp]", "8b4600"),
    ("inc word ptr [bp - 0xc]", "ff46f4"),
    ("inc byte ptr [bp - 5]", "fe46fb"),
    ("inc si", "46"),
    ("dec cx", "49"),
    ("neg ax", "f7d8"),
    ("div cx", "f7f1"),
    ("imul ax, bx, 3", "6bc303"),
    ("enter 0xe, 0", "c80e0000"),
    ("leave", "c9"),
    ("retf 6", "ca0600"),
    ("ret", "c3"),
    ("int 0x21", "cd21"),
    ("in al, 2", "e402"),
    ("out 0x6a, al", "e66a"),
    ("in al, dx", "ec"),
    ("out dx, ax", "ef"),
    ("xchg ax, bx", "93"),
    ("xchg bl, byte ptr [si]", "861c"),
    ("rep movsw", "f3a5"),
    ("repne scasb", "f2ae"),
    ("lodsb", "ac"),
    ("lcall [0x1234]", "ff1e3412"),
    ("ljmp [bx]", "ff2f"),
    ("lcall 0, 0xdce", "9ace0d0000"),
    ("ljmp 0x1234:0x5678", "ea78563412"),
    ("call bx", "ffd3"),
    ("jmp word ptr [bx + 2]", "ff6702"),
    ("pushf", "9c"),
    ("iret", "cf"),
    ("cbw", "98"),
    ("cwd", "99"),
    ("pusha", "60"),
]


def check_known():
    bad = 0
    for text, want in KNOWN:
        code, _ = assemble(text, org=0x100)
        if code.hex() != want:
            print(f"MISMATCH  {text!r}: got {code.hex()} want {want}")
            bad += 1
    return bad


BRANCHES = """
start:
    jmp fwd_short
    jcxz start
    loop start
    je start
    jnz fwd_short
fwd_short:
    call far_away
    jmp far_away
    jmp short start
    resb 200
far_away:
    jmp start
    ret
"""


def check_branches():
    a = Asm(BRANCHES, org=0x100)
    code = a.build()
    lab = a.labels
    bad = 0
    # jmp over 200 bytes must be near, backward jmp from far_away too
    first = next(c for adr, c, st in a.listing if st.text.strip() == "jmp far_away")
    last = next(c for adr, c, st in a.listing if st.text.strip() == "jmp start")
    if first[0] != 0xE9 or last[0] != 0xE9:
        print("relaxation did not pick near jumps", first.hex(), last.hex())
        bad += 1
    short = next(c for adr, c, st in a.listing if st.text.strip() == "jmp fwd_short")
    if short[0] != 0xEB:
        print("short jump not kept short", short.hex())
        bad += 1
    if lab["start"] != 0x100:
        print("org not applied")
        bad += 1
    return bad, len(code)


ERRORS = [
    "mov [bx], 1",                       # size unknown
    "je far_label\nresb 300\nfar_label:",  # conditional out of range
    "mov cs, ax",
    "push al",
    "mov al, bx",
    "mov ax, [bx + cx]",
    "mov ax, undefined_name",
]


def check_errors():
    bad = 0
    for src in ERRORS:
        try:
            assemble(src)
        except AsmError:
            continue
        print(f"no error for {src!r}")
        bad += 1
    return bad


COVER = """
value equ 0x1234
    add al, 1
    adc cx, word ptr [si]
    sbb byte ptr [di + 3], dl
    or dx, value
    sub word ptr cs:[data], 0x100
    xor bh, bh
    cmp byte ptr [data + 1], 'A'
    test ax, 0x8000
    test cx, dx
    test word ptr [bx], 7
    mov bl, 0x80
    mov sp, value
    mov word ptr [data], value
    mov ds, ax
    mov word ptr [bx + si], es
    not byte ptr [bx]
    mul bl
    idiv word ptr [data]
    rol byte ptr [bx], 1
    rcr ax, 3
    sar dx, cl
    xchg dx, word ptr [bp + 2]
    in ax, 0x40
    out dx, al
    push data
    pop word ptr [data]
    push cs
    pop es
    popa
    popf
    lahf
    sahf
    clc
    stc
    cmc
    cld
    std
    cli
    sti
    nop
    xlatb
    int3
    stosw
    rep stosb
    repe cmpsw
    movsb
    scasw
    call word ptr [data]
    lcall ptr [bx + 4]
    ljmp [data]
    retf
    ret 2
    loope data
data:
    dw data, value, 0
    db 1, 2, "ok", 0xff, -1
"""


def main():
    bad = check_known()
    b, n = check_branches()
    bad += b
    bad += check_errors()
    code, labels = assemble(COVER)
    print(f"known encodings: {len(KNOWN)}, branch test {n} B, error cases {len(ERRORS)}, "
          f"coverage program {len(code)} B")
    print("FAIL" if bad else "all asm86 checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
