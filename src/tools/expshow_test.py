#!/usr/bin/env python3
"""expshow_test.py - 经验值显示修复 on an emulated CPU (unicorn): the value the summary's experience line
prints against what the payout really adds to each member, in the original DDS98.EXE and with
tools/expshow.py's sites in.

The reader of script operands of kind 4Fh, 1603:A71C (index in [bp+4], result in dx:ax, ret 2), and the
payout's share-out, ov02:0000 (the sum in [bp+4]/[bp+6], ret 4; overlay 2 loaded and relocated by the
load segment), are each entered with a near return address that stops the run. Six party slots are
staged as records (id, level +6Bh, experience +6Eh, status bits +156h); only the slot lookup 358E:514C is
replaced, by a stub that hands out their addresses - the head count 358E:4B7C, the status test and the
C run-time's long division run as shipped. Checks:
  * with the fix, index 4 is what ov02:0000 adds to every member who takes a share, for parties of one
    to six, with members dead, turned to stone, poisoned, asleep, at level 99, marked 灰 (which the
    original's status test lets through - its code is 0 - and 能力值修复 keeps out), and sums above FFFFh;
    it is 0 for a sum of 0 and when nobody can take a share (where the original ov02:0000 divides by
    zero and one with 能力值修复 pays nobody);
  * in the original, index 4 gives 0;
  * indexes 0-3 (Macca, MAG, the sum, the dropped item) and 5 give the same in both programs;
  * the program differs from the original at the two sites alone, none of whose bytes a relocation
    touches, and expshow.mend_exe(..., revert=True) gives the original file back.

    expshow_test.py [--image HDI]

With an image, the DDS98.EXE in it is the mended program - every other fix of the build in it too -
and the same file with this fix taken out (expshow.mend_exe(..., revert=True)) the original.
"""
import os
import struct
import sys

from unicorn import UC_ARCH_X86, UC_MODE_16, Uc, UcError
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import expshow  # noqa: E402
import statfix  # noqa: E402
from asm86 import assemble  # noqa: E402
from mz import MZ, overlays  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP
SP = 0xAB00                             # inside the startup stack
OV, REC = 0x8000, 0xA000                # overlay 2, the staged records
TABLE = 0xF000                          # DGROUP: the six far pointers the stub hands out
STOP = 0xFFF0                           # the near return address a run stops at
READER, SHARE_OUT = (LOAD + 0x1603, 0xA71C), (OV, 0x0000)
STATUS = {"灰": 0, "死": 1, "瀕死": 2, "昏倒": 3, "石化": 4, "麻痺": 5, "凍結": 6, "眠り": 0x0D, "毒": 0x0F}
EXCLUDING = (2, 1, 0, 3, 4, 5, 6)       # DS:2426, in its order
fails = 0


def takes_share(statuses, level, ash_fixed):
    """ov02:0000's test, as 358E:3D7C/3CE4 make it: the last status of DS:2426 the member has is the
    answer, and 0 means none - so in the original 灰, whose code is 0, does not keep a member out, and
    after 死 it even lets a dead one in again; with 能力值修复 (tools/statfix.py ash_check) 灰 counts.
    Level 99 takes nothing."""
    last = 0
    for code in EXCLUDING:
        if code in {STATUS[s] for s in statuses}:
            last = code
    return last == 0 and not (ash_fixed and "灰" in statuses) and level < 99


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def image(blob):
    path = os.path.join(WORK, "build", "_expshow_test.exe")
    with open(path, "wb") as f:
        f.write(blob)
    try:
        return bytes(MZ(path, base=LOAD).image), MZ(path).reloc_set, overlays(path)[2]
    finally:
        os.remove(path)


