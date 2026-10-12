#!/usr/bin/env python3
"""expgap_test.py - 等级差经验 on an emulated CPU (unicorn): the defeat's bookkeeping, the payout and the
summary's number against the rule of tools/expgap.py, with and without 能力值修复 in the program.

The programs: the original DDS98.EXE with 经验值显示修复 in (and 能力值修复, as the build has it, or
not), and the same with this patch in. Overlay 2 is loaded and relocated by the load segment; the party
slot lookup 358E:514C and the roster lookup 358E:507E are stubs handing out staged records (id, level
+6Bh, experience +6Eh, status bits +156h) - slot 0 is the protagonist, roster member 0 - and everything
else runs as shipped: the head count 358E:4B7C, the status test, ov02:0000 and ov02:005C, A71C.
A defeat is run from 25CA:AA37 to AA47 with es:si on a staged enemy (level +6Bh, experience +6Eh).
Checks:
  * the program differs from 经验值显示修复's only inside this patch's sites; no relocated word is
    touched but the segment word of the far call at ov02:0029, which stays relocated; mend_exe(...,
    revert=True) gives that program back, and a program without 经验值显示修复 is refused;
  * a defeat adds the enemy's experience to DS:9B0C as before and to its level's bucket (levels above 99
    to 99's); the first one after the sum was 0 empties stale buckets;
  * the program's factor table is round(4096 x 2^(g/5)) for g = -10..10;
  * after a battle's defeats, ov02:0000 gives each member who takes a share 2 x sum(E x F(g)) /
    (4096 N) with g = enemy level - member level held to -10..10 and F(g) = round(4096 x 2^(g/5)), and
    nothing to the others; a party level with every enemy gets what the program without the patch gives;
  * index 4 of A71C (the summary's number) is the protagonist's gain, 0 when he takes no share;
  * defeats kept over a fled fight are paid with the next one's, each at its own level.

    expgap_test.py
"""
import os
import random
import struct
import sys

from unicorn import UC_ARCH_X86, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import expgap  # noqa: E402
import expshow  # noqa: E402
import statfix  # noqa: E402
from asm86 import assemble  # noqa: E402
from mz import MZ, overlays  # noqa: E402
from storyfix import StoryFixError  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC
SP = 0xAB00
OV, REC, FOE = 0x8000, 0xA000, 0xB000
TABLE = 0xF000
STOP = 0xFFF0
READER, SHARE_OUT = (LOAD + 0x1603, 0xA71C), (OV, 0x0000)
DEFEAT = (LOAD + 0x25CA, expgap.STUB_AT, expgap.STUB_AT + len(expgap.STUB_ORIG))
BUCKETS = (LOAD + 0x1603) * 16 + expgap.BUCKETS
STATUS = {"灰": 0, "死": 1, "瀕死": 2, "昏倒": 3, "石化": 4, "麻痺": 5, "凍結": 6, "眠り": 0x0D, "毒": 0x0F}
EXCLUDING = (2, 1, 0, 3, 4, 5, 6)
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def blocked(statuses, ash_fixed):
    """358E:3D7C as tools/expshow_test.py has it: the last DS:2426 status the member has, 0 for none."""
    last = 0
    for code in EXCLUDING:
        if code in {STATUS[s] for s in statuses}:
            last = code
    return last != 0 or (ash_fixed and "灰" in statuses)


def factor(g):
    """The rule's factor in 1/4096: 2^(g/5) with g held to -10..10 (written out here, not taken from expgap)."""
    return round(4096 * 2 ** (max(-10, min(10, g)) / 5))


def rule(members, foes, ash_fixed):
    """{slot: gain} by expgap's rule; foes [(experience, level)]."""
    n = sum(1 for m in members if m and not blocked(m[3], ash_fixed))
    out = {}
    for i, m in enumerate(members):
        if not m:
            continue
        if blocked(m[3], ash_fixed) or m[1] >= 99 or n == 0:
            out[i] = 0
            continue
        w = sum(e * factor(min(lv, 99) - m[1]) for e, lv in foes)
        out[i] = 2 * w // (4096 * n)
    return out


