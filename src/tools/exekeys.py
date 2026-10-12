#!/usr/bin/env python3
"""Keys for DDS98.EXE: W Z A D Q E S walk the map like the numeric keypad, and Enter and Space go on
wherever the game is waiting for a click to go on.

How the game reads the keyboard. Only through DOS: main 0x2B5F6 asks INT 21h AH=0Bh whether a key is
waiting (main 0x00D80) and reads it with AH=08h (main 0x00DA6). It is called only from main 0x2B554,
while the map screen (main 0x3CA4E -> 0x3D044) finds no click on one of its seven movement buttons, and
it takes the characters '1'-'9' through the word table at ds:0x175E + 2 x character to a button number:
'8' 0 forward, '6' 1 right, '2' 2 back, '4' 3 left, '9' and '3' 4 turn right, '5' 5 turn around, '7'
and '1' 6 turn left (main 0x2B524, the buttons' handler, then acts). Nothing else reads keys: the only
other callers of those two DOS calls, main 0x0F13C and main 0x3CA4E, throw pending keys away. The C
runtime's one-character push-back slot ds:0x4DB2 starts at FFFF and is never given a character, and its
hook at ds:0x53CC is never armed (ds:0x53CA is 0 and nothing writes it), so both calls are plain DOS.

How the game waits for a click. The buttons are kept per frame by main 0x0D852 in ds:0x98F8 (bit 0 left
held, bit 2 left pressed this frame, bit 4 right held). A click to go on is a wait state: main 0x2E150
(window, count, mask, mode) pushes game state 1 with the mode in ds:0x78C8, and main 0x2E0E4 runs it
once a frame - called by the game's state machine main 0x2DF2A, and by script command 210 (main 0x2221A)
in its own loop while a battle line holds. Mode 1 waits for a click, mode 2 counts frames and a click
cuts it short; for both the frame's check at main 0x2E11A ends the wait when the mask allows a held left
button (mask bit 0), a pressed one (mask bit 1), or the right button is held. Every "click to continue"
of the game goes through it: the pages of dialogue (210 mode 1), the battle's timed lines (210 mode 2),
and windows the game opens itself, like the end-of-battle summary (main 0x20BBE, flag 0x20 of the
window at 4827:085C). Menus and buttons do not: they take the click latched with the pointer position in
ds:0x9B30 / ds:0x9940 and ask what is under it (main 0x2A020, 0x2B2FE, 0x38D60, 0x3D044, ov05:0BF0,
ov16:2C2E and the debugger) - a key has no position to give them, so they stay mouse-only, and so do the
error box of main 0x0FB54, the pop-up of ov22:107A and the skip click of ov45:040C.

The change, three sites and one routine block:

  main 0x2B605  after the character is read, `call map_key` turns w z a d q e s (either case) into
                8 2 4 6 7 9 5 before the unchanged '1'-'9' check and table look-up
  main 0x2E140  the frame's last test, right button held, becomes `call advance`: that, or a key
                waiting that is Enter (0D) or Space (20) - read with AH=06h, which does not wait; a key
                read that is neither is dropped, since nothing else reads keys while a wait runs
  main 0x2E157  where a wait is set up, `call flush_wait`: for modes 1 and 2, INT 21h AH=0Ch AL=00
                empties the keyboard buffer first, so a key pressed before the wait began (a second
                Enter while the page was still being drawn) does not end it - as a click from before a
                wait does not, the press being kept for one frame only

The routines go where main 0x2F038-0x2F0D3 was: a routine (it walks a combatant's skill list) that
nothing can enter - no near branch into it from outside, no far call, no relocated pointer to it, and
its entry offset 25CA:9398 occurs nowhere in the image or the overlays; a retf and a pad byte come before
it. All of it is in segment 25CA, so every call is near and the relocation table is untouched; no
relocation falls inside any site or the block, and no branch lands inside a site except on its first
byte (0x2E140 is the target of the mask bit 1 test, and stays the start of the new call)."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm86 import assemble  # noqa: E402

FILE = "DDS98.EXE"
SEG_BASE = 0x25CA0
BLOCK = 0x2F038
BLOCK_ORIG = bytes.fromhex(
    "c808000057568b7608c746f800008e460a2683bcf101007e7b33ff26c49cf3012683390074468e460a26c49cf301"
    "26ff31900ee840fb8ec28bd88946fc8c46fe268a072ae43b46067522ff760a565253900ee8f9fe8946faff760a56ff"
    "76feff76fc900ee80dff0b46fa741683c702ff46f88b46f88e460a263984f1017f9ceb13908e460a26c49cf3018b7e"
    "f803ff268b01eb0233c05e5fc9ca0600")

ROUTINES = """
map_key:                        ; al = the character read (ah = 0) -> si = ax = the character to use
    push cx
    mov cl, al
    or al, 0x20                 ; a letter in either case, as lower case
    mov ch, '8'
    cmp al, 'w'
    je found
    mov ch, '2'
    cmp al, 'z'
    je found
    mov ch, '4'
    cmp al, 'a'
    je found
    mov ch, '6'
    cmp al, 'd'
    je found
    mov ch, '7'
    cmp al, 'q'
    je found
    mov ch, '9'
    cmp al, 'e'
    je found
    mov ch, '5'
    cmp al, 's'
    jne keep
