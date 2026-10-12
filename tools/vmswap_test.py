#!/usr/bin/env python3
"""vmswap_test.py - tools/vmswap.py on an emulated CPU (unicorn): the recovery 0871:94C4 of the original DDS98.EXE
(the swap file) and of the fixed one (XMS) run side by side on the same virtual memory. Every routine they call
that is not their own is answered by a model: the handle table at [616A] (the game's layout: +0 bit 0 in use, +2
the size, +4/+6 the block's address), lock / free / allocate / shut down / start afresh (0871:1E0C 5FC8 5DAE 12FC
1AF2), the unlocking at the start (20A8 1FE4), the caller's handle (9904), [10D0]'s relock (617E 6124), the path
(9128), the C run-time's fopen / fwrite / fread / fclose / printf / exit, and an XMS driver at [974C] (09h
allocate, 0Ah free, 0Bh move, which refuses odd lengths and moves past either end).

  * the same blocks in use - odd, even, empty and 0FFFAh-byte ones, some locked twice - come back in both: every
    new block holds its old bytes, the table points at the new blocks, the caller's pointer and [10D0]'s relock as
    in the original, si di bp sp kept; the fixed one opens no file, asks for [9710] + 1 KB, frees its XMS block,
    and every move stays inside a block's even room (the guard bytes around each are untouched);
  * every failure ends both with the same message and exit(1): fwopen (no file / no XMS block, or a memory
    without XMS for the fixed one), recover-r, dsk, init, recover-w, size;
  * the file: only 956C-9753 changes, every relocated word in it keeps its bytes, apply_to is idempotent and
    revert gives the original back.

    vmswap_test.py [--image HDI]

With an image, its DDS98.EXE is the fixed program (with every other fix of the build) and the same file with this
fix taken out the original.
"""
import argparse
import os
import random
import struct
import sys

from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import vmswap  # noqa: E402
from mz import MZ  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP
CS0871 = LOAD + 0x0871
SP0 = 0xFF00
HT = 0x7000                             # the handle table's segment
PTR = HT * 16 + 0x2100                  # the caller's pointer (a block address) for kind != 0
ARENA, ARENA_END = 0x73000, 0xE0000     # locked blocks' rooms
XMSSEG = 0xE000                         # the XMS driver's entry
SENT = 0xF000
GUARD = 16
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def load(blob):
    path = os.path.join(WORK, "build", "_vmswap_test.exe")
    with open(path, "wb") as f:
        f.write(blob)
    try:
        return bytes(MZ(path, base=LOAD).image), MZ(path).reloc_set
    finally:
        os.remove(path)


def even(n):
    return n + (n & 1)