class Game:
    def __init__(self, blob):
        img, _relocs, ov = image(blob)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x110000)
        self.mu.mem_write(LOAD * 16, img)
        ov_img = bytearray(ov.image)
        for p in ov.relocs:
            struct.pack_into("<H", ov_img, p, (struct.unpack_from("<H", ov_img, p)[0] + LOAD) & 0xFFFF)
        self.mu.mem_write(OV * 16, bytes(ov_img))
        stub = assemble(f"""
            push bp
            mov bp, sp
            mov bx, word ptr [bp + 6]
            shl bx, 1
            shl bx, 1
            mov ax, word ptr [bx + {TABLE:#x}]
            mov dx, word ptr [bx + {TABLE + 2:#x}]
            pop bp
            retf 2
        """, org=0x514C)[0]
        self.mu.mem_write((LOAD + 0x358E) * 16 + 0x514C, stub)
        self.masks = bytes(self.mu.mem_read(DS * 16 + 0x42, 8))

    def w16(self, seg, off, v):
        self.mu.mem_write(seg * 16 + off, struct.pack("<H", v & 0xFFFF))

    def stage(self, members, total):
        """members: six (id, level, experience, [status names]) or None for an empty slot."""
        for i, m in enumerate(members):
            if m is None:
                self.w16(DS, TABLE + 4 * i, 0)
                self.w16(DS, TABLE + 4 * i + 2, 0)
                continue
            ident, level, exp, statuses = m
            base = i * 0x200
            rec = bytearray(0x200)
            struct.pack_into("<H", rec, 0, ident)
            rec[0x6B] = level
            struct.pack_into("<I", rec, 0x6E, exp)
            for s in statuses:
                c = STATUS[s]
                rec[0x156 + (c >> 3)] |= self.masks[c & 7]
            self.mu.mem_write(REC * 16 + base, bytes(rec))
            self.w16(DS, TABLE + 4 * i, base)
            self.w16(DS, TABLE + 4 * i + 2, REC)
        self.mu.mem_write(DS * 16 + 0x9B0C, struct.pack("<I", total))

    def near(self, where, args):
        """Enter a near function with args (words, first pushed last in the list) under a return address
        that ends the run. -> dx:ax."""
        seg, off = where
        words = [STOP] + list(args)
        sp = SP - 2 * len(words)
        self.mu.mem_write(DS * 16 + sp, struct.pack(f"<{len(words)}H", *words))
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_SP, sp), (X.UC_X86_REG_DS, DS),
                       (X.UC_X86_REG_ES, DS), (X.UC_X86_REG_BP, 0), (X.UC_X86_REG_CS, seg),
                       (X.UC_X86_REG_IP, off)):
            self.mu.reg_write(reg, v)
        self.mu.emu_start(seg * 16 + off, seg * 16 + STOP, count=2_000_000)
        if self.mu.reg_read(X.UC_X86_REG_IP) != STOP or self.mu.reg_read(X.UC_X86_REG_CS) != seg:
            raise RuntimeError(f"run from {seg:04X}:{off:04X} did not come back")
        return (self.mu.reg_read(X.UC_X86_REG_DX) << 16) | self.mu.reg_read(X.UC_X86_REG_AX)

    def reader(self, index):
        return self.near(READER, [index])

    def exp_of(self, i):
        return struct.unpack("<I", self.mu.mem_read(REC * 16 + i * 0x200 + 0x6E, 4))[0]

    def share_out(self, total):
        return self.near(SHARE_OUT, [total & 0xFFFF, total >> 16])


if "--image" in sys.argv:
    from fat12 import Fat12, open_hdi
    _raw, _hdr, disk, part = open_hdi(sys.argv[sys.argv.index("--image") + 1])
    fs = Fat12(disk, part)
    entry = fs.find("DDS98/" + expshow.EXE)
    fixed = fs.read_chain(entry["cluster"], entry["size"])
    orig = expshow.mend_exe(fixed, revert=True)
    check(fixed == expshow.mend_exe(fixed), f"{sys.argv[sys.argv.index('--image') + 1]}: 修复已在程序里")
else:
    orig = open(os.path.join(WORK, "files", "DDS98", "DDS98.EXE"), "rb").read()
    fixed = expshow.mend_exe(orig)

print("the program")
diff = [i for i in range(len(orig)) if orig[i] != fixed[i]]
sites = [(o, o + len(a)) for o, a, _b, _w in expshow.EXE_SITES]
check(len(orig) == len(fixed) and all(any(lo <= i < hi for lo, hi in sites) for i in diff),
      f"differs from the original in {len(diff)} bytes, all inside the two sites")
_img, relocs, _ov = image(orig)
hdr = 0x3800
touched = [o for lo, hi in sites for o in range(lo - hdr - 1, hi - hdr) if o in relocs]
check(not touched, "no relocation touches a byte of either site")
check(expshow.mend_exe(fixed, revert=True) == orig, "mend_exe(..., revert=True) gives the original back")

