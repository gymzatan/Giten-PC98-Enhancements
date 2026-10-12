#!/usr/bin/env python3
"""bagexpand_test.py - tools/bagexpand.py on an emulated CPU (unicorn): the bag module of the original DDS98.EXE and of
the expanded one, run side by side on the game's own code. Stubbed: the item table lookups 25CA:C17A (kind), CC1A
(stack limit), C158 (record) - from the shipped ET0001 kinds and CC1A's own kind map -, C1DA (the record buffer,
whose byte CE6C reads and then overwrites), the got-item message F40C,
the discard menu F50A (never reached: the tests give items with 25CA:CE16's silent flag set), sprintf, the fatal
error window 0871:7444 (records the call), the allocator 0871:7AA8 / 7ABA, fwrite / fread (0000:0570 / 03FC, on
a file in memory) and the last save section 358E:9E6C / 9EC4 (a 6-byte marker).

  * the file: every site original or expanded, apply_to idempotent and reversible, no relocation inside a changed
    site but the two ov03 calls' segment words (the loader relocates them, now to 25CA);
  * new game: ov08:1474 empties 64 / 127 slots;
  * giving distinct single items (swords): 48 / 111 go in, the next one does not; consumables stack to 99;
    恋人の部位 go to slots 48-63 / 111-126, the 17th is the fatal 「シナリオアイテムバッファが一杯です」;
  * taking, counting, the used-slot count, the list of used slots (D86E with 40h / 7Fh) and packing (D9F8);
  * command 2E6 (D96E): store, empty, restore gives the same bag; the copy itself is the original's 64 entries;
  * saves: the expanded game's save and load give the same bag back; an original save loads into the expanded game
    with slots 48-110 empty; an expanded save loads into the original game with the first 48 and the 16 scenario
    slots; the last section's marker is read back in every case.

    bagexpand_test.py [--image HDI]

With an image, its DDS98.EXE is the expanded program (with every other fix of the build in it) and the same file with
this change taken out the original.
"""
import argparse
import os
import random
import struct
import sys

from unicorn import UC_ARCH_X86, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bagexpand as B  # noqa: E402
import tables  # noqa: E402
from asm86 import assemble  # noqa: E402
from mz import MZ, overlays  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC
CS25, CS358, CS0, CS871 = LOAD + 0x25CA, LOAD + 0x358E, LOAD, LOAD + 0x0871
OV8 = 0xC000                            # where ov08's image goes (its 1474 needs no relocation)
TSEG = 0xB000                           # kinds at 0, stack limits at 800h
FSEG = 0x8000                           # the save file
SENT = 0xD000
STUBS = 0xE000                          # the stubs' bodies
FPOS, FLEN, FATAL, MARK, MARKIN = 0xF800, 0xF802, 0xF804, 0xF810, 0xF820
ALLOC = 0xF100                          # the allocator's block (DS)
COPY = 0xF400                           # command 2E6's copy (DS), 256 bytes
STACK = 0xF0F0
SILENT = 0x2F84
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def kinds():
    """item number -> kind byte (ET0001 +4), as the game's records give it."""
    (chunk,) = tables.chunks_of(open(os.path.join(WORK, "files", "DDS98", "ET0001.BIN"), "rb").read())[:1]
    out = bytearray(0x800)
    for i, e in enumerate(tables.string_table(chunk)):
        if len(e) > 8 and e[4] in tables.ITEM_HEADER:
            out[i] = e[4]
    return out


KINDS = kinds()
LIMIT = bytes(99 if k in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 19) else 1 for k in KINDS)   # 25CA:CC1A
SWORDS = [i for i in range(0x800) if KINDS[i] == 11]
CONSUMABLE = next(i for i in range(0x800) if KINDS[i] == 1)
PARTS = [i for i in range(0x800) if KINDS[i] == 10]


def asm(src, org):
    return assemble(src, org=org)[0]


