#!/usr/bin/env python3
"""holdshow_test.py - tools/holdshow.py on an emulated CPU (unicorn) and in the file.

  * the file: only the call sites, the two blocks and the five counts differ; the call sites keep their
    relocations (the segment word, now 358E) and no relocation lies in a block; nothing another change of the
    build, an option of the patch page or the 再平衡版 writes overlaps them; apply_to is idempotent and revert gives the
    original back; each count is the `push` of 25CA:8758's count, -1 in the original and 60 changed, and each
    notice's name is the build's wording (text/tables/DDS98.EXE.json) of the string pushed with it;
  * DRAW (358E:4174), far-called as from 1603:C240, with 25CA:882E a stub that counts its calls: no window, or a
    window whose text cursor is home (row 0 or the +10h row when +1Eh bit 0 is set, column 0), is not drawn; a
    cursor anywhere else is, once; either way it comes back to its caller with [78C6] in ax (25CA:8090) and the
    stack as it was;
  * SETUP (358E:4148), far-called as from 1603:C22F with the four arguments of 25CA:84B0, which is a stub that
    keeps them and returns with retf 8: the mask arrives as it was pushed unless the left button is held
    ([98F8] bit 0), when it arrives with bit 0 cleared; the other arguments are untouched and the stack is
    balanced;
  * the game's own wait check 25CA:8444 for a mode-2 wait (25CA:8438, the end of the wait, a counting stub):
    the mask FFFF ends it on a held left button - the click that picked a target -, the mask SETUP leaves does
    not, and a new press or the right button held still does; a click wait's mask 2 is left alone.

    holdshow_test.py [--image HDI]

With an image, its DDS98.EXE is the changed program (with every other change of the build in it, the keys'
Enter / Space check in 8444 included - INT 21h answers that no key waits) and the same file with this change
taken out the original.
"""
import argparse
import os
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_16, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_INTR, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import holdshow  # noqa: E402
from asm86 import assemble  # noqa: E402
from mz import MZ  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP
CAVE = LOAD + holdshow.SEG              # 358E
WIN = LOAD + holdshow.WINDOW_SEG        # 25CA
SENT = 0xD000                           # a hlt the far returns come back to
DRAWS, ENDED, KEPT = 0xFFE0, 0xFFE2, 0xFFE4      # the stubs' counters, and 84B0's four arguments as it got them
WINDOWS = 0x6E30                        # the window records, 34h bytes each
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def load(blob):
    path = os.path.join(WORK, "build", "_holdshow_test.exe")
    with open(path, "wb") as f:
        f.write(blob)
    try:
        return bytes(MZ(path, base=LOAD).image), MZ(path).reloc_set
    finally:
        os.remove(path)