def image(blob):
    path = os.path.join(WORK, "build", "_expgap_test.exe")
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
        slot = assemble(f"""
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
        self.mu.mem_write((LOAD + 0x358E) * 16 + 0x514C, slot)
        hero = assemble(f"mov dx, {REC:#x}\nxor ax, ax\nretf 2", org=0x507E)[0]
        self.mu.mem_write((LOAD + 0x358E) * 16 + 0x507E, hero)
        self.masks = bytes(self.mu.mem_read(DS * 16 + 0x42, 8))

    def w16(self, seg, off, v):
        self.mu.mem_write(seg * 16 + off, struct.pack("<H", v & 0xFFFF))

    def stage(self, members):
        """members: six (id, level, experience, [status names]) or None; slot 0 is the protagonist."""
        for i, m in enumerate(members):
            if m is None:
                self.w16(DS, TABLE + 4 * i, 0)
                self.w16(DS, TABLE + 4 * i + 2, 0)
                continue
            ident, level, exp, statuses = m
            rec = bytearray(0x200)
            struct.pack_into("<H", rec, 0, ident)
            rec[0x6B] = level
            struct.pack_into("<I", rec, 0x6E, exp)
            for s in statuses:
                c = STATUS[s]
                rec[0x156 + (c >> 3)] |= self.masks[c & 7]
            self.mu.mem_write(REC * 16 + i * 0x200, bytes(rec))
            self.w16(DS, TABLE + 4 * i, i * 0x200)
            self.w16(DS, TABLE + 4 * i + 2, REC)

    def run(self, cs, ip, until, regs):
        for reg, v in regs:
            self.mu.reg_write(reg, v)
        self.mu.reg_write(X.UC_X86_REG_CS, cs)
        self.mu.reg_write(X.UC_X86_REG_IP, ip)
        self.mu.emu_start(cs * 16 + ip, cs * 16 + until, count=2_000_000)
        if self.mu.reg_read(X.UC_X86_REG_IP) != until or self.mu.reg_read(X.UC_X86_REG_CS) != cs:
            raise RuntimeError(f"run from {cs:04X}:{ip:04X} did not reach {until:04X}")

    def near(self, where, args):
        seg, off = where
        words = [STOP] + list(args)
        sp = SP - 2 * len(words)
        self.mu.mem_write(DS * 16 + sp, struct.pack(f"<{len(words)}H", *words))
        self.run(seg, off, STOP, ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_SP, sp), (X.UC_X86_REG_DS, DS),
                                  (X.UC_X86_REG_ES, DS), (X.UC_X86_REG_BP, 0)))
        return (self.mu.reg_read(X.UC_X86_REG_DX) << 16) | self.mu.reg_read(X.UC_X86_REG_AX)

    def defeat(self, exp, level):
        rec = bytearray(0x238)
        rec[0x6B] = level
        struct.pack_into("<I", rec, 0x6E, exp)
        self.mu.mem_write(FOE * 16, bytes(rec))
        seg, ip, until = DEFEAT
        self.run(seg, ip, until, ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_SP, SP), (X.UC_X86_REG_DS, DS),
                                  (X.UC_X86_REG_ES, FOE), (X.UC_X86_REG_SI, 0), (X.UC_X86_REG_BP, SP)))

    def total(self):
        return struct.unpack("<I", self.mu.mem_read(DS * 16 + 0x9B0C, 4))[0]

    def set_total(self, v):
        self.mu.mem_write(DS * 16 + 0x9B0C, struct.pack("<I", v))

    def buckets(self):
        return list(struct.unpack("<100I", self.mu.mem_read(BUCKETS, 400)))

    def exp_of(self, i):
        return struct.unpack("<I", self.mu.mem_read(REC * 16 + i * 0x200 + 0x6E, 4))[0]

    def battle(self, members, foes, fresh=True):
        """Stage the party, run the defeats (on a cleared sum unless fresh is False), the summary's reader
        and the payout as ov02:0362 does: -> (shown, {slot: gain}, sum)."""
        self.stage(members)
        if fresh:
            self.set_total(0)
        for e, lv in foes:
            self.defeat(e, lv)
        total = self.total()
        shown = self.near(READER, [4])
        before = {i: self.exp_of(i) for i, m in enumerate(members) if m}
        self.near(SHARE_OUT, [total & 0xFFFF, total >> 16])
        self.set_total(0)                                           # ov02:03B1
        return shown, {i: self.exp_of(i) - before[i] for i in before}, total


H = (0, 30, 1000, [])
PARTIES = [
    ("主角与三只低等级恶魔，打 Lv45 的两只", [H, (1, 30, 2000, []), (0x40, 20, 5000, []), (0x41, 10, 900, []),
                                         (0x42, 5, 50, []), None], [(1200, 45), (1300, 45)]),
    ("满员六人，敌人等级不一", [(0, 40, 10, []), (1, 38, 10, []), (0x40, 52, 10, []), (0x41, 30, 10, []),
                              (0x42, 12, 10, []), (0x43, 1, 10, [])], [(900, 20), (2500, 50), (4000, 60), (700, 35)]),
    ("全队与敌人同级（与原来相同）", [(0, 30, 10, []), (1, 30, 10, []), (0x40, 30, 10, []), None, None, None],
     [(300, 30), (400, 30)]),
    ("高于敌人：高 5 级拿一半，高 10 级以上拿四分之一", [(0, 30, 10, []), (1, 35, 10, []), (0x40, 40, 10, []),
                                                   (0x41, 52, 10, []), None, None], [(1000, 30), (800, 25)]),
    ("低于敌人：低 1 到 9 级按 2^(差/5)", [(0, 21, 10, []), (0x40, 22, 10, []), (0x41, 24, 10, []), (0x42, 27, 10, []),
                                        (0x43, 29, 10, []), None], [(997, 30)]),
    ("主角倒下：主角不领，显示 0", [(0, 20, 10, ["死"]), (0x40, 15, 10, []), (0x41, 18, 10, []), None, None, None],
     [(1500, 30)]),
    ("主角 99 级：算在人数里但不领", [(0, 99, 9_000_000, []), (0x40, 40, 10, []), None, None, None, None],
     [(5000, 50)]),
    ("中毒、睡着的照领，石化、麻痹的不领", [H, (0x40, 10, 10, ["毒"]), (0x41, 12, 10, ["眠り"]), (0x42, 5, 10, ["石化"]),
                                         (0x43, 7, 10, ["麻痺"]), None], [(3000, 40), (100, 3)]),
    ("差距超过 10 级按 10 算（两个方向），敌人等级超过 99 记在 99", [(0, 20, 10, []), (0x40, 2, 10, []), None, None, None,
                                                              None], [(1000, 80), (1000, 120), (5000, 1)]),
    ("总和超过 FFFFh", [H, (0x40, 25, 10, []), (0x41, 35, 10, []), None, None, None], [(40000, 45), (50000, 50)]),
    ("分级表乘倍率超过 32 位", [(0, 20, 10, []), (0x40, 25, 10, []), None, None, None, None],
     [(400000, 60), (400000, 60), (3, 20)]),
    ("一个都没打倒（总和 0）", [H, (0x40, 25, 10, []), None, None, None, None], []),
]

orig = open(os.path.join(WORK, "files", "DDS98", "DDS98.EXE"), "rb").read()
for with_stat in (True, False):
    base = expshow.mend_exe(statfix.apply_to(orig) if with_stat else orig)
    patched = expgap.mend_exe(base)
    ash_fixed = with_stat
    print(f"== 程序：经验值显示修复{' + 能力值修复' if with_stat else ''}，有无等级差经验")

    diff = [i for i in range(len(base)) if base[i] != patched[i]]
    sites = [(o, o + len(a)) for o, a, _b, _w in expgap.EXE_SITES + expgap.NEEDS_SITES]
    check(len(base) == len(patched) and all(any(lo <= i < hi for lo, hi in sites) for i in diff),
          f"与没有这个补丁的程序相差 {len(diff)} 字节，都在补丁的位置里")
    _img, main_relocs, ov2 = image(base)
    hdr = 0x3800
    touched = [o for lo, hi in sites if lo < ov2.file_off for o in range(lo - hdr - 1, hi - hdr) if o in main_relocs]
    ov_site = expgap._ov02_file(expgap.CALL_AT)
    ov_touched = sorted(p for p in ov2.relocs if expgap.CALL_AT - 1 <= p < expgap.CALL_AT + len(expgap.CALL_ORIG))
    check(not touched and ov_touched == [expgap.CALL_AT + 3],
          f"主程序里没有重定位字被碰到；ov02 的远调用只换了偏移与段字（{ov_site:#x}，段字仍是重定位字）")
    check(expgap.mend_exe(patched, revert=True) == base, "mend_exe(..., revert=True) 退回经验值显示修复的程序")
    try:
        expgap.mend_exe(statfix.apply_to(orig) if with_stat else orig)
        check(False, "没有经验值显示修复的程序被拒绝")
    except StoryFixError as e:
        check("经验值显示修复" in str(e), f"没有经验值显示修复的程序被拒绝（{e}）")

    old, new = Game(base), Game(patched)
    table = list(struct.unpack("<21H", new.mu.mem_read((LOAD + 0x1603) * 16 + expgap.CODE1_LABELS["factors"], 42)))
    check(table == [factor(g) for g in range(-10, 11)],
          f"程序里的倍率表是 round(4096 × 2^(g/5))，g = −10〜10：{table[0]} … {table[10]} … {table[20]}")
    print("  打倒敌人时的记账")
    new.set_total(0)
    new.mu.mem_write(BUCKETS, bytes(range(256)) + bytes(144))          # stale buckets
    new.defeat(1234, 37)
    b = new.buckets()
    check(new.total() == 1234 and b[37] == 1234 and sum(b) == 1234, "总和为 0 时先清空分级表，再记 Lv37 的 1234")
    new.defeat(70000, 37)
    new.defeat(5, 150)
    b = new.buckets()
    check(new.total() == 71239 and b[37] == 71234 and b[99] == 5 and sum(b) == new.total(),
          "继续累加：同级合计、超过 99 级的记在 99，分级表的和等于 DS:9B0C")
    old.set_total(0)
    old.defeat(1234, 37)
    check(old.total() == 1234, "没有补丁的程序照旧只加总和")

    print("  发放与结算那行")
    for name, members, foes in PARTIES:
        want = rule(members, foes, ash_fixed)
        shown, got, total = new.battle(members, foes)
        hero_ok = shown == want.get(0, 0)
        check(got == want and hero_ok and total == sum(e for e, _l in foes),
              f"{name}：显示 {shown}；实得 " + " ".join(f"+{got[i]}" if i in got else "空" for i in range(6)))
        if foes and all(m is None or all(m[1] == min(lv, 99) for _e, lv in foes) for m in members):
            _s, plain, _t = old.battle(members, foes)
            check(plain == got, f"{name}：与没有补丁的程序发放的相同")
    print("  逃跑的那一战留下的击破，下一战一起按各自等级发放")
    members = [H, (0x40, 10, 10, []), None, None, None, None]
    new.stage(members)
    new.set_total(0)
    new.defeat(800, 30)                                               # a fight the party fled
    shown, got, _total = new.battle(members, [(500, 15)], fresh=False)
    want = rule(members, [(800, 30), (500, 15)], ash_fixed)
    check(got == want and shown == want[0], f"两战合在一起：显示 {shown}；实得 {got}，按规则 {want}")
    print("  随机的队伍与敌人")
    rng = random.Random(7)
    bad = 0
    for _k in range(200):
        members = [(0, rng.randint(1, 99), 10, rng.choice([[], [], ["死"], ["毒"]]))]
        members += [(0x40 + j, rng.randint(1, 99), 10, rng.choice([[], [], [], ["石化"], ["眠り"]]))
                    if rng.random() < 0.7 else None for j in range(5)]
        foes = [(rng.randint(0, 9000), rng.randint(1, 99)) for _j in range(rng.randint(0, 8))]
        if not any(m and not blocked(m[3], ash_fixed) for m in members) and not with_stat:
            continue                                                  # the original divides by zero there
        want = rule(members, foes, ash_fixed)
        shown, got, _t = new.battle(members, foes)
        bad += got != want or shown != want.get(0, 0)
    check(bad == 0, f"200 个随机的队伍与敌人：{200 - bad if bad else '全部'}与规则一致")

print("FAILED" if fails else "OK", f"({fails} failed)")
sys.exit(1 if fails else 0)