class Game:
    def __init__(self, blob, expanded):
        self.expanded = expanded
        self.bag = B.BAG if expanded else 0x866E
        self.total, self.normal = (B.TOTAL, B.NORMAL) if expanded else (64, 48)
        path = os.path.join(WORK, "build", "_bagexpand_test.exe")
        with open(path, "wb") as f:
            f.write(blob)
        try:
            img = bytes(MZ(path, base=LOAD).image)
            ov8 = bytes(overlays(path)[8].image)
        finally:
            os.remove(path)
        mu = self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        mu.mem_map(0, 0x110000)
        mu.mem_write(LOAD * 16, img)
        mu.mem_write(OV8 * 16, ov8)
        mu.mem_write(TSEG * 16, bytes(KINDS) + LIMIT)
        mu.mem_write(SENT * 16, b"\xf4")
        stub = {
            (CS25, 0xC17A): f"push bp\nmov bp, sp\npush es\npush bx\nmov ax, {TSEG:#x}\nmov es, ax\n"
                            "mov bx, word ptr [bp + 6]\nand bx, 0x7ff\nmov al, byte ptr es:[bx]\nxor ah, ah\n"
                            "pop bx\npop es\npop bp\nretf 2",
            (CS25, 0xCC1A): f"push bp\nmov bp, sp\npush es\npush bx\nmov ax, {TSEG:#x}\nmov es, ax\n"
                            "mov bx, word ptr [bp + 6]\nand bx, 0x7ff\nmov al, byte ptr es:[bx + 0x800]\nxor ah, ah\n"
                            "pop bx\npop es\npop bp\nretf 2",
            (CS25, 0xC158): f"push bp\nmov bp, sp\npush es\npush bx\nmov ax, {TSEG:#x}\nmov es, ax\n"
                            "mov bx, word ptr [bp + 6]\nand bx, 0x7ff\nxor ax, ax\nxor dx, dx\n"
                            "cmp byte ptr es:[bx], 0\nje c158_none\nmov ax, bx\nmov dx, es\nc158_none:\n"
                            "pop bx\npop es\npop bp\nretf 2",
            (CS25, 0xC1DA): f"mov ax, 0x1000\nmov dx, {TSEG:#x}\nretf 2",     # CE6C reads +7 and overwrites it
            (CS25, 0xF40C): "retf 2",
            (CS25, 0xF50A): f"mov word ptr [{FATAL:#x}], 2\nretf",
            (CS0, 0x0FA8): "retf",
            (CS871, 0x7444): f"mov word ptr [{FATAL:#x}], 1\nljmp {SENT:#x}:0",
            (CS871, 0x7AA8): f"mov ax, {ALLOC:#x}\nmov dx, ds\nretf 4",
            (CS871, 0x7ABA): "retf 4",
            (CS0, 0x0570): f"""
                push bp
                mov bp, sp
                push si
                push di
                push ds
                push es
                mov ax, word ptr [bp + 0xa]
                mul word ptr [bp + 0xc]
                mov cx, ax
                mov di, word ptr [{FPOS:#x}]
                mov ax, {FSEG:#x}
                mov es, ax
                lds si, ptr [bp + 6]
                cld
                rep movsb
                pop es
                pop ds
                mov word ptr [{FPOS:#x}], di
                mov word ptr [{FLEN:#x}], di
                mov ax, word ptr [bp + 0xc]
                pop di
                pop si
                pop bp
                retf""",
            (CS0, 0x03FC): f"""
                push bp
                mov bp, sp
                push si
                push di
                push es
                mov ax, word ptr [{FLEN:#x}]
                sub ax, word ptr [{FPOS:#x}]
                xor dx, dx
                div word ptr [bp + 0xa]
                cmp ax, word ptr [bp + 0xc]
                jbe fread_n
                mov ax, word ptr [bp + 0xc]
            fread_n:
                push ax
                mul word ptr [bp + 0xa]
                mov cx, ax
                mov si, word ptr [{FPOS:#x}]
                add word ptr [{FPOS:#x}], cx
                les di, ptr [bp + 6]
                push ds
                mov ax, {FSEG:#x}
                mov ds, ax
                cld
                rep movsb
                pop ds
                pop ax
                pop es
                pop di
                pop si
                pop bp
                retf""",
            (CS358, B.SAVE_LAST): f"push bp\nmov bp, sp\npush word ptr [bp + 8]\npush word ptr [bp + 6]\npush 6\n"
                                  f"push 1\npush ds\npush {MARK:#x}\nlcall {CS0:#x}:0x570\nadd sp, 0xc\nxor ax, ax\n"
                                  "pop bp\nretf 4",
            (CS358, B.LOAD_LAST): f"push bp\nmov bp, sp\npush word ptr [bp + 8]\npush word ptr [bp + 6]\npush 6\n"
                                  f"push 1\npush ds\npush {MARKIN:#x}\nlcall {CS0:#x}:0x3fc\nadd sp, 0xc\nxor ax, ax\n"
                                  "pop bp\nretf 4",
        }
        # each stub's body in a segment of its own, a far jump to it in the routine's place (stubs never overlap)
        for k, ((seg, off), src) in enumerate(stub.items()):
            body = 0x100 * k
            mu.mem_write(STUBS * 16 + body, asm(src, body))
            mu.mem_write(seg * 16 + off, asm(f"ljmp {STUBS:#x}:{body:#x}", off))
        self.w(MARK, b"MARK!!")

    # memory
    def w(self, off, data, seg=DS):
        self.mu.mem_write(seg * 16 + off, bytes(data))

    def r(self, off, n, seg=DS):
        return bytes(self.mu.mem_read(seg * 16 + off, n))

    def word(self, off, seg=DS):
        return struct.unpack("<H", self.r(off, 2, seg))[0]

    def slots(self):
        raw = self.r(self.bag, 4 * self.total)
        return [struct.unpack_from("<HBB", raw, 4 * i) for i in range(self.total)]

    def items(self):
        """[(slot, item, count)] of the used slots."""
        return [(i, w & 0x7FF, c) for i, (w, c, _f) in enumerate(self.slots()) if (w & 0x7FF) != 0x7FF]

    # calls
    def far(self, seg, off, args=(), until_ret=True):
        """call seg:off far with args as [bp+6], [bp+8], ...; -> ax, dx"""
        sp = STACK - 4 - 2 * len(args)
        self.w(sp, struct.pack("<2H", 0, SENT) + b"".join(struct.pack("<H", a & 0xFFFF) for a in args))
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, seg), (X.UC_X86_REG_IP, off), (X.UC_X86_REG_SP, sp),
                       (X.UC_X86_REG_BP, 0), (X.UC_X86_REG_SI, 0), (X.UC_X86_REG_DI, 0)):
            self.mu.reg_write(reg, v)
        try:
            self.mu.emu_start(seg * 16 + off, SENT * 16, count=20_000_000)
        except Exception as e:
            cs, ip = self.mu.reg_read(X.UC_X86_REG_CS), self.mu.reg_read(X.UC_X86_REG_IP)
            raise RuntimeError(f"{seg - LOAD:04X}:{off:04X} stopped at {cs - LOAD:04X}:{ip:04X} "
                               f"({bytes(self.mu.mem_read(cs * 16 + ip, 6)).hex(' ')}): {e}") from None
        if self.mu.reg_read(X.UC_X86_REG_CS) != SENT:
            raise RuntimeError(f"{seg - LOAD:04X}:{off:04X} did not come back")
        if self.word(FATAL) != 1 and self.mu.reg_read(X.UC_X86_REG_SP) != STACK:
            raise RuntimeError(f"{seg - LOAD:04X}:{off:04X} left the stack at {self.mu.reg_read(X.UC_X86_REG_SP):04X}")
        return self.mu.reg_read(X.UC_X86_REG_AX), self.mu.reg_read(X.UC_X86_REG_DX)

    def new_game(self):
        self.w(FATAL, bytes(2))
        self.far(OV8, 0x1474)

    def give(self, item, n=1):
        self.w(SILENT, struct.pack("<H", 1))
        self.w(FATAL, bytes(2))
        return self.far(CS25, 0xCE6C, (-1, n, item))[0]

    def take(self, item, n=1):
        return self.far(CS25, 0xCEFC, (n, item))[0]

    def count(self, item):
        return self.far(CS25, 0xCE2A, (item,))[0]

    def used(self):
        return self.far(CS25, 0xD84C)[0]

    def listed(self, n):
        ax, dx = self.far(CS25, 0xD86E, (0, 0, n, 0))
        k = self.word(ax, dx)
        raw = self.r(ax + 2, 4 * k, dx)
        return [struct.unpack_from("<H", raw, 4 * i)[0] & 0x7FF for i in range(k)]

    def pack(self):
        self.far(CS25, 0xD9F8)

    def file_io(self, calls, data=None):
        """the save routines in order, each (seg, off) called with FILE = DS:F900 -> results; data = file to read"""
        self.w(FPOS, bytes(2))
        if data is not None:
            self.w(0, data, FSEG)
            self.w(FLEN, struct.pack("<H", len(data)))
        else:
            self.w(FLEN, bytes(2))
        out = [self.far(seg, off, (0xF900, DS))[0] for seg, off in calls]
        return out, self.r(0, self.word(FLEN if data is None else FPOS), FSEG)