class Game:
    def __init__(self, blob):
        img, _ = load(blob)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x110000)
        self.mu.mem_write(LOAD * 16, img)
        # 25CA:882E (draw the message window): count the call
        self.mu.mem_write(WIN * 16 + 0x882E, assemble(f"inc word ptr [{DRAWS:#x}]\nretf", org=0x882E)[0])
        # 25CA:84B0 (set a wait up): keep its four arguments, return as it does
        keep = "push bp\nmov bp, sp\n" + "".join(
            f"mov ax, word ptr [bp + {6 + 2 * k}]\nmov word ptr [{KEPT + 2 * k:#x}], ax\n" for k in range(4))
        self.mu.mem_write(WIN * 16 + 0x84B0, assemble(keep + "pop bp\nretf 8", org=0x84B0)[0])
        # 25CA:8438 (end the wait): count the call
        self.mu.mem_write(WIN * 16 + 0x8438, assemble(f"inc word ptr [{ENDED:#x}]\nretf", org=0x8438)[0])
        self.mu.mem_write(SENT * 16, b"\xf4")
        self.mu.hook_add(UC_HOOK_INTR, self.intr)

    def intr(self, mu, n, _data):
        # INT 21h for the keys' check in 8444 (tools/exekeys.py): AH=06h, no key waiting (ZF set)
        ah = mu.reg_read(X.UC_X86_REG_AH)
        if n != 0x21 or ah != 0x06:
            raise RuntimeError(f"INT {n:02X}h AH={ah:02X}h")
        mu.reg_write(X.UC_X86_REG_AL, 0)
        mu.reg_write(X.UC_X86_REG_FLAGS, mu.reg_read(X.UC_X86_REG_FLAGS) | 0x40)

    def word(self, off, seg=DS):
        return struct.unpack("<H", self.mu.mem_read(seg * 16 + off, 2))[0]

    def put(self, off, *words):
        self.mu.mem_write(DS * 16 + off, struct.pack(f"<{len(words)}H", *words))

    def far_call(self, cs, ip, args=()):
        """Far-call cs:ip with `args` pushed (first pushed first) -> (ax, sp after the return - sp before the
        arguments were pushed)."""
        top = 0xA000
        frame = struct.pack("<2H", 0, SENT) + struct.pack(f"<{len(args)}H", *reversed(args))
        sp = top - len(frame)
        self.mu.mem_write(DS * 16 + sp, frame)
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, cs), (X.UC_X86_REG_IP, ip), (X.UC_X86_REG_SP, sp),
                       (X.UC_X86_REG_FLAGS, 0x0202)):
            self.mu.reg_write(reg, v)
        self.mu.emu_start(cs * 16 + ip, SENT * 16, count=100_000)
        if self.mu.reg_read(X.UC_X86_REG_CS) != SENT:
            raise RuntimeError(f"{cs:04X}:{ip:04X} did not come back")
        return self.mu.reg_read(X.UC_X86_REG_AX), self.mu.reg_read(X.UC_X86_REG_SP) - top

    def draw(self, window, row=0, col=0, keep_home=None):
        """DRAW with the message window [1BBA] = window (-1: none) and its cursor at (row, col); keep_home: the
        home row +10h with +1Eh bit 0 set -> (draws, ax, stack)."""
        self.put(DRAWS, 0)
        self.put(0x78C6, 0x1234)
        self.put(0x1BBA, window & 0xFFFF)
        if window >= 0:
            rec = WINDOWS + 0x34 * window
            self.mu.mem_write(DS * 16 + rec, b"\xa5" * 0x34)
            flags = 0xA5A4 | (1 if keep_home is not None else 0)
            self.put(rec + 0x1E, flags)
            self.put(rec + 0x10, keep_home if keep_home is not None else 0x5A5A)
            self.put(rec + 0x0C, row, col)
        ax, stack = self.far_call(CAVE, holdshow.DRAW_AT)
        return self.word(DRAWS), ax, stack

    def setup(self, buttons, mask, mode=2, count=60, arg=7):
        """SETUP with [98F8] = buttons and 84B0's arguments (mode, mask, count, arg pushed in that order) ->
        ((arg, count, mask, mode) as 84B0 got them, stack)."""
        self.put(0x98F8, buttons)
        self.put(KEPT, 0, 0, 0, 0)
        _ax, stack = self.far_call(CAVE, holdshow.SETUP_AT, (mode, mask, count, arg))
        return tuple(self.word(KEPT + 2 * k) for k in range(4)), stack

    def check_wait(self, buttons, mask):
        """One frame of 25CA:8444 for a mode-2 wait of 10 frames -> whether it ended."""
        self.put(0x78C8, 2, mask, 10)           # mode, mask, count
        self.put(0x98F8, buttons)
        self.put(0x14D6, 0xFFFF)                 # no click prompt to blink (25CA:4002 returns at once)
        self.put(ENDED, 0)
        self.far_call(WIN, 0x8444)
        return self.word(ENDED) == 1