class Run:
    """One call of 94C4 on a fresh copy of a scenario: sizes {handle: size}, locks {handle: count}, data {handle:
    bytes of its even room}, fail {kind: n} (the n-th such event fails), xms (the memory keeps its pages in XMS),
    caller (a handle for kind != 0, else None), relock ([10D0])."""

    def __init__(self, img, sc, fail=None):
        self.sc, self.fail = sc, dict(fail or {})
        self.counts = {}
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_16)
        mu.mem_map(0, 0x110000)
        mu.mem_write(LOAD * 16, img)
        mu.mem_write(SENT * 16, b"\xf4")
        mu.mem_write(XMSSEG * 16, b"\xcb")
        self.blocks = {}                # address -> {"size", "data", "locks", "freed", "room"}
        self.addr = 0x00100000
        self.arena = ARENA
        self.rooms = []                 # (linear, length) of every room handed out, guards around it
        for h, size in sc["sizes"].items():
            a = self._new_block(size, sc["data"][h])
            self.blocks[a]["locks"] = sc["locks"].get(h, 0)
            mu.mem_write(HT * 16 + 8 * h, struct.pack("<HHI", 1, size, a))
        self.w16(DS * 16 + 0x616A, HT)
        self.w16(DS * 16 + 0x10D6, 0)
        self.w16(DS * 16 + 0x10D0, sc["relock"] or 0)
        mu.mem_write(DS * 16 + 0x970C, bytes([1 if sc["xms"] else 0]))
        total = sum(even(s) for s in sc["sizes"].values())
        self.kb = total // 1024 + 3     # the memory's XMS block: every page, some room to spare
        self.w16(DS * 16 + 0x9710, self.kb)
        mu.mem_write(DS * 16 + 0x974C, struct.pack("<HH", 0, XMSSEG))
        if sc["caller"]:
            h = sc["caller"]
            mu.mem_write(PTR, struct.pack("<I", struct.unpack_from("<I", mu.mem_read(HT * 16 + 8 * h + 4, 4))[0]))
        self.file = None
        self.files = []
        self.xms = {}
        self.xms_next = 0x10
        self.xms_asked = []
        self.moves = []
        self.calls = []
        self.printed = []
        self.exited = None
        stubs = {
            (CS0871, 0x1E0C): self.lock, (CS0871, 0x5FC8): self.free, (CS0871, 0x12FC): self.shutdown,
            (CS0871, 0x1AF2): self.start, (CS0871, 0x5DAE): self.alloc, (CS0871, 0x20A8): self.locked,
            (CS0871, 0x1FE4): self.unlock, (CS0871, 0x9904): self.handle_of, (CS0871, 0x617E): self.relock,
            (CS0871, 0x6124): self.relock2, (CS0871, 0x9128): self.path, (LOAD, 0x03A0): self.fopen,
            (LOAD, 0x0570): self.fwrite, (LOAD, 0x03FC): self.fread, (LOAD, 0x029E): self.fclose,
            (LOAD, 0x0708): self.printf, (LOAD, 0x01EB): self.exit, (XMSSEG, 0): self.xmsdrv}
        for (seg, off), fn in stubs.items():
            mu.hook_add(UC_HOOK_CODE, self._hook(fn), begin=seg * 16 + off, end=seg * 16 + off)

    # ---- plumbing
    def w16(self, lin, v):
        self.mu.mem_write(lin, struct.pack("<H", v & 0xFFFF))

    def r16(self, lin):
        return struct.unpack("<H", self.mu.mem_read(lin, 2))[0]

    def arg(self, n):
        """The n-th word above the return address (far: 2 words of it)."""
        mu = self.mu
        return self.r16(mu.reg_read(X.UC_X86_REG_SS) * 16 + mu.reg_read(X.UC_X86_REG_SP) + 2 * n)

    def _hook(self, fn):
        def hook(_mu, _addr, _size, _ud):
            fn()
        return hook

    def ret(self, far, pop, ax=None, dx=None):
        mu = self.mu
        ss, sp = mu.reg_read(X.UC_X86_REG_SS), mu.reg_read(X.UC_X86_REG_SP)
        ip = self.r16(ss * 16 + sp)
        if far:
            cs = self.r16(ss * 16 + sp + 2)
            mu.reg_write(X.UC_X86_REG_SP, sp + 4 + pop)
            mu.reg_write(X.UC_X86_REG_CS, cs)
        else:
            mu.reg_write(X.UC_X86_REG_SP, sp + 2 + pop)
        if ax is not None:
            mu.reg_write(X.UC_X86_REG_AX, ax & 0xFFFF)
        if dx is not None:
            mu.reg_write(X.UC_X86_REG_DX, dx & 0xFFFF)
        mu.reg_write(X.UC_X86_REG_IP, ip)

    def failing(self, kind):
        n = self.counts[kind] = self.counts.get(kind, 0) + 1
        return self.fail.get(kind) == n

    def _new_block(self, size, data=None):
        a = self.addr
        self.addr += 0x10000
        self.blocks[a] = {"size": size, "data": bytearray(data if data is not None else bytes(even(size))),
                          "locks": 0, "freed": False, "room": None}
        return a

    # ---- the memory's routines
    def lock(self):                     # 1E0C(flag, address): far pointer to the block's room
        a = self.arg(3) | self.arg(4) << 16
        b = self.blocks[a]
        if self.failing("lock"):
            return self.ret(True, 6, 0, 0)
        if b["room"] is None:
            room = self.arena + GUARD
            self.arena = room + even(b["size"]) + GUARD
            if self.arena > ARENA_END:
                raise RuntimeError("the arena is full")
            self.mu.mem_write(room - GUARD, b"\xa5" * GUARD)
            self.mu.mem_write(room, bytes(b["data"]))
            self.mu.mem_write(room + even(b["size"]), b"\x5a" * GUARD)
            self.rooms.append((room, even(b["size"])))
            b["room"] = room
        b["locks"] += 1
        room = b["room"]
        return self.ret(True, 6, room & 0xF, room >> 4)

    def free(self):                     # 5FC8(address)
        a = self.arg(2) | self.arg(3) << 16
        self.blocks[a]["freed"] = True
        self.calls.append(("free", a))
        self.ret(True, 4)

    def shutdown(self):                 # 12FC
        self.calls.append(("shutdown", sorted(a for a, b in self.blocks.items() if not b["freed"])))
        self.ret(True, 0)

    def start(self):                    # 1AF2(7, 1100h, FFFh)
        args = (self.arg(2), self.arg(3), self.arg(4))
        self.calls.append(("start", args))
        self.ret(True, 6, 0 if self.failing("start") else 1)

    def alloc(self):                    # 5DAE(size): a new block's address
        size = self.arg(2) | self.arg(3) << 16
        a = self._new_block(size)
        self.ret(True, 4, a & 0xFFFF, a >> 16)

    def locked(self):                   # 20A8(address)
        a = self.arg(2) | self.arg(3) << 16
        self.ret(True, 4, 1 if self.blocks[a]["locks"] > 0 else 0)

    def unlock(self):                   # 1FE4(n, address)
        a = self.arg(3) | self.arg(4) << 16
        self.blocks[a]["locks"] -= self.arg(2)
        self.ret(True, 6)

    def handle_of(self):                # 9904(address): its handle (near, ret 4)
        a = self.arg(1) | self.arg(2) << 16
        for h in range(1, 0x400):
            if struct.unpack_from("<I", self.mu.mem_read(HT * 16 + 8 * h + 4, 4))[0] == a:
                return self.ret(False, 4, h)
        self.ret(False, 4, 0)

    def relock(self):                   # 617E(n, address)
        self.calls.append(("617E", self.arg(2), self.arg(3) | self.arg(4) << 16))
        self.ret(True, 6)

    def relock2(self):                  # 6124(address)
        self.calls.append(("6124", self.arg(2) | self.arg(3) << 16))
        self.ret(True, 4)

    def path(self):                     # 9128(n): DS:6CF6, "vm\v0000.buf" (near, ret 2)
        self.mu.mem_write(DS * 16 + 0x6CF6, b"vm\\v0000.buf\0")
        self.ret(False, 2, 0x6CF6, DS)

    # ---- the C run-time
    def _cstr(self, seg, off):
        s = bytes(self.mu.mem_read(seg * 16 + off, 64))
        return s.split(b"\0")[0].decode("ascii", "replace")

    def fopen(self):
        name, mode = self._cstr(self.arg(3), self.arg(2)), self._cstr(self.arg(5), self.arg(4))
        self.files.append((name, mode))
        if self.failing("fopen"):
            return self.ret(True, 0, 0, 0)
        if mode.startswith("w"):
            self.file = bytearray()
        self.pos = 0
        self.ret(True, 0, 0x4AC4, DS)

    def fwrite(self):                   # fwrite(ptr, size, n, fp)
        ptr = self.arg(3) * 16 + self.arg(2)
        n = self.arg(4) * self.arg(5)
        self.file += bytes(self.mu.mem_read(ptr, n))
        self.ret(True, 0, self.arg(5) - (1 if self.failing("write") else 0))

    def fread(self):
        ptr = self.arg(3) * 16 + self.arg(2)
        n = self.arg(4) * self.arg(5)
        self.mu.mem_write(ptr, bytes(self.file[self.pos:self.pos + n]))
        self.pos += n
        self.ret(True, 0, self.arg(5) - (1 if self.failing("read") else 0))

    def fclose(self):
        self.ret(True, 0, 0)

    def printf(self):
        self.printed.append(self._cstr(self.arg(3), self.arg(2)))
        self.ret(True, 0, 0)

    def exit(self):
        self.exited = self.arg(2)
        self.mu.emu_stop()

    # ---- the XMS driver
    def xmsdrv(self):
        mu = self.mu
        ah = mu.reg_read(X.UC_X86_REG_AX) >> 8
        if ah == 0x09:
            kb = mu.reg_read(X.UC_X86_REG_DX)
            self.xms_asked.append(kb)
            if self.failing("xalloc"):
                mu.reg_write(X.UC_X86_REG_BX, 0xA0)
                return self.ret(True, 0, 0)
            h = self.xms_next
            self.xms_next += 1
            self.xms[h] = bytearray(kb * 1024)
            return self.ret(True, 0, 1, h)
        if ah == 0x0A:
            ok = self.xms.pop(mu.reg_read(X.UC_X86_REG_DX), None) is not None
            return self.ret(True, 0, 1 if ok else 0)
        if ah == 0x0B:
            lin = mu.reg_read(X.UC_X86_REG_DS) * 16 + mu.reg_read(X.UC_X86_REG_SI)
            length, sh, so, dh, do = struct.unpack("<IHIHI", bytes(mu.mem_read(lin, 16)))
            self.moves.append((length, sh, so, dh, do))
            fail = self.failing("move") or length & 1
            for h, o in ((sh, so), (dh, do)):
                if h and (h not in self.xms or o + length > len(self.xms[h])):
                    fail = True
                if not h:
                    a = (o >> 16) * 16 + (o & 0xFFFF)
                    if not any(r <= a and a + length <= r + n for r, n in self.rooms):
                        fail = True
            if fail:
                mu.reg_write(X.UC_X86_REG_BX, 0xA7)
                return self.ret(True, 0, 0)
            if sh:
                data = bytes(self.xms[sh][so:so + length])
            else:
                data = bytes(mu.mem_read((so >> 16) * 16 + (so & 0xFFFF), length))
            if dh:
                self.xms[dh][do:do + length] = data
            else:
                mu.mem_write((do >> 16) * 16 + (do & 0xFFFF), data)
            return self.ret(True, 0, 1)
        raise RuntimeError(f"XMS function {ah:02X}h")

    # ---- the call
    def run(self, kind):
        mu = self.mu
        ptr = (PTR & 0xF, PTR >> 4) if kind else (0, 0)
        sp = SP0 - 10
        mu.mem_write(DS * 16 + sp, struct.pack("<5H", 0, SENT, ptr[0], ptr[1], kind))
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, CS0871), (X.UC_X86_REG_IP, 0x94C4), (X.UC_X86_REG_SP, sp),
                       (X.UC_X86_REG_BP, 0x1234), (X.UC_X86_REG_SI, 0x5A5A), (X.UC_X86_REG_DI, 0xA5A5)):
            mu.reg_write(reg, v)
        mu.emu_start(CS0871 * 16 + 0x94C4, SENT * 16, count=20_000_000)
        back = mu.reg_read(X.UC_X86_REG_CS) == SENT
        regs = (mu.reg_read(X.UC_X86_REG_SI), mu.reg_read(X.UC_X86_REG_DI), mu.reg_read(X.UC_X86_REG_BP),
                mu.reg_read(X.UC_X86_REG_SP))
        return back, regs

    def outcome(self):
        """What a run left: per handle its size and the bytes of its block, the caller's pointer's block, the
        relock calls, the message and exit code."""
        table = {}
        for h in range(1, 0x400):
            flags, size, a = struct.unpack("<HHI", bytes(self.mu.mem_read(HT * 16 + 8 * h, 8)))
            if flags & 1:
                b = self.blocks.get(a)
                room = b["room"] if b else None
                data = bytes(self.mu.mem_read(room, size)) if room is not None else None
                table[h] = (size, a, data)
        caller = struct.unpack("<I", bytes(self.mu.mem_read(PTR, 4)))[0]
        relocks = [c for c in self.calls if c[0] in ("617E", "6124")]
        return table, caller, relocks, self.printed, self.exited

    def guards_whole(self):
        mu = self.mu
        return all(bytes(mu.mem_read(r - GUARD, GUARD)) == b"\xa5" * GUARD and
                   bytes(mu.mem_read(r + n, GUARD)) == b"\x5a" * GUARD for r, n in self.rooms)