H = (0, 10, 1000, [])                    # the hero, a human (id below 20h)
PARTY = [
    ("主人公一人", 90, [H, None, None, None, None, None]),
    ("两人", 90, [H, (0x40, 12, 5000, []), None, None, None, None]),
    ("三人", 91, [H, (1, 11, 2000, []), (0x40, 12, 5000, []), None, None, None]),
    ("满员六人", 90, [H, (1, 11, 2000, []), (2, 9, 800, []), (0x40, 12, 5000, []), (0x41, 8, 900, []),
                      (0x42, 7, 700, [])]),
    ("六人，一死一石化，一人中毒一人睡着", 97, [H, (1, 11, 2000, ["死"]), (2, 9, 800, ["毒"]),
                                            (0x40, 12, 5000, ["石化"]), (0x41, 8, 900, ["眠り"]),
                                            (0x42, 7, 700, [])]),
    ("四人，其中一人 99 级", 101, [(0, 99, 9_000_000, []), (1, 11, 2000, []), (0x40, 12, 5000, []),
                                  (0x41, 8, 900, []), None, None]),
    ("五人，总和超过 FFFFh", 123457, [H, (1, 11, 2000, []), (2, 9, 800, []), (0x40, 12, 5000, []),
                                     (0x41, 8, 900, []), None]),
    ("两人能领：空位在中间，麻痹、冻结、昏倒兼濒死各一人", 7,
     [H, None, (2, 9, 800, ["麻痺"]), (0x40, 12, 5000, ["凍結"]), (0x41, 8, 900, ["昏倒", "瀕死"]),
      (0x42, 7, 700, [])]),
    ("带灰的三人：一人只有灰、一人同时带死和灰、一人灰兼石化", 50,
     [H, (1, 11, 2000, ["灰"]), (2, 9, 800, ["死", "灰"]), (0x40, 12, 5000, ["灰", "石化"]), None, None]),
    ("三人，什么也没得到", 0, [H, (1, 11, 2000, []), (0x40, 12, 5000, []), None, None, None]),
]
NOBODY = ("全员不能领（死、石化、麻痹）", 60, [(0, 10, 1000, ["死"]), (1, 11, 2000, ["石化"]),
                                           (0x40, 12, 5000, ["麻痺"]), None, None, None])

old, new = Game(orig), Game(fixed)
ash_fixed = statfix.state(fixed) == "fixed"
print("what the summary prints against what each member gains"
      + ("（程序里有能力值修复：灰算作不能领，没人能领时不再除以零）" if ash_fixed else ""))
for name, total, members in PARTY:
    takers = [i for i, m in enumerate(members) if m and takes_share(m[3], m[1], ash_fixed)]
    new.stage(members, total)
    shown = new.reader(4)
    before = {i: new.exp_of(i) for i, m in enumerate(members) if m}
    new.share_out(total)
    gains = {i: new.exp_of(i) - before[i] for i in before}
    ok = all(gains[i] == (shown if i in takers else 0) for i in gains)
    check(ok, f"{name}：显示 {shown}；实得 " + " ".join(f"+{gains[i]}" if i in gains else "空" for i in range(6)))
    old.stage(members, total)
    check(old.reader(4) == 0, f"{name}：原版序号 4 给 0")
name, total, members = NOBODY
new.stage(members, total)
check(new.reader(4) == 0, f"{name}：显示 0")
before = {i: new.exp_of(i) for i, m in enumerate(members) if m}
try:
    new.share_out(total)
    check(ash_fixed and all(new.exp_of(i) == before[i] for i in before),
          f"{name}：发放照常结束，没有人得到经验")
except UcError as e:
    check(not ash_fixed, f"{name}：发放除以零（{e}）")
    print(f"        (没有能力值修复的程序在这里除以零：{e})")

print("the other indexes")
for name, total, members in PARTY[3:5]:
    for g in (old, new):
        g.stage(members, total)
        for off, v in ((0x9B1C, 1234), (0x9B38, 567890), (0x9900, 0x6A)):
            g.mu.mem_write(DS * 16 + off, struct.pack("<I" if off != 0x9900 else "<H", v))
    same = all(old.reader(i) == new.reader(i) for i in (0, 1, 2, 3, 5, 0x7F))
    check(same, f"{name}：序号 0、1、2、3、5、7Fh 两边相同（{[new.reader(i) for i in (0, 1, 2, 3, 5)]}）")

print("FAILED" if fails else "OK", f"({fails} failed)")
sys.exit(1 if fails else 0)