found:
    mov cl, ch
keep:
    mov al, cl
    xor ah, ah
    mov si, ax
    pop cx
    ret

advance:                        ; ZF clear: the wait ends (right button held, or Enter / Space)
    test byte ptr [0x98f8], 0x10
    jne done
    push dx
    mov ah, 6
    mov dl, 0xff
    int 0x21                    ; ZF set when no key is waiting
    je none
    cmp al, 0xd
    je key
    cmp al, 0x20
    je key
none:
    xor dx, dx                  ; ZF set
    pop dx
    ret
key:
    test al, al                 ; ZF clear
    pop dx
done:
    ret

flush_wait:                     ; si = the mode of the wait being set up; ax = 1 on return
    mov ax, si
    dec ax
    cmp ax, 1
    ja set
    mov ax, 0xc00
    int 0x21                    ; empty the keyboard buffer, read nothing
set:
    mov ax, 1
    ret
"""


def routines():
    """(block bytes, {label: image address}) - the routines assembled where they go, padded to the
    length of what they replace with NOPs."""
    code, labels = assemble(ROUTINES, org=BLOCK - SEG_BASE)
    if len(code) > len(BLOCK_ORIG):
        raise ValueError(f"the routines take {len(code)} bytes, the block has {len(BLOCK_ORIG)}")
    return code + b"\x90" * (len(BLOCK_ORIG) - len(code)), {k: v + SEG_BASE for k, v in labels.items()}


def sites():
    """[(name, image address, original bytes, new bytes)], the block last."""
    block, at = routines()

    def call(site, target, tail):
        code, _ = assemble(f"call {target - SEG_BASE:#x}\n{tail}", org=site - SEG_BASE)
        return code

    return [
        ("读键换码", 0x2B605, bytes.fromhex("8bf083fe31721483fe39770f"),
         call(0x2B605, at["map_key"], "cmp al, 0x31\njb 0x5980\ncmp al, 0x39\nja 0x5980\nnop")),
        ("点击等待", 0x2E140, bytes.fromhex("f606f898107405"),
         call(0x2E140, at["advance"], "je 0x84ac\nnop\nnop")),
        ("等待开始", 0x2E157, bytes.fromhex("b80100"),
         call(0x2E157, at["flush_wait"], "")),
        ("新增例程", BLOCK, BLOCK_ORIG, block),
    ]


def header_size(blob):
    return struct.unpack_from("<H", blob, 8)[0] * 16


def state(blob):
    """'orig' or 'patched' - every site has to be in the same one."""
    hdr = header_size(blob)
    seen = set()
    for name, at, orig, new in sites():
        here = bytes(blob[hdr + at:hdr + at + len(orig)])
        if here == orig:
            seen.add("orig")
        elif here == new:
            seen.add("patched")
        else:
            raise ValueError(f"{name}（main 0x{at:05X}）：{here.hex(' ')} 既不是原版也不是改后的字节")
    if len(seen) != 1:
        raise ValueError("DDS98.EXE 只改了一部分")
    return seen.pop()


def apply_to(blob):
    """The executable with the keys in."""
    state(blob)
    out = bytearray(blob)
    hdr = header_size(blob)
    for _name, at, orig, new in sites():
        assert len(new) == len(orig)
        out[hdr + at:hdr + at + len(new)] = new
    return bytes(out)


def main(argv):
    """exekeys.py [DDS98.EXE] - whether the keys are in, and what each site becomes."""
    path = argv[0] if argv else os.path.join("files", "DDS98", FILE)
    blob = open(path, "rb").read()
    print(f"{path}：{'已改' if state(blob) == 'patched' else '原版'}")
    for name, at, orig, new in sites():
        print(f"  {name}  main 0x{at:05X}  {len(orig)} 字节")
        if len(orig) < 16:
            print(f"      原 {orig.hex(' ')}\n      新 {new.hex(' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