def other_changes(orig):
    """[file offset] every byte the build's other changes, the patch page's options and the 再平衡版 write."""
    import bagexpand, checkfix, ctxfree, exefix, exekeys, expgap, expshow, moonfast, nospace, rebalance  # noqa
    import skillfix, slotorder, statfix, storyfix, targetprompt, vmswap  # noqa
    built = orig
    for step in (exefix.apply_to, storyfix.mend_exe, checkfix.mend_exe, statfix.apply_to, expshow.mend_exe,
                 nospace.apply_to, slotorder.apply_to, ctxfree.apply_to, vmswap.apply_to, bagexpand.apply_to,
                 skillfix.mend_exe, moonfast.mend_exe, exekeys.apply_to, expgap.mend_exe, rebalance.mend_exe,
                 targetprompt.apply_to):
        built = step(built)
    return {i for i in range(len(orig)) if orig[i] != built[i]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    a = ap.parse_args()
    if a.image:
        from fat12 import Fat12, open_hdi
        _raw, _hdr, disk, part = open_hdi(a.image)
        fs = Fat12(disk, part)
        e = fs.find("DDS98/" + holdshow.FILE)
        fixed = bytes(fs.read_chain(e["cluster"], e["size"]))
        check(holdshow.state(fixed) == "fixed", f"{a.image}: the change is in")
        orig = holdshow.apply_to(fixed, revert=True)
    else:
        orig = open(os.path.join(WORK, "files", "DDS98", holdshow.FILE), "rb").read()
        check(holdshow.state(orig) == "orig", "files/DDS98: the original")
        fixed = holdshow.apply_to(orig)

    print("the file")
    mine = set()
    for _name, o, a_, _b in holdshow.sites():
        mine |= set(range(o, o + len(a_)))
    diff = {i for i in range(len(orig)) if orig[i] != fixed[i]}
    check(len(orig) == len(fixed) and diff <= mine, f"only the sites differ ({len(diff)} bytes)")
    _img, relocs = load(fixed)
    hdr = holdshow.HDR
    for site in (0x1603 * 16 + 0xC240, 0x1603 * 16 + 0xC22F):
        img = fixed[hdr + site:hdr + site + 5]
        check(site + 3 in relocs and img[3:5] == struct.pack("<H", holdshow.SEG),
              f"the call at {site:#x} keeps its relocation and names 358E")
    blocks = set()
    for start, code in holdshow.blocks().items():
        blocks |= set(range(holdshow.SEG * 16 + start, holdshow.SEG * 16 + start + len(code)))
    check(not any(p in relocs or p + 1 in relocs for p in blocks), "no relocation in the blocks")
    if not a.image:
        others = other_changes(orig)
        check(not (others & mine), f"no byte shared with the other changes ({len(others)} bytes)")
    check(holdshow.apply_to(fixed) == fixed, "apply_to is idempotent")
    check(holdshow.apply_to(fixed, revert=True) == orig, "revert gives the original back")
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    for name, push in holdshow.NOTICES:
        o = holdshow.at(holdshow.WINDOW_SEG, push) + 1          # the count byte
        off = push + 1
        for blob, want in ((orig, "-1"), (fixed, "0x3c")):
            ins = list(md.disasm(blob[o - 5:o + 6], off - 5))
            got = [f"{i.mnemonic} {i.op_str}".strip() for i in ins]
            check(got == ["push ds", got[1], f"push {want}", "nop", "push cs", "call 0x8758"]
                  and got[1].startswith("push 0x"), f"{name}: {' / '.join(got)}")

    g = Game(fixed)
    print("DRAW (358E:4174)")
    for args, want, what in (((-1,), 0, "no window"),
                             ((3, 0, 0), 0, "cursor home"),
                             ((3, 0, 5), 1, "text on the first row"),
                             ((3, 1, 0), 1, "a line end written"),
                             ((3, 2, 0, 2), 0, "home row 2, cursor there"),
                             ((3, 2, 4, 2), 1, "home row 2, text written"),
                             ((3, 0, 0, 2), 1, "home row 2, cursor above it")):
        draws, ax, stack = g.draw(*args[:3], keep_home=args[3] if len(args) > 3 else None)
        check(draws == want and ax == 0x1234 and stack == 0,
              f"{what}: {draws} draw(s), ax {ax:04X}, stack {stack:+d}")
    print("SETUP (358E:4148)")
    for buttons, mask, want, what in ((0x00, 0xFFFF, 0xFFFF, "nothing held"),
                                      (0x01, 0xFFFF, 0xFFFE, "left held"),
                                      (0x05, 0xFFFF, 0xFFFE, "left pressed this frame"),
                                      (0x10, 0xFFFF, 0xFFFF, "right held"),
                                      (0x01, 0x0002, 0x0002, "click wait, left held")):
        kept, stack = g.setup(buttons, mask)
        check(kept == (7, 60, want, 2) and stack == 0,
              f"{what}: 84B0 gets mask {kept[2]:04X} (arg {kept[0]}, count {kept[1]}, mode {kept[3]}), "
              f"stack {stack:+d}")
    print("the wait's check (25CA:8444), mode 2")
    for buttons, mask, want, what in ((0x01, 0xFFFF, True, "held, mask as the game sets it"),
                                      (0x01, 0xFFFE, False, "held from before the wait"),
                                      (0x05, 0xFFFE, True, "a new press"),
                                      (0x10, 0xFFFE, True, "right held"),
                                      (0x00, 0xFFFE, False, "nothing"),
                                      (0x01, 0x0002, False, "click wait's mask, held")):
        ended = g.check_wait(buttons, mask)
        check(ended == want, f"{what}: {'ends' if ended else 'goes on'}")

    print("FAILED" if fails else "all passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