def scenario(rng, n=40, xms=True, caller=True, relock=True, big=True):
    handles = rng.sample(range(1, 0x400), n)
    sizes = {}
    for k, h in enumerate(handles):
        sizes[h] = (0 if k == 0 else 0xFFFA if big and k == 1 else rng.choice((1, 2, 3, 7, 8)) if k < 8
                    else rng.randrange(1, 3000))
    data = {h: bytes(rng.randrange(256) for _ in range(even(s))) for h, s in sizes.items()}
    locks = {h: rng.choice((0, 0, 1, 2)) for h in handles}
    return {"sizes": sizes, "data": data, "locks": locks, "xms": xms,
            "caller": handles[5 % n] if caller else None, "relock": handles[6 % n] if relock else None}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    a = ap.parse_args()
    if a.image:
        from fat12 import Fat12, open_hdi
        _raw, _hdr, disk, part = open_hdi(a.image)
        fs = Fat12(disk, part)
        e = fs.find("DDS98/" + vmswap.FILE)
        fixed = bytes(fs.read_chain(e["cluster"], e["size"]))
        check(vmswap.state(fixed) == "fixed", f"{a.image}: the fix is in")
        orig = vmswap.apply_to(fixed, revert=True)
    else:
        orig = open(vmswap.SRC, "rb").read()
        check(vmswap.state(orig) == "orig", "files/DDS98: the original")
        fixed = vmswap.apply_to(orig)

    print("the file")
    lo, hi = vmswap.at(vmswap.START), vmswap.at(vmswap.END)
    diff = [i for i in range(len(orig)) if orig[i] != fixed[i]]
    check(len(orig) == len(fixed) and all(lo <= i < hi for i in diff),
          f"{len(diff)} bytes differ, all inside {vmswap.SEG:04X}:{vmswap.START:04X}-{vmswap.END:04X}")
    img_o, relocs = load(orig)
    img_f, relocs_f = load(fixed)
    gaps = vmswap.holes()
    check(relocs == relocs_f and all(fixed[vmswap.at(g):vmswap.at(g) + 2] == orig[vmswap.at(g):vmswap.at(g) + 2]
                                     for g in gaps),
          f"the relocation table is the same and the {len(gaps)} relocated words in the window keep their bytes")
    check(vmswap.apply_to(fixed) == fixed, "apply_to is idempotent")
    check(vmswap.apply_to(fixed, revert=True) == orig, "revert gives the original back")

    rng = random.Random(1997)
    print("the blocks come back")
    for trial in range(12):
        sc = scenario(rng, n=rng.choice((1, 5, 40, 120)), caller=trial % 3 != 2, relock=trial % 2 == 0,
                      big=trial % 4 == 0)
        ro, rf = Run(img_o, sc), Run(img_f, sc)
        kind = 3 if sc["caller"] else 0
        bo, regs_o = ro.run(kind)
        bf, regs_f = rf.run(kind)
        oo, of = ro.outcome(), rf.outcome()
        want = {h: bytes(sc["data"][h][:s]) for h, s in sc["sizes"].items()}
        same_data = all(of[0][h][2] == want[h] for h in want) and all(oo[0][h][2] == want[h] for h in want)
        ok = (bo and bf and oo == of and same_data and regs_o == regs_f == (0x5A5A, 0xA5A5, 0x1234, SP0)
              and set(of[0]) == set(sc["sizes"]) and rf.files == [] and rf.xms == {}
              and rf.xms_asked == [rf.kb + 1] and rf.guards_whole() and ro.guards_whole()
              and all(m[0] % 2 == 0 for m in rf.moves)
              and len(rf.moves) == 2 * sum(1 for s in sc["sizes"].values() if s))
        check(ok, f"{len(sc['sizes'])} blocks ({sum(sc['sizes'].values())} bytes, "
                  f"{'caller ' if sc['caller'] else ''}{'relock ' if sc['relock'] else ''}"
                  f"{'0FFFAh ' if 0xFFFA in sc['sizes'].values() else ''}): the same as the original, "
                  f"{len(rf.moves)} XMS moves")
        if not ok:
            print(f"      back {bo} {bf}, regs {regs_o} {regs_f}, files {rf.files}, xms left {list(rf.xms)}, "
                  f"asked {rf.xms_asked} (kb {rf.kb}), printed {ro.printed} {rf.printed}, handles "
                  f"{set(of[0]) == set(sc['sizes'])}, guards {ro.guards_whole()} {rf.guards_whole()}, even moves "
                  f"{all(m[0] % 2 == 0 for m in rf.moves)}")
            for k, (x, y) in enumerate(zip(oo, of)):
                if x != y:
                    print(f"      outcome part {k} differs: original {x!r:.300} / fixed {y!r:.300}")
            for h in want:
                if of[0][h][2] != want[h] or oo[0][h][2] != want[h]:
                    print(f"      handle {h:03X} size {sc['sizes'][h]}: want {want[h].hex()[:40]}, original "
                          f"{(oo[0][h][2] or b'').hex()[:40]}, fixed {(of[0][h][2] or b'').hex()[:40]}")
    sc = scenario(rng, n=1)
    sc["sizes"], sc["data"], sc["locks"] = {}, {}, {}
    sc["caller"] = sc["relock"] = None
    ro, rf = Run(img_o, sc), Run(img_f, sc)
    bo, _ = ro.run(0)
    bf, _ = rf.run(0)
    check(bo and bf and rf.xms == {} and rf.xms_asked == [rf.kb + 1] and not rf.moves,
          "no block in use: both finish, the XMS block is had and given back")

    print("failures")
    # 20 blocks, the first empty: 20 locks and 19 moves out, then 20 locks and 19 moves back
    cases = [("fwopen", {"fopen": 1}, {"xalloc": 1}), ("recover-r", {"lock": 3}, {"lock": 3}),
             ("dsk", {"write": 4}, {"move": 4}), ("init", {"start": 1}, {"start": 1}),
             ("recover-w", {"lock": 23}, {"lock": 23}), ("size", {"read": 5}, {"move": 24})]
    for name, fail_o, fail_f in cases:
        sc = scenario(random.Random(name), n=20, big=False, caller=False, relock=False)
        sc["locks"] = {}
        ro, rf = Run(img_o, sc, fail_o), Run(img_f, sc, fail_f)
        ro.run(0)
        rf.run(0)
        text = f"VM double fault({name})\n" if name != "init" else "vm double fault(init)\n"
        ok = ro.printed == rf.printed == [text] and ro.exited == rf.exited == 1
        check(ok, f"{name}: both print 「{text.strip()}」 and exit(1)")
        if not ok:
            print(f"      original {ro.printed} {ro.exited}, fixed {rf.printed} {rf.exited}")
    sc = scenario(random.Random("noxms"), n=10, xms=False, caller=False, relock=False)
    rf = Run(img_f, sc)
    rf.run(0)
    check(rf.printed == ["VM double fault(fwopen)\n"] and rf.exited == 1 and rf.xms_asked == [],
          "a memory without XMS: the fixed one prints fwopen and exits, asking XMS for nothing")
    print(f"\n{fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