def save_calls(g):
    return [(CS25, 0xDBE4), (CS25, 0xDE24), (CS25, 0xDBFA) if g.expanded else (CS358, B.SAVE_LAST)]


def load_calls(g):
    return [(CS25, 0xDC04), (CS25, 0xDE44), (CS25, 0xDC1A) if g.expanded else (CS358, B.LOAD_LAST)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    a = ap.parse_args()
    if a.image:
        from fat12 import Fat12, open_hdi
        _raw, _hdr, disk, part = open_hdi(a.image)
        fs = Fat12(disk, part)
        e = fs.find("DDS98/" + B.FILE)
        fixed = bytes(fs.read_chain(e["cluster"], e["size"]))
        check(B.state(fixed) == "fixed", f"{a.image}: the expansion is in")
        orig = B.apply_to(fixed, revert=True)
    else:
        orig = open(B.SRC, "rb").read()
        check(B.state(orig) == "orig", "files/DDS98: the original")
        fixed = B.apply_to(orig)

    print("the file")
    check(len(orig) == len(fixed), "same length")
    check(B.apply_to(fixed) == fixed, "apply_to is idempotent")
    check(B.apply_to(fixed, revert=True) == orig, "revert gives the original back")
    path = os.path.join(WORK, "build", "_bagexpand_test.exe")
    with open(path, "wb") as f:
        f.write(orig)
    try:
        m, ovs = MZ(path), overlays(path)
    finally:
        os.remove(path)
    root_relocs = {m.hdr + p for p in m.reloc_set}
    ov_relocs = {ov.file_off + ov.hdr + p for ov in ovs.values() for p in ov.relocs}
    expected = {B._file("ov03", at + 3) for at, _l, _e, _w in B.OV03_CALLS}
    touched = set()
    for _why, fo, old, new in B.SITES:
        for i in range(len(old)):
            if old[i] != new[i]:
                touched.add(fo + i)
    relocated = {p for p in root_relocs | ov_relocs if p in touched or p + 1 in touched}
    check(relocated == expected, f"relocated words changed: {sorted(hex(p) for p in relocated)} (the two ov03 calls)")

    go, gx = Game(orig, False), Game(fixed, True)
    print("new game (ov08:1474)")
    for g in (go, gx):
        g.w(g.bag, b"\x00" * 4 * g.total)
        g.new_game()
        sl = g.slots()
        check(all(w == 0x7FF and c == 0 and f == 0 for w, c, f in sl), f"{g.total} slots empty")

    print("single items (swords)")
    for g in (go, gx):
        g.new_game()
        added = [g.give(s) for s in SWORDS[:g.normal + 1]]
        check(added == [1] * g.normal + [0], f"{g.normal} go in, the next one does not")
        its = g.items()
        check([s for s, _i, _c in its] == list(range(g.normal)) and all(c == 1 for _s, _i, c in its),
              f"slots 0-{g.normal - 1}, one each")
        check(g.used() == g.normal, f"used slots {g.used()}")
        check(g.listed(0x40 if not g.expanded else 0x7F) == SWORDS[:g.normal], "D86E lists them all, in order")
        check(g.count(SWORDS[g.normal - 1]) == 1 and g.count(SWORDS[g.normal]) == 0, "counting")

    print("stacks, taking, packing")
    for g in (go, gx):
        g.new_game()
        check(g.give(CONSUMABLE, 250) == 250 and [c for _s, _i, c in g.items()] == [99, 99, 52], "250 = 99 + 99 + 52")
        for s in SWORDS[:g.normal - 3]:
            g.give(s)
        check(g.used() == g.normal, "full")
        check(g.take(CONSUMABLE, 120) == 120 and g.count(CONSUMABLE) == 130, "take 120 of them (CEFC: how many)")
        for s in SWORDS[:g.normal - 3:2]:
            g.take(s)
        before = [i for _s, i, _c in g.items()]
        g.pack()
        its = g.items()
        check([s for s, _i, _c in its] == list(range(len(its))) and [i for _s, i, _c in its] == before,
              f"packed: {len(its)} items in slots 0-{len(its) - 1}, same order")

    print("merging stacks, walking the used slots")
    for g in (go, gx):
        g.new_game()
        far_slot = g.normal - 2
        for i, (item, n) in ((0, (CONSUMABLE, 50)), (5, (SWORDS[0], 1)), (far_slot, (CONSUMABLE, 30))):
            g.w(g.bag + 4 * i, struct.pack("<HBB", item, n, 0))
        g.give(SWORDS[1])
        its = g.items()
        check([c for _s, i, c in its if i == CONSUMABLE] == [80], f"slots 0 and {far_slot}: one stack of 80 after "
              "the next add (D4AE merges through D2C2)")
        g.new_game()
        for i in (3, far_slot - 1):
            g.w(g.bag + 4 * i, struct.pack("<HBB", SWORDS[i], 1, 0))
        nxt = [g.far(CS25, 0xD7C2, (k,))[0] for k in (0, 4, far_slot)]
        check(nxt == [3, far_slot - 1, 0xFFFF], f"D7C2 from 0 / 4 / {far_slot}: {nxt}")

    print("恋人の部位 (kind 10)")
    for g in (go, gx):
        g.new_game()
        for s in SWORDS[:10]:
            g.give(s)
        for p in PARTS[:16]:
            g.give(p)
        its = g.items()
        part_slots = [s for s, i, _c in its if i in PARTS]
        check(part_slots == list(range(g.normal, g.total)), f"16 parts in slots {g.normal}-{g.total - 1}")
        check(g.word(FATAL) == 0, "no fatal error")
        g.give(PARTS[16])
        check(g.word(FATAL) == 1, "the 17th: 「シナリオアイテムバッファが一杯です」")
        g.new_game()
        for s in SWORDS[:g.normal]:
            g.give(s)
        g.give(PARTS[0])
        check(any(i == PARTS[0] and s == g.normal for s, i, _c in g.items()), "a part goes in when the rest is full")
        g.take(SWORDS[3])
        g.give(SWORDS[g.normal + 5])
        check(any(i == SWORDS[g.normal + 5] for _s, i, _c in g.items()) and g.used() == g.normal + 1,
              "a freed ordinary slot takes the next sword")

    print("command 2E6 (25CA:D96E)")
    rnd = random.Random(98)
    for g in (go, gx):
        g.new_game()
        for s in rnd.sample(SWORDS, g.normal - 4):
            g.give(s)
        g.give(CONSUMABLE, 40)
        for p in PARTS[:5]:
            g.give(p)
        before = g.slots()
        g.w(COPY, b"\xcc" * 256)
        g.far(CS25, 0xD96E, (0, COPY, DS))
        copy = g.r(COPY, 256)
        want = b"".join(struct.pack("<HBB", *e) for e in before[:48] + before[g.normal:g.normal + 16])
        check(copy == want, "the copy is slots 0-47 and the 16 scenario slots")
        g.new_game()
        check(g.used() == 0, "emptied")
        g.far(CS25, 0xD96E, (1, COPY, DS))
        check(g.slots() == before, "restored: the same bag")

    print("saves")
    rnd = random.Random(1998)
    for g in (go, gx):
        g.new_game()
        for s in rnd.sample(SWORDS, g.normal - 6):
            g.give(s)
        g.give(CONSUMABLE, 120)
        for p in PARTS[:4]:
            g.give(p)
    res, file_x = gx.file_io(save_calls(gx))
    check(res == [0, 0, 0], f"expanded save: results {res}")
    check(len(file_x) == 256 + 64 + 6 + 2 * 252, f"expanded save: {len(file_x)} bytes (64 + 16 gems + marker + tail)")
    want = b"".join(struct.pack("<HBB", *e) for e in gx.slots()[:48] + gx.slots()[B.NORMAL:])
    check(file_x[:256] == want, "the 64-entry block in its place: slots 0-47 and the scenario slots")
    saved = gx.slots()
    gx.new_game()
    gx.w(MARKIN, bytes(6))
    res, _ = gx.file_io(load_calls(gx), file_x)
    check(res == [0, 0, 0] and gx.slots() == saved and gx.r(MARKIN, 6) == b"MARK!!",
          "expanded load: the same bag, the marker read")

    res, file_o = go.file_io(save_calls(go))
    check(res == [0, 0, 0] and len(file_o) == 256 + 64 + 6, f"original save: {len(file_o)} bytes")
    gx.new_game()
    gx.w(MARKIN, bytes(6))
    res, _ = gx.file_io(load_calls(gx), file_o)
    o = go.slots()
    want = o[:48] + [(0x7FF, 0, 0)] * B.EXT_N + o[48:]
    check(res == [0, 0, 0] and gx.slots() == want and gx.r(MARKIN, 6) == b"MARK!!",
          "an original save in the expanded game: slots 48-110 empty, the rest in place")

    go.new_game()
    go.w(MARKIN, bytes(6))
    res, _ = go.file_io(load_calls(go), file_x)
    want = saved[:48] + saved[B.NORMAL:]
    check(res == [0, 0, 0] and go.slots() == want and go.r(MARKIN, 6) == b"MARK!!",
          "an expanded save in the original game: the first 48 and the scenario slots")

    print("the 2E6 copy across a save")
    g = gx
    g.new_game()
    for s in SWORDS[:100]:
        g.give(s)
    before = g.slots()
    g.far(CS25, 0xD96E, (0, COPY, DS))
    copy = g.r(COPY, 256)
    g.new_game()
    res, file_b = g.file_io(save_calls(g))
    g.w(B.EXTBK, b"\xee" * 4 * B.EXT_N)
    res, _ = g.file_io(load_calls(g), file_b)
    g.w(COPY, copy)
    g.far(CS25, 0xD96E, (1, COPY, DS))
    check(g.slots() == before, "items taken by 2E6, saved and loaded, then given back: the same bag")

    print("FAILED" if fails else "all passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
