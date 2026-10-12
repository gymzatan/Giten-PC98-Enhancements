#!/usr/bin/env python3
"""rebalance_test.py - 再平衡 (tools/rebalance.py) on an emulated CPU (unicorn): every changed routine of DDS98.EXE
run as the game runs it, against the redesign's rules written out here (the balance lab's vrules.VNew with tuned38,
rolled as its sim3 rolls them; tools/rebalance.py has the numbers).

The program is loaded as DOS loads it (the build's DDS98.EXE: 能力值修复, 攻击技能修复 and 再平衡 in), overlays 16
and 2 relocated in free memory, with SS = DS = DGROUP. x87 code is in the MS C 8087 emulator's form: an INT 34h..3Dh
is turned into the real instruction where it stands and run again, as the emulator does with a coprocessor. The
random generator's byte source (1603:3E32) hands out bytes from a script, so every roll is tried on both sides of its
threshold; the moon table (ET0003) sits behind DS:22A4; the item and skill tables answer the memory manager
(0871:9326) as in tools/statfix_test.py.

  W1   the derived values: 296E's tail entered at 2B46 in a staged frame (the skill levels in di, [bp-2], [bp-4],
       [bp-6] as 296E leaves them), the three equipment readers stubbed - every value against the integer rule of
       rebalance.FORMULAS, within 0.5 of the exact value; +F8h L (the protagonist's 魅力 for a roster demon, when
       one of the protagonist's awakening slots holds COMP), +104h the gun terms x4, +110h the raw gun attack; the
       words beside them; the stack
  W2   max HP (358E:4314): floor(min(9999, 5 + 加护 + 命运 + Lv (0.99 + 0.297 体力 + 0.198 Lv)))
  W3   speed (358E:1992): max(1, round(4 sqrt(敏捷性) - 0.25 armour / max(1, sqrt(力量)))), armour from 358E:2CEE
  W4   the hit rolls' tails (ov16:0C44, 384E): U(0..65535) < p16 hits, else a byte below 128 grazes; p16 the rounded
       65536 / (1 + (0.4 E / H)^2) in 3277..63570; +186h, [98FC] and the return as the game's exits set them
  W5   damage before the game's multipliers (ov16:0D6A-0E26, 3920-39F8): 0.5227 A^2 / (A + max(1, D)), x2.5 on a
       crit, a plain attack's later swings x0.5; the swing count (07BC's 07CA)
  W6   crits and instant kills (ov16:0964, 3556): the gate, the redesign's kill and crit chances at their thresholds,
       the game's own block for an enemy in a ＠ボス戦 (same decision as the game on the same draws), none for the
       party on a ＠ボス戦 enemy, the code 0 / -6
  W7   the magic hit's tail (2FBD): 0.8, S x R / 50, the code's R; COMP hit (2ECE, 32FD)
  W8   magic damage (30AA-3122): 1.9008 S^2 / (S + max(1, M)), S = ax / 2; the attack it is given (309C)
  W9   the moon (25CA:8E68): x sqrt(v / 50), rounded
  W10  heals (358E:0252): round((sqrt(魔力) + power + 0.75 魔力) U(80..120) / 100), and the FD-FF fractions
  W11  growth: ov02:0272's redirected point to the lowest attribute; ov02:01D8's 命运 as the game gives it, 体力
       untouched; ov02:0FBC from both callers (the level-up screen's return 061A, the automatic level-up's 0A80)
       against the program before 再平衡 on the same random bytes - the same points and result, and the 体力 point
       (6 at [951A] and [951C] on a human's level reached divisible by 3: the screen's argument, the automatic
       one's level + 1) with the loops' bounds [9524] / [9526]; the loops' compares at 0631 and 0ABE
  W12  the COMP's summon (358E's SUMMON_SWAP, 4B30 stubbed): the swap's arguments and result passed on, the COMP
       holder (the protagonist, else 英美, present and able to act; 山瀬 never) 255 further from its turn unless
       its own action is under way, nobody else touched
  W13  the gun attack (390E's h_gatk: the raw value x0.5 for humans and demons alike) and GUNPANEL's raw panel
  W14  カジャ (25CA:AF8F): every set, the COMP values beside sets 3 and 5, the sum
  the battle's start (ov16:1590): every roster member with stale (zero) values comes out as 358E:18D8 makes an
       identical twin, the party's countdowns 0, the others' untouched
  W16  negotiation (1603:8844 run from 886B to 8870 in a staged frame): the protagonist's value S raised by his COMP
       level - x (100 + C) / 100 for 直感 魔力 知力 敏捷性 器用 魅力 命运, x (200 + C) / 200 for the level only in
       EC:44 - while the VM's selector is E0h-EFh and the sides are not swapped; everything else and [bp-2] = 0 kept

    rebalance_test.py
"""
import math
import os
import random
import struct
import sys
from fractions import Fraction

from unicorn import UC_ARCH_X86, UC_HOOK_INTR, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rebalance as RB  # noqa: E402
import skillfix  # noqa: E402
import statfix  # noqa: E402
import tables  # noqa: E402
from asm86 import assemble, emu_to_real  # noqa: E402
from mz import MZ, overlays  # noqa: E402

SRC = RB.SRC
LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP (SS too)
OV16, OV2 = 0x8000, 0x8800              # the overlays' load segments
REC = 0x9000                            # staged unit records, 200h apart
ITEMS, SKILLS = 0xB000, 0xC000
MOONTAB = 0xD000                        # ET0003 as the game loads it
RANDSTUB = 0xE000                       # the scripted byte source 1603:3E32 jumps to
STOP_SEG, STOP = 0x0F00, 0x0010         # a far return address a run stops at
QUEUE, QPTR = 0xF000, 0xEFFE            # DGROUP: the scripted random bytes, the pointer into them
STUB = 0xF100                           # DGROUP: W1's equipment-reader stubs
BP = 0xAA00
BUF = LOAD + 0x4827
LEVELS = (0xF6, 0x102, 0x10E, 0x11A)
fails = 0
counts = {}


def check(ok, what):
    global fails
    fails += not ok
    if not ok:
        print("  FAIL  " + what)


def count(what):
    counts[what] = counts.get(what, 0) + 1


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def r16(v):
    return v - 0x10000 if v & 0x8000 else v


def build_exe():
    shipped = open(os.path.join(SRC, RB.EXE_NAME), "rb").read()
    return RB.mend_exe(skillfix.mend_exe(statfix.apply_to(shipped)))


EXE = build_exe()


class Machine:
    def __init__(self, exe=EXE):
        path = os.path.join(WORK, "build", "_rebalance_test.exe")
        with open(path, "wb") as f:
            f.write(exe)
        try:
            img = bytes(MZ(path, base=LOAD).image)
            ovs = overlays(path)
        finally:
            os.remove(path)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x110000)
        self.mu.mem_write(LOAD * 16, img)
        for n, seg in ((16, OV16), (2, OV2)):
            ov = bytearray(ovs[n].image)
            for p in ovs[n].relocs:
                struct.pack_into("<H", ov, p, (struct.unpack_from("<H", ov, p)[0] + LOAD) & 0xFFFF)
            self.mu.mem_write(seg * 16, bytes(ov))
        (items,) = tables.chunks_of(statfix.apply_table(open(os.path.join(SRC, "ET0001.BIN"), "rb").read()))
        skills = tables.chunks_of(open(os.path.join(SRC, "ET0004.BIN"), "rb").read())[0]
        self.mu.mem_write(ITEMS * 16, items)
        self.mu.mem_write(SKILLS * 16, skills)
        self.patch(0x871, 0x9326, f"""
            push bp
            mov bp, sp
            mov dx, {ITEMS:#x}
            cmp word ptr [bp + 6], 1
            jne s_out
            mov dx, {SKILLS:#x}
        s_out:
            xor ax, ax
            pop bp
            retf 2
        """)
        self.mu.mem_write(RANDSTUB * 16, assemble(f"""
            push bx
            mov bx, word ptr [{QPTR:#x}]
            mov al, byte ptr [bx]
            inc word ptr [{QPTR:#x}]
            pop bx
            retf
        """, org=0)[0])
        self.patch(0x1603, 0x3E32, f"ljmp {RANDSTUB:#x}:0")       # 5 bytes, inside the 10 of 3E32
        self.w16(DS, 0x29C0, 1)
        self.w16(DS, 0x2F52, 2)
        self.w16(DS, 0x29C8, 0xFFFF)
        self.w16(DS, 0x637C, BUF)
        self.w16(DS, 0x2FCE, 156)
        moon = tables.chunks_of(open(os.path.join(SRC, "ET0003.BIN"), "rb").read())[0]
        self.moon = bytes(moon)
        self.mu.mem_write(MOONTAB * 16, self.moon)
        self.w16(DS, 0x22A4, 0)
        self.w16(DS, 0x22A6, MOONTAB)
        self.mu.hook_add(UC_HOOK_INTR, self._intr)
        self.draws = 0

    def patch(self, seg, off, source):
        at = (LOAD + seg) * 16 + off
        code = assemble(source, org=off)[0]
        self.mu.mem_write(at, code)
        self.mu.ctl_remove_cache(at, at + len(code))         # unicorn keeps code it has translated

    def _intr(self, mu, intno, _data):
        if not 0x34 <= intno <= 0x3D:
            raise RuntimeError(f"INT {intno:02X}h")
        cs, ip = mu.reg_read(X.UC_X86_REG_CS), mu.reg_read(X.UC_X86_REG_IP)
        at = cs * 16 + ip - 2
        code = bytes(mu.mem_read(at, 3))
        mu.mem_write(at, emu_to_real(code))
        mu.ctl_remove_cache(at, at + 3)
        mu.reg_write(X.UC_X86_REG_IP, ip - 2)

    def w8(self, seg, off, v):
        self.mu.mem_write(seg * 16 + off, bytes([v & 0xFF]))

    def w16(self, seg, off, v):
        self.mu.mem_write(seg * 16 + off, struct.pack("<H", v & 0xFFFF))

    def w32(self, seg, off, v):
        self.mu.mem_write(seg * 16 + off, struct.pack("<I", v & 0xFFFFFFFF))

    def wd(self, seg, off, v):
        self.mu.mem_write(seg * 16 + off, struct.pack("<d", v))

    def r8(self, seg, off):
        return self.mu.mem_read(seg * 16 + off, 1)[0]

    def r16(self, seg, off):
        return struct.unpack("<H", bytes(self.mu.mem_read(seg * 16 + off, 2)))[0]

    def rd(self, seg, off):
        return struct.unpack("<d", bytes(self.mu.mem_read(seg * 16 + off, 8)))[0]

    def script(self, values):
        """The random bytes the next run draws, in order."""
        data = bytes(v & 0xFF for v in values)
        self.mu.mem_write(DS * 16 + QUEUE, data + bytes(64))
        self.w16(DS, QPTR, QUEUE)

    def drawn(self):
        return self.r16(DS, QPTR) - QUEUE

    def run(self, cs, ip, stop_linear, regs=None, count_=3_000_000):
        mu = self.mu
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, cs), (X.UC_X86_REG_IP, ip)):
            mu.reg_write(reg, v)
        for name, v in (regs or {}).items():
            mu.reg_write(getattr(X, "UC_X86_REG_" + name.upper()), v & 0xFFFF)
        mu.emu_start(cs * 16 + ip, stop_linear, count=count_)
        if mu.reg_read(X.UC_X86_REG_CS) * 16 + mu.reg_read(X.UC_X86_REG_IP) != stop_linear:
            raise RuntimeError(f"stopped at {mu.reg_read(X.UC_X86_REG_CS):04X}:{mu.reg_read(X.UC_X86_REG_IP):04X}")

    def far_call(self, cs, ip, args=(), regs=None):
        """Far call cs:ip (a load segment), the args pushed in the order given; -> (ax, dx)."""
        stack = [STOP, STOP_SEG] + [a & 0xFFFF for a in reversed(args)]
        sp = 0xAB00 - 2 * len(stack)
        self.mu.mem_write(DS * 16 + sp, struct.pack(f"<{len(stack)}H", *stack))
        self.run(cs, ip, STOP_SEG * 16 + STOP, {"sp": sp, "bp": 0xAB00, **(regs or {})})
        return self.mu.reg_read(X.UC_X86_REG_AX), self.mu.reg_read(X.UC_X86_REG_DX)

    def frame(self, size, args, saved=0):
        """A routine's frame as its `enter size` and `saved` pushes leave it, called far with `args` (as pushed, in
        order): bp, with sp below the saved registers."""
        bp = 0xAA00
        stack = [0x3333, STOP, STOP_SEG] + [a & 0xFFFF for a in reversed(args)]
        self.mu.mem_write(DS * 16 + bp, struct.pack(f"<{len(stack)}H", *stack))
        self.mu.mem_write(DS * 16 + bp - size - 2 * saved, bytes(size + 2 * saved))
        return bp, bp - size - 2 * saved

    def unit(self, slot, ident=0x40, lv=30, attr=None, **words):
        """A record at REC:slot*200h: id, level, effective attributes (+E0h) and base ones (+88h), other words."""
        off = slot * 0x200
        self.mu.mem_write(REC * 16 + off, bytes(0x200))
        self.w16(REC, off, ident)
        self.w8(REC, off + 0x6B, lv)
        for k, v in enumerate(attr or [20] * 11):
            self.w16(REC, off + 0xE0 + 2 * k, v)
            self.w16(REC, off + 0x88 + 2 * k, v)
        for name, v in words.items():
            place = int(name[1:], 16)
            if name[0] == "b":
                self.w8(REC, off + place, v)
            else:
                self.w16(REC, off + place, v)
        return off


ATTR = RB.ATTRS
IX = {a: k for k, a in enumerate(ATTR)}
rng = random.Random(98)


def rand_attr():
    return [rng.randrange(1, 101) for _ in range(11)]


# ---- W1: the derived values ------------------------------------------------------------------------------------
def w1_tests():
    m = Machine()
    for k, (off, args) in enumerate(((0xE8D4, 1), (0xE92C, 1), (0xE80E, 3))):
        note = "\n".join(f"""
            mov ax, word ptr ss:[bx + {4 + 2 * j}]
            mov word ptr [{STUB + 8 + 6 * k + 2 * j:#x}], ax""" for j in range(args))
        m.patch(0x25CA, off, f"""
            mov bx, sp
            {note}
            mov ax, word ptr [{STUB + 2 * k:#x}]
            retf {2 * args}
        """)

    def stage(slot, u):
        return m.unit(slot, u["id"], u["lv"], [u["attr"][a] for a in ATTR],
                      **{f"w{p:x}": v for p, v in zip(LEVELS, u["levels"])}, w1b6=u["sword_slot"],
                      w1ba=u["gun_slot"], **{f"b{0x42 + k:x}": b for k, b in enumerate(u["slots"])})

    def derive(off, u):
        frame = bytearray(0x42)

        def put(disp, v):
            struct.pack_into("<H", frame, 0x42 + disp, v & 0xFFFF)
        for k, v in enumerate(u["gear"]):
            put(-0x36 + 2 * k, v)
        put(-0x3A, off)
        put(-0x38, REC)
        put(-2, u["levels"][1])
        put(-4, u["levels"][2])
        put(-6, u["levels"][3])
        put(-0x40, 0x1111)
        put(-0x42, 0x2222)
        m.mu.mem_write(DS * 16 + BP - 0x42, bytes(frame))
        for k, v in enumerate((0x3333, STOP, STOP_SEG, off, REC)):
            m.w16(DS, BP + 2 * k, v)
        for k, v in enumerate((u["mgear_hit"], u["mgear_atk"], u["mgear_def"])):
            m.w16(DS, STUB + 2 * k, v)
        m.mu.mem_write(DS * 16 + STUB + 8, bytes(18))
        m.run(LOAD + 0x358E, RB.W1_TAIL, STOP_SEG * 16 + STOP,
              {"es": REC, "bp": BP, "sp": BP - 0x42, "di": u["levels"][0]})
        out = {name: m.r16(REC, off + place) for name, place, _b, _t in RB.FORMULAS}
        out.update(g_def=m.r16(REC, off + 0x10C), lead=m.r16(REC, off + 0xF8), t4=m.r16(REC, off + 0x104),
                   g9=m.r16(REC, off + 0x110),
                   ones=[m.r16(REC, off + p) for p in (0x11C, 0x122, 0x124)],
                   levels=[m.r16(REC, off + p) for p in LEVELS],
                   args=[m.r16(DS, STUB + 8 + 2 * j) for j in range(9)],
                   regs=[m.mu.reg_read(r) for r in (X.UC_X86_REG_SP, X.UC_X86_REG_BP, X.UC_X86_REG_SI,
                                                     X.UC_X86_REG_DI)])
        return out

    def sources(u, lead):
        a = u["attr"]
        g = [r16(x & 0xFFFF) for x in u["gear"]]
        gun = u["id"] < 0x20 and (u["gun_slot"] & 0x7FF) not in (0, 0x7FF)
        gun_lv = u["levels"][1]
        s = dict(a)
        s.update(gear_hit=g[2], gear_atk=g[3], gear_eva=g[4], gear_def=g[5], gear_ghit=g[8], gear_gatk=g[9],
                 mgear_eva=g[16], mgear_hit=u["mgear_hit"], mgear_atk=u["mgear_atk"], mgear_def=u["mgear_def"],
                 lv=u["lv"], gun_lv=gun_lv, lead=lead, dex_gun=a["器用"] if gun else 0,
                 gun_bonus=2 * (gun_lv + 5) if gun_lv >= 1 else 0, sw_lv=u["levels"][0], mg_lv=u["levels"][2],
                 cp_lv=u["levels"][3])
        return s

    def rule(u, lead):
        s = sources(u, lead)
        out = {}
        for name, _place, boosted, terms in RB.FORMULAS:
            acc = sum(s[src] * coef for src, coef in terms)
            mm = 2000 + (lead if boosted else 0)
            out[name] = (min(999, max(1, (acc * mm + 40000) // 80000)),
                         min(Fraction(999), max(Fraction(1), Fraction(acc * mm, 80000))))
        t4 = (20 * s["dex_gun"] + 2 * s["lv"] + 2 * s["gun_lv"]) & 0xFFFF
        return out, t4, u["gear"][9] & 0xFFFF

    def random_unit(ident):
        item = rng.randrange(1, 0x7FF)
        # awakening slots +42h..+44h: the skill in the low two bits (3 COMP), a negative byte empty
        slots = [0] + [rng.choice([1, 2, 3, 0x43, 0xFF, 0x83]) for _ in range(2)]
        return {"id": ident, "lv": rng.randrange(1, 100), "attr": {a: rng.randrange(1, 101) for a in ATTR},
                "gear": [rng.randrange(-40, 260) for _ in range(24)],
                "sword_slot": rng.choice([0, 0x7FF, item | rng.randrange(0, 32) << 11]),
                "gun_slot": rng.choice([0, 0x7FF, item | rng.randrange(0, 32) << 11]),
                "levels": [rng.randrange(0, 60) if ident < 0x20 else 0 for _ in range(4)],
                "mgear_hit": rng.randrange(0, 60), "mgear_atk": rng.randrange(0, 80),
                "mgear_def": rng.randrange(0, 120), "slots": slots}

    def extreme(ident, top):
        v = 100 if top else 1
        return {"id": ident, "lv": 99 if top else 1, "attr": {a: v for a in ATTR},
                "gear": [999 if top else -999] * 24, "sword_slot": 0x123, "gun_slot": 0x155,
                "levels": [99, 99, 99, 99] if top else [0, 0, 0, 0],
                "mgear_hit": 999 if top else 0, "mgear_atk": 999 if top else 0, "mgear_def": 999 if top else 0,
                "slots": [0, 2, 3] if top else [0, 0xFF, 0xFF]}

    def has_comp(u):
        return any(b < 0x80 and b & 3 == 3 for b in u["slots"])

    worst = Fraction(0)
    cases = [[random_unit(0), random_unit(rng.randrange(0x20, 0x200)), random_unit(rng.randrange(1, 0x20)),
              random_unit(rng.randrange(0x20, 0x200))] for _ in range(300)]
    cases += [[extreme(0, t), extreme(0x40, t), extreme(5, t), extreme(0x41, t)] for t in (True, False)]
    for n, units in enumerate(cases):
        offs = [stage(k, u) for k, u in enumerate(units)]
        for k in range(32):
            m.w16(DS, 0x9973 + 4 * k, offs[k] if k < 3 else 0)
            m.w16(DS, 0x9975 + 4 * k, REC if k < 3 else 0)
        for k, (u, off) in enumerate(zip(units, offs)):
            lead = units[0]["attr"]["魅力"] if (u["id"] >= 0x20 and 0 < k < 3 and has_comp(units[0])) else 0
            got = derive(off, u)
            count("W1 单位")
            want, t4, g9 = rule(u, lead)
            tag = f"W1 #{n} 单位 {k} ({u['id']:03X})"
            for name, (w, exact) in want.items():
                check(got[name] == w, f"{tag} {name}: {got[name]} != {w}")
                worst = max(worst, abs(got[name] - exact))
            check(got["g_def"] == got["s_def"], f"{tag} 枪防御 {got['g_def']} != {got['s_def']}")
            check((got["lead"], got["t4"], got["g9"]) == (lead, t4, g9),
                  f"{tag} +F8h/+104h/+110h {got['lead']}/{got['t4']}/{got['g9']} != {lead}/{t4}/{g9}")
            check(got["ones"] == [1, 1, 1], f"{tag} COMP 栏 {got['ones']}")
            check(got["levels"] == u["levels"], f"{tag} 技能等级 {got['levels']}")
            sword = u["sword_slot"] & 0x7FF
            sword = (sword - 0x800 if sword & 0x400 else sword) & 0xFFFF
            want_args = [sword, 0, 0, sword, 0, 0, 3, off, REC]
            check(got["args"] == want_args, f"{tag} 读装备的参数 {got['args']}")
            check(got["regs"] == [BP + 10, 0x3333, 0x2222, 0x1111], f"{tag} sp bp si di {got['regs']}")
    check(worst <= Fraction(1, 2), f"W1 与精确值的最大差 {float(worst):.3f}")
    print(f"W1 派生值：{counts.get('W1 单位', 0)} 个单位，与精确值最大差 {float(worst):.3f}")


# ---- W6: crits and instant kills -------------------------------------------------------------------------------
KP, K25, K04, K05, K08, KM, KMG = (f32(x) for x in (0.5227, 2.5, 0.4, 0.5, 0.8, 1.9008, 0.35))


def gate_of(age):
    x = (age + 13) % 14 + 1
    return x * x // 4


def kill16(a, t):
    k4 = lambda u: 2 * u[IX["直感"]] + u[IX["知力"]] + 4 * u[IX["命运"]]  # noqa: E731
    kt = max(1, k4(t))
    d = min(max(k4(a) - kt, 0), kt)
    return 98304 * d // (5 * kt)


def crit16(a, t, b0):
    p = 12 + 8 * (2 * a[IX["直感"]] + a[IX["知力"]] - 2 * t[IX["加护"]]) + b0
    return min(140, max(0, p)) * 4096 // 25


def crit_tests(old_m):
    m = Machine()
    for side, at, b0_at in (("剑", 0x964, None), ("枪", 0x3556, None)):
        for n in range(500):
            a, t = rand_attr(), rand_attr()
            if n % 5 == 0:                                   # strong attackers: the kill chance above 0
                a[IX["直感"]], a[IX["命运"]], t[IX["命运"]] = 95, 95, rng.randrange(1, 30)
            b0 = rng.randrange(-30, 60)
            age = rng.randrange(28)
            code = rng.choice([50, 50, 50, 100, 25, 0, -6, -1])
            flag = rng.random() < 0.2
            enemy_actor = rng.random() < 0.4
            boss = rng.random() < 0.4
            m.patch(OV16 - LOAD, 0x0000, f"mov ax, {b0 & 0xFFFF:#x}\nretf 8")
            ao = m.unit(0, 0x40, 30, a, b186=rng.randrange(256))
            to = m.unit(1, 0x41, 30, t)
            old186 = m.r8(REC, ao + 0x186)
            m.w8(DS, 0x98EA, age)
            m.w16(DS, 0x9A0A, 3 if enemy_actor else 0xFFFE)
            m.w16(DS, 0x2EF8, 1 if boss else 0)
            m.w16(DS, 0x98FC, 0x7777)
            g = gate_of(age)
            r_gate = rng.choice([g - 1, g, rng.randrange(256)]) & 0xFF
            gate = r_gate < g
            pk = kill16(a, t)
            pc = crit16(a, t, b0)
            u_kill = rng.choice([pk - 1, pk, rng.randrange(65536)]) & 0xFFFF
            u_crit = rng.choice([pc - 1, pc, rng.randrange(65536)]) & 0xFFFF
            mode = 3 if code in (0, -6) else (2 if not gate or flag else (1 if enemy_actor and boss else 0))
            if mode == 1:
                continue                                     # the game's own block: below
            q = [r_gate]
            if mode == 0:
                q += [u_kill >> 8, u_kill & 0xFF]
            if mode == 2 or (mode == 0 and u_kill >= pk):
                q += [u_crit >> 8, u_crit & 0xFF]
            m.script(q)
            ax, _dx = m.far_call(OV16, at, (REC, ao, REC, to, int(flag), code))
            got = (r16(ax), m.r8(REC, ao + 0x186), m.r16(DS, 0x98FC))
            if mode == 3:
                want = (0, old186, 0x7777)
            elif mode == 0 and u_kill < pk:
                want = (5, (old186 & 0x85) | 5, 5)
            elif u_crit < pc:
                want = (4, (old186 & 0x84) | 4, 4)
            else:
                want = (0, old186 & 0x80, 0)
            count(f"W6 {side}")
            check(got == want and m.drawn() == len(q),
                  f"W6 {side} #{n} mode {mode} gate {r_gate}/{g} kill {u_kill}/{pk} crit {u_crit}/{pc}: {got} != "
                  f"{want}, drew {m.drawn()} of {len(q)}")
        # an enemy in a ＠ボス戦 fight: the game's own instant-kill block decides as the game does on the same draws
        same = 0
        for n in range(200):
            a, t = rand_attr(), rand_attr()
            a[IX["命运"]] = rng.randrange(40, 101)
            b0 = rng.randrange(-10, 40)
            age = rng.choice([0, 7, 13, 20, 27])
            g = gate_of(age)
            draws = [rng.randrange(g)] + [rng.randrange(256) for _ in range(6)]
            results = []
            for mm in (m, old_m):
                mm.patch(OV16 - LOAD, 0x0000, f"mov ax, {b0 & 0xFFFF:#x}\nretf 8")
                ao = mm.unit(0, 0x40, 30, a)
                to = mm.unit(1, 0x41, 30, t)
                mm.w8(DS, 0x98EA, age)
                mm.w16(DS, 0x9A0A, 3)
                mm.w16(DS, 0x2EF8, 1)
                mm.script(draws)
                ax, _dx = mm.far_call(OV16, at, (REC, ao, REC, to, 0, 50))
                results.append(r16(ax))
            count(f"W6 {side} 头目即死")
            check((results[0] == 5) == (results[1] == 5), f"W6 {side} 头目即死 #{n}: 再平衡 {results[0]}，原版 {results[1]}")
            same += results[1] == 5
        check(same > 5, f"W6 {side} 头目即死：原版只即死 {same} 次，样本不足")
    print(f"W6 会心与即死：剑 {counts.get('W6 剑', 0)} 例，枪 {counts.get('W6 枪', 0)} 例；头目自带的即死各 "
          f"{counts.get('W6 剑 头目即死', 0)} 例与原版判定一致")


# ---- W4: the hit rolls -----------------------------------------------------------------------------------------
def p16_phys(H, E, k):
    H, E = max(1, H), max(1, E)
    x = Fraction(k) * Fraction(E, H)
    p = Fraction(65536) / (1 + x * x)
    v = round(p)                                             # half to even, as fistp
    return min(63570, max(3277, v))


def hit_tests():
    m = Machine()
    for side, tail, h, e, hit_exit_mark in (("剑", 0x0C44, 4, 0xC, 3), ("枪", 0x384E, 4, 8, 3)):
        for n in range(600):
            H = rng.choice([rng.randrange(1, 2000), rng.randrange(1, 200000)])
            E = rng.choice([rng.randrange(1, 2000), rng.randrange(1, 200000), H * rng.randrange(1, 6)])
            p = p16_phys(H, E, K04)
            u = rng.choice([p - 1, p, rng.randrange(65536)]) & 0xFFFF
            g = rng.choice([127, 128, rng.randrange(256)])
            ao = m.unit(0, 0x40, b186=rng.randrange(256))
            old186 = m.r8(REC, ao + 0x186)
            bp, sp = m.frame(0xC, (REC, ao, REC, 0x200, 0), saved=2)
            m.w16(DS, bp - 0xE, 0x1111)
            m.w16(DS, bp - 0x10, 0x2222)
            m.w32(DS, bp - h, H)
            m.w32(DS, bp - e, E)
            m.w16(DS, 0x98FC, 0x7777)
            m.script([u >> 8, u & 0xFF, g])
            m.run(OV16, tail, STOP_SEG * 16 + STOP, {"bp": bp, "sp": sp, "si": ao, "di": 0x200})
            ax = m.mu.reg_read(X.UC_X86_REG_AX)
            got = (ax, m.r8(REC, ao + 0x186), m.r16(DS, 0x98FC))
            if u < p:
                want = (1, (old186 & 0x83) | 3, 3)
            elif g < 128:
                want = (1, (old186 & 0x82) | 2, 2)
            else:
                want = (0, old186 & 0x80, 0)
            count(f"W4 {side}")
            check(got == want, f"W4 {side} #{n} H {H} E {E} p16 {p} U {u} g {g}: {got} != {want}")
    print(f"W4 命中：剑 {counts.get('W4 剑', 0)} 例，枪 {counts.get('W4 枪', 0)} 例")


# ---- W5 / W13: damage before the game's multipliers ------------------------------------------------------------
def phys_base(A, D, mode, swing):
    D = max(1, D)
    v = A * A / (A + D) * KP
    if mode == 4:
        v *= K25
    if swing:
        v *= K05
    return v


def damage_tests():
    m = Machine()
    for n in range(400):                                     # the sword: 0D6A..0E26
        A = rng.choice([rng.randrange(1, 1000), rng.randrange(1, 4000)]) + rng.random()
        D = rng.choice([0, rng.randrange(1, 1000)])
        mode = rng.choice([1, 2, 3, 4])
        plain = rng.random() < 0.5
        count29 = rng.randrange(1, 6)
        ao = m.unit(0, 0x40, b181=1 if plain else 4)
        to = m.unit(1, 0x41, w130=D)
        bp, sp = m.frame(0x1A, (REC, ao, REC, to, mode), saved=2)
        m.wd(DS, bp - 8, A)
        m.w16(DS, 0x29D2, count29)
        m.run(OV16, 0x0D6A, (OV16) * 16 + 0x0E26, {"bp": bp, "sp": sp})
        got = m.rd(DS, bp - 8)
        want = phys_base(A, D, mode, plain and count29 >= 3)
        count("W5 剑")
        check(abs(got - want) <= 1e-9 * max(1.0, want), f"W5 剑 #{n} A {A} D {D} mode {mode}: {got} != {want}")
    swings = []
    for c in range(1, 5):                                     # the swing count: 07CA
        for mode in (1, 4):
            ao = m.unit(0, 0x40, b181=mode)
            bp, sp = m.frame(6, (REC, ao, REC, 0x200, 0), saved=2)
            m.w16(DS, 0x29D2, c)
            m.w16(DS, 0x9B3E, 0x5555)
            m.run(OV16, 0x07CA, OV16 * 16 + 0x07CD, {"bp": bp, "sp": sp, "si": ao, "ax": 0})
            swings.append((c, mode, m.r16(DS, 0x29D2), m.r16(DS, 0x9B3E)))
    check(all(n2 == (c + 1 if mode == 1 else c) and z == 0 for c, mode, n2, z in swings), f"W5 连击计数 {swings}")
    for n in range(600):                                     # the gun: 3920..39F8 (h_gatk, then the formula)
        human = rng.random() < 0.6
        plain = rng.random() < 0.5
        mg = (not plain) and rng.random() < 0.3
        q = rng.choice([0, rng.randrange(1, 400)])
        lead = 0 if human else rng.choice([0, rng.randrange(1, 101)])
        t4 = rng.randrange(0, 600)
        panel_base = rng.randrange(1, 400)
        kaja = rng.choice([0, 0, rng.randrange(-50, 120)])
        panel = max(1, min(999, panel_base + kaja))
        D = rng.choice([0, rng.randrange(1, 900)])
        mode = rng.choice([1, 2, 3, 4])
        ao = m.unit(0, 5 if human else 0x40, b181=2 if plain else 4,
                    w182=(0x8000 | (RB.MACHINEGUN if mg else 3)), w134=t4, w128=lead, w138=panel, w108=panel_base)
        to = m.unit(1, 0x41, w13c=D)
        bp, sp = m.frame(0x24, (REC, ao, REC, to, mode), saved=2)
        m.w16(DS, 0x864E, q)
        m.run(OV16, 0x3920, OV16 * 16 + 0x39F8, {"bp": bp, "sp": sp})
        got = m.rd(DS, bp - 8)
        if q:
            a = q * K05 + t4 * 0.25
            a = a * (lead + f32(2000.0)) / f32(2000.0)
            if not plain:
                a *= KMG if mg else K04
            a = min(999.0, max(1.0, a))
            a = min(999.0, max(1.0, a + (panel - panel_base)))
        else:
            a = float(panel)
        want = phys_base(a, D, mode, False)
        count("W13 枪")
        check(abs(got - want) <= 1e-9 * max(1.0, want), f"W13 枪 #{n} q {q} 人 {human} 普通 {plain} 机枪 {mg}: "
              f"{got} != {want} (A {a})")
    print(f"W5 伤害：剑 {counts.get('W5 剑', 0)} 例，连击计数 {len(swings)} 例；W13 枪 {counts.get('W13 枪', 0)} 例")


# ---- W7 / W8 / W15: magic ---------------------------------------------------------------------------------------
def comp_skill_ids():
    """(a COMP program, a magic spell): ET0004 ids by the type bits of their header."""
    chunk = tables.chunks_of(open(os.path.join(SRC, "ET0004.BIN"), "rb").read())[0]
    comp = magic = None
    for i, e in enumerate(tables.string_table(chunk)):
        if len(e) <= 20 or i < 16:
            continue
        if e[0] >> 6 == 3 and comp is None and e[10]:
            comp = i
        if e[0] >> 6 == 0 and magic is None and e[10]:
            magic = i
    return comp, magic


def magic_tests():
    m = Machine()
    d001 = struct.unpack("<d", bytes(m.mu.mem_read(DS * 16 + 0x629E, 8)))[0]
    for n in range(600):                                     # the hit's tail: 2FBD
        S = rng.choice([rng.randrange(1, 3000), rng.randrange(100, 300000)])
        V = rng.choice([rng.randrange(1, 3000), rng.randrange(100, 300000)])
        code = rng.choice([50, 100, 25, 250, 0, -1, -2, -3, 75])
        R = 50 if code < 0 else code
        ao = m.unit(0, 0x40, b186=rng.randrange(256))
        old186 = m.r8(REC, ao + 0x186)
        bp, sp = m.frame(0xE, (REC, ao, REC, 0x200, 0), saved=2)
        m.w32(DS, bp - 8, S)
        m.w32(DS, bp - 0xC, V)
        m.w16(DS, 0x2F22, code)
        m.w16(DS, 0x98FC, 3)
        if R:
            s2 = S * R * d001 * 2
            x = Fraction(K08) * Fraction(max(1.0, V)) / Fraction(max(1.0, s2))
            p = min(63570, max(3277, round(Fraction(65536) / (1 + x * x))))
        else:
            p = 0
        u = rng.choice([p - 1, p, rng.randrange(65536)]) & 0xFFFF
        m.script([u >> 8, u & 0xFF])
        m.run(OV16, 0x2FBD, STOP_SEG * 16 + STOP, {"bp": bp, "sp": sp, "si": ao})
        ax = m.mu.reg_read(X.UC_X86_REG_AX)
        hit = R != 0 and u < p
        want = (1, old186, 3) if hit else (0, old186 & 0x80, 0)
        got = (ax, m.r8(REC, ao + 0x186), m.r16(DS, 0x98FC))
        count("W7 魔法命中")
        check(got == want, f"W7 #{n} S {S} V {V} code {code} p16 {p} U {u}: {got} != {want}")
    for n in range(400):                                     # the damage: 30AA..3122
        ax_in = rng.randrange(1, 30001)
        M = rng.choice([0, rng.randrange(1, 999)])
        to = m.unit(1, 0x41, w148=M)
        bp, sp = m.frame(0x10, (REC, 0x200, REC, to, 1), saved=0)
        m.run(OV16, 0x30AA, OV16 * 16 + 0x3122, {"bp": bp, "sp": sp, "ax": ax_in})
        S = ax_in * 0.5
        want = S * S / (S + max(1, M)) * KM
        got = m.rd(DS, bp - 8)
        count("W8 魔法伤害")
        check(abs(got - want) <= 1e-9 * max(1.0, want), f"W8 #{n} ax {ax_in} M {M}: {got} != {want}")
    comp, magic = comp_skill_ids()
    for sid, typ in ((comp, 3), (magic, 0)):                   # the attack handed on (309C) and the hit (2ECE, 32FD)
        matk, catk, mhit, chit, power = 77, 133, 55, 91, rng.randrange(1, 200)
        ao = m.unit(0, 0x40, w144=matk, w150=catk, w142=mhit, w14e=chit, w182=0x8000 | sid)
        rec = m.unit(2, 0)
        m.w8(REC, rec, typ << 6)
        bp, sp = m.frame(0x10, (REC, ao, REC, 0x200, 1), saved=0)
        m.run(OV16, 0x309C, OV16 * 16 + 0x30A5, {"bp": bp, "sp": sp, "ax": power, "es": REC, "bx": rec})
        pushed = m.r16(DS, m.mu.reg_read(X.UC_X86_REG_SP))
        want = power + 2 * (catk if typ == 3 else matk)
        check(pushed == want, f"W8 攻击值 类型 {typ}: {pushed} != {want}")
        m.w16(DS, 0x29D0, 1234)
        for entry, back, at in ((0x2ECE, 0x2ED3, 0xC), (0x32FD, 0x3302, 0xE)):
            args = (REC, ao, REC, 0x200, 1) if at == 0xC else (REC, ao, 0, REC, 0x200, 1)
            bp, sp = m.frame(0x10, args, saved=2)
            m.run(OV16, entry, OV16 * 16 + back, {"bp": bp, "sp": sp})
            got = m.mu.reg_read(X.UC_X86_REG_AX)
            want = chit if typ == 3 else 1234
            count("W15 COMP")
            check(got == want, f"W15 {entry:04X} 技能 {sid} 类型 {typ}: {got} != {want}")
    print(f"W7 魔法命中 {counts.get('W7 魔法命中', 0)} 例；W8 魔法伤害 {counts.get('W8 魔法伤害', 0)} 例；"
          f"W15 COMP 程序 {counts.get('W15 COMP', 0)} 例（技能 {comp} / {magic}）")


# ---- W9 the moon, W14 カジャ, W13's GUNPANEL --------------------------------------------------------------------
def seg25_tests():
    m = Machine()
    d001 = struct.unpack("<d", bytes(m.mu.mem_read(DS * 16 + 0x629E, 8)))[0]
    for n in range(300):
        row, age = rng.randrange(21), rng.randrange(28)
        x = rng.randrange(0, 3_000_000)
        m.w8(DS, 0x98EA, age)
        ax, dx = m.far_call(LOAD + 0x25CA, 0x8E68, (x >> 16, x & 0xFFFF, row, 2))
        v = m.moon[row * 28 + age]
        exact = Fraction(math.sqrt(v * d001 * 2)) * x
        want = round(exact)
        got = (dx << 16) | ax
        near_half = abs(exact - math.floor(exact) - Fraction(1, 2)) < Fraction(1, 10**6)
        count("W9 月相")
        check(got == want or (near_half and abs(got - want) <= 1), f"W9 #{n} row {row} age {age} v {v} x {x}: "
              f"{got} != {want}")
    sets = {0: [(0xFC, 1), (0x108, 1)], 1: [(0xFA, 1), (0x106, 1)], 2: [(0x100, 1), (0x10C, 1)],
            3: [(0x114, 1), (0x120, 0), (0x112, 1), (0x11E, 0)], 4: [(0x116, 1), (0x118, 1)],
            5: [(0x114, 1), (0x120, 0), (0x112, 1), (0x11E, 0), (0x116, 1), (0x118, 1)]}
    every = [0xFA, 0xFC, 0xFE, 0x100, 0x106, 0x108, 0x10A, 0x10C, 0x112, 0x114, 0x116, 0x118, 0x11E, 0x120]
    for n in range(300):
        st = rng.randrange(6)
        d = rng.choice([rng.randrange(1, 60), -rng.randrange(1, 60)])
        base = {p: rng.randrange(1, 400) for p in every}
        cur = {p: max(1, min(999, base[p] + rng.randrange(-30, 200))) for p in every}
        to = m.unit(1, 0x41, **{f"w{p:x}": base[p] for p in every}, **{f"w{p + 0x30:x}": cur[p] for p in every})
        bp, sp = m.frame(0x10, (REC, to, REC, to), saved=2)  # AE66: the target at [bp+6], the caster at [bp+0Ah]
        m.run(LOAD + 0x25CA, 0xAF8F, (LOAD + 0x25CA) * 16 + 0xB0FA,
              {"bp": bp, "sp": sp, "ax": st, "si": to, "di": d})
        total = 0
        want = dict(cur)
        for p, summed in sets[st]:
            cap = min(999, max(1, 4 * base[p]))
            t = min(cur[p] + d, cap)
            if 2 * cur[p] < t:
                t = 2 * cur[p]
            t = min(999, max(1, t))
            want[p] = t
            if summed:
                total += t - cur[p]
        got = {p: m.r16(REC, to + p + 0x30) for p in every}
        gsum = struct.unpack("<i", bytes(m.mu.mem_read(DS * 16 + bp - 4, 4)))[0]
        count("W14 カジャ")
        check(got == want and gsum == total, f"W14 #{n} 组 {st} 步 {d}: 和 {gsum} != {total}; "
              + ", ".join(f"{p:X} {got[p]}/{want[p]}" for p in every if got[p] != want[p]))
    # GUNPANEL: a gun skill's 864E = the raw panel (+140h) less the bullet (at least 1)
    _code, labels = assemble(skillfix.GUNPANEL, org=skillfix.CAVE, consts={"RELOC_LO": 0, "RELOC_HI": 0})
    bullet_id = skillfix.item_ids()[skillfix.DEMON[3][1]]
    for n in range(40):
        raw = rng.randrange(0, 300)
        bullet = 0
        if n % 4:
            buf_ax, buf_dx = m.far_call(LOAD + 0x25CA, 0xC1DA, (bullet_id,))
            bullet = m.r8(buf_dx, buf_ax + 0x20)
        ao = m.unit(0, 5, b181=rng.choice([4, 6]), w140=raw, w138=777,
                    w1be=0x7FF if n % 4 == 0 else 0xF800 | bullet_id)
        m.w16(DS, 0x864E, 0)
        m.w16(DS, 0xA000, 0)
        sp = 0xAB00 - 2
        m.w16(DS, sp, 0xFFF0)                                # a near return to 25CA:FFF0
        m.run(LOAD + 0x25CA, labels["gunpanel"], (LOAD + 0x25CA) * 16 + 0xFFF0,
              {"sp": sp, "bp": 0xA000 + 0x0A, "es": REC, "di": ao})
        got = m.r16(DS, 0x864E)
        want = max(1, raw - bullet)
        count("W13 GUNPANEL")
        check(got == want, f"W13 GUNPANEL #{n} 原始 {raw} 子弹 {bullet}: {got} != {want}")
    print(f"W9 月相 {counts.get('W9 月相', 0)} 例；W14 カジャ {counts.get('W14 カジャ', 0)} 例；GUNPANEL "
          f"{counts.get('W13 GUNPANEL', 0)} 例")


# ---- W2 max HP, W3 speed, W10 heals ------------------------------------------------------------------------------
def seg358_tests():
    m = Machine()
    c = {k: struct.unpack("<d", struct.pack("<d", v))[0] for k, v in (("198", 0.198), ("297", 0.297), ("099", 0.99),
                                                                        ("075", 0.75))}
    for n in range(400):
        a = rand_attr()
        lv = rng.randrange(1, 100)
        uo = m.unit(0, rng.choice([0, 5, 0x40]), lv, a)
        ax, _dx = m.far_call(LOAD + 0x358E, 0x4314, (REC, uo))
        exact = (5 + a[IX["加护"]] + a[IX["命运"]]
                 + Fraction(lv) * (Fraction(c["099"]) + Fraction(c["297"]) * a[IX["体力"]] + Fraction(c["198"]) * lv))
        want = min(9999, math.floor(exact))
        near = abs(exact - round(exact)) < Fraction(1, 10**9)
        count("W2 HP")
        check(ax == want or near, f"W2 #{n} Lv {lv} 体力 {a[IX['体力']]}: {ax} != {want}")
    for n in range(200):
        a = rand_attr()
        uo = m.unit(0, 5, 30, a)
        for k in range(8):
            m.w16(REC, uo + 0x1A2 + 4 * k, rng.choice([0xFFFF, 0xF800 | rng.randrange(400, 560)]))
        armour, _ = m.far_call(LOAD + 0x358E, 0x2CEE, (REC, uo))
        ax, _dx = m.far_call(LOAD + 0x358E, 0x1992, (REC, uo))
        x = 4 * math.sqrt(a[IX["敏捷性"]]) - 0.25 * armour / max(1.0, math.sqrt(a[IX["力量"]]))
        want = max(1, math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5))
        count("W3 速度")
        check(ax == want, f"W3 #{n} 敏捷性 {a[IX['敏捷性']]} 力量 {a[IX['力量']]} 护甲 {r16(armour)}: {ax} != {want}")
    for n in range(300):
        a = rand_attr()
        uo = m.unit(0, 5, 30, a)
        power = rng.choice([0, 0xFF, 0xFE, 0xFD, rng.randrange(1, 200)])
        top = rng.randrange(1, 999)
        r = rng.randrange(256)
        m.script([r])
        ax, _dx = m.far_call(LOAD + 0x358E, 0x0252, (power, REC, uo, top))
        mag = a[IX["魔力"]]
        if power == 0:
            want = 0
        elif power >= 0xFD:
            want = {0xFF: top, 0xFE: top // 2, 0xFD: top // 4}[power]
        else:
            u = 80 + r * 41 // 256
            x = (math.sqrt(mag) + power + mag * c["075"]) * (u * 0.01)
            want = math.floor(x + 0.5)
        count("W10 回复")
        check(ax == want, f"W10 #{n} 魔力 {mag} 威力 {power}: {ax} != {want}")
    print(f"W2 最大HP {counts.get('W2 HP', 0)} 例；W3 速度 {counts.get('W3 速度', 0)} 例；W10 回复 "
          f"{counts.get('W10 回复', 0)} 例")


# ---- W11 growth ---------------------------------------------------------------------------------------------------
def growth_tests(old):
    m = Machine()
    for n in range(200):                                     # ov02:0272 with a redirected point (-1)
        base = [rng.randrange(1, 99) for _ in range(11)]
        if n % 3 == 0:
            low = min(base[:10])
            for k in rng.sample(range(10), 3):
                base[k] = low
        uo = m.unit(0, 0, 30, base)
        sp = 0xAB00 - 8
        for k, v in enumerate((0xFFF0, 0xFFFF, uo, REC)):
            m.w16(DS, sp + 2 * k, v)
        m.run(OV2, 0x0272, OV2 * 16 + 0xFFF0, {"sp": sp, "bp": 0xAB00})
        got = m.mu.reg_read(X.UC_X86_REG_AX)
        want = min(range(10), key=lambda k: (base[k], k))
        count("W11 最低")
        check(got == want, f"W11 最低属性 #{n} {base[:10]}: {got} != {want}")
    for n in range(300):                                     # ov02:01D8 (LU358): the game's luck point, 体力 untouched
        ident = rng.choice([0, 5, 0x40, 0x123])
        lv = rng.randrange(1, 99)
        base = [rng.randrange(1, 101) for _ in range(11)]
        uo = m.unit(0, ident, lv, base)
        sp = 0xAB00 - 6
        for k, v in enumerate((0xFFF0, uo, REC)):
            m.w16(DS, sp + 2 * k, v)
        m.run(OV2, 0x01D8, OV2 * 16 + 0xFFF0, {"sp": sp, "bp": 0xAB00})
        ax = m.mu.reg_read(X.UC_X86_REG_AX)
        luck = (lv % 2 == 0) if ident < 0x20 else (lv % 3 == 0)
        want_luck = min(100, base[10] + 1) if luck else base[10]
        got = (ax, m.r16(REC, uo + 0x9C), m.r16(REC, uo + 0x94))
        count("W11 每级")
        check(got == (int(luck), want_luck, base[6]),
              f"W11 每级 #{n} id {ident:X} Lv {lv} 命运 {base[10]} 体力 {base[6]}: {got} != "
              f"{(int(luck), want_luck, base[6])}")

    def fbc(mach, ident, lv, slots, level_arg, ret_ip, rand):
        """ov02:0FBC(level, DS:9514, unit) called from ret_ip -> (ax, the ten words at DS:9514, filled with 5555h)."""
        uo = mach.unit(0, ident, lv, None, **{f"b{0x42 + k:x}": b for k, b in enumerate(slots)})
        mach.mu.mem_write(DS * 16 + 0x9514, b"\x55" * 20)
        mach.script(rand)
        sp = 0xAB00 - 12
        for k, v in enumerate((ret_ip, level_arg, 0x9514, DS, uo, REC)):
            mach.w16(DS, sp + 2 * k, v)
        mach.run(OV2, 0x0FBC, OV2 * 16 + ret_ip, {"sp": sp, "bp": 0xAB00})
        return mach.mu.reg_read(X.UC_X86_REG_AX), [mach.r16(DS, 0x9514 + 2 * k) for k in range(10)]

    for n in range(400):                                     # 0FBC's end (FBC_VIT): the 体力 point and the bounds
        ident = rng.choice([0, 5, 0xB, 0x40, 0x123])
        lv = rng.randrange(1, 99)
        slots = [rng.choice([0, 1, 2, 3, 0xFF]) for _ in range(3)]
        screen = rng.random() < 0.5
        ret_ip = 0x061A if screen else 0x0A80
        level_arg = lv + rng.randrange(0, 4) if screen else lv + rng.randrange(0, 2)
        rand = [rng.randrange(256) for _ in range(24)]
        want_ax, want_words = fbc(old, ident, lv, slots, level_arg, ret_ip, rand)
        got_ax, got = fbc(m, ident, lv, slots, level_arg, ret_ip, rand)
        reached = level_arg if screen else lv + 1
        vit = ident < 0x20 and reached % 3 == 0
        want = list(want_words)
        if vit:
            want[3] = want[4] = 6
        want[8] = 3 + vit
        want[9] = 0x951C + 2 * vit
        count("W11 体力点")
        check((got_ax, got) == (want_ax, want),
              f"W11 体力点 #{n} id {ident:X} Lv {lv} 参数 {level_arg} {'画面' if screen else '自动'} 觉醒 {slots}: "
              f"{got_ax} {[f'{w:X}' for w in got]} != {want_ax} {[f'{w:X}' for w in want]}")

    def carry_after(mach, start, stop, regs):
        mach.run(OV2, start, OV2 * 16 + stop, regs)
        return mach.mu.reg_read(X.UC_X86_REG_EFLAGS) & 1

    for idx in range(6):                                     # the screen's loop (0631 -> VIT_CMP) and the automatic one's end (0ABE)
        for vit in (0, 1):
            m.w16(DS, 0x9524, 3 + vit)
            m.w16(DS, 0x9526, 0x951C + 2 * vit)
            got = (carry_after(m, 0x0631, 0x0634, {"ax": idx, "sp": 0xAB00}),
                   carry_after(m, 0x0ABE, 0x0AC2, {"di": 0x9514 + 2 * idx}))
            count("W11 循环")
            check(got == (int(idx < 3 + vit), int(idx < 4 + vit)),
                  f"W11 循环 第 {idx} 点 体力点 {vit}: 画面 {got[0]} 自动 {got[1]}")
    print(f"W11 成长：最低属性 {counts.get('W11 最低', 0)} 例，每级固定点 {counts.get('W11 每级', 0)} 例，"
          f"体力点 {counts.get('W11 体力点', 0)} 例，循环 {counts.get('W11 循环', 0)} 例")


# ---- W12: a summon costs the COMP holder a turn ------------------------------------------------------------------
def summon_tests():
    m = Machine()
    # 4B30 itself (slot assignment, through an overlay thunk) is stubbed: it notes its arguments and answers 77h
    m.patch(0x358E, 0x4B30, f"""
        push bp
        mov bp, sp
        mov ax, word ptr [bp + 6]
        mov word ptr [{STUB:#x}], ax
        mov ax, word ptr [bp + 8]
        mov word ptr [{STUB + 2:#x}], ax
        mov ax, 0x77
        pop bp
        retf 4
    """)
    swap = RB.LABELS["summon_swap"]
    for n in range(300):
        ids = [0x40, 0x41, 0, 0x0A, 0x0B, 0x42]
        rng.shuffle(ids)
        present = {i for i in (0, 0x0A, 0x0B) if rng.random() < 0.7}
        able = {i: rng.random() < 0.75 for i in (0, 0x0A, 0x0B)}
        acting = {i: rng.random() < 0.15 for i in (0, 0x0A, 0x0B)}
        cd = {i: rng.choice([0, 0, rng.randrange(1, 300)]) for i in (0, 0x0A, 0x0B)}
        roster = []
        for k, ident in enumerate(ident for ident in ids if ident >= 0x20 or ident in present):
            off = m.unit(k, ident, 30, w17f=cd.get(ident, 5), b17e=int(acting.get(ident, False)))
            if not able.get(ident, True):
                m.mu.mem_write(REC * 16 + off + 0x156, b"\xff" * 5)
            roster.append(off)
        for k in range(32):
            m.w16(DS, 0x9973 + 4 * k, roster[k] if k < len(roster) else 0)
            m.w16(DS, 0x9975 + 4 * k, REC if k < len(roster) else 0)
        slot, demon = rng.randrange(6), rng.randrange(32)
        m.mu.mem_write(DS * 16 + STUB, bytes(4))
        ax, _dx = m.far_call(LOAD + 0x358E, swap, (slot, demon))
        holder = next((i for i in (0, 0x0B) if i in present and able[i]), None)     # 山瀬 (0Ah) never holds it
        got = {i: m.r16(REC, roster[[m.r16(REC, o) for o in roster].index(i)] + 0x17F)
               for i in (0, 0x0A, 0x0B) if i in present}
        want = {i: cd[i] + (255 if i == holder and not acting[i] else 0) for i in got}
        count("W12 召唤")
        check(ax == 0x77 and (m.r16(DS, STUB), m.r16(DS, STUB + 2)) == (demon, slot) and got == want,
              f"W12 #{n} 在队 {sorted(present)} 能行动 {able} 行动中 {acting}: ax {ax:X} 参数 "
              f"{m.r16(DS, STUB)},{m.r16(DS, STUB + 2)} 倒计时 {got} != {want}")
    print(f"W12 召唤占回合 {counts.get('W12 召唤', 0)} 例")


# ---- the battle's start: every roster member worked out again --------------------------------------------------
def battle_start_tests():
    m = Machine()
    fields = list(range(0x5E, 0x60, 2)) + [0x82, 0x86] + list(range(0xF6, 0x156, 2))
    for n in range(40):
        roster = []
        twins = []
        for k in range(rng.randrange(3, 9)):
            ident = rng.choice([0, 5, 7]) if k < 3 else rng.choice([5, 7, 9])  # humans: no leadership to differ
            attr = rand_attr()
            lv = rng.randrange(1, 90)
            items = [rng.choice([0xFFFF, 0xF800 | rng.randrange(191, 560)]) for _ in range(8)]
            for slot, twin in ((k, False), (16 + k, True)):
                off = m.unit(slot, ident, lv, attr)
                for j, it in enumerate(items):
                    m.w16(REC, off + 0x1A2 + 4 * j, it)
                m.mu.mem_write(REC * 16 + off + 0xF6, bytes(0x60))  # stale values: all 0
                m.w16(REC, off + 0x17F, 0x99)
                m.w8(REC, off + 0x17E, 0)
                (twins if twin else roster).append(off)
        for k in range(32):
            m.w16(DS, 0x9973 + 4 * k, roster[k] if k < len(roster) else 0)
            m.w16(DS, 0x9975 + 4 * k, REC if k < len(roster) else 0)
        party = rng.sample(range(len(roster)), min(6, len(roster)))
        for s in range(6):
            m.w16(DS, 0x9965 + 2 * s, party[s] if s < len(party) else 0xFFFF)
        m.far_call(OV16, 0x1590)
        for twin in twins:
            m.far_call(LOAD + 0x358E, 0x18D8, (REC, twin))
        for k, (off, twin) in enumerate(zip(roster, twins)):
            got = [m.r16(REC, off + f) for f in fields if f not in (0x17F,)]
            want = [m.r16(REC, twin + f) for f in fields if f not in (0x17F,)]
            cd = m.r16(REC, off + 0x17F)
            count("战斗开始")
            check(got == want and any(m.r16(REC, off + p) for p in (0xFA, 0xFC, 0x112))
                  and cd == (0 if k in party else 0x99),
                  f"战斗开始 #{n} 成员 {k}: 与 18D8 的结果不同或倒计时 {cd:X}（{'在队' if k in party else '不在队'}）")
    print(f"战斗开始：{counts.get('战斗开始', 0)} 个成员重算后与 358E:18D8 的结果一致，在队成员的倒计时归零")


# ---- W16: the COMP level in the negotiation checks ----------------------------------------------------------------
TALK_KINDS = {0, 2, 3, 7, 8, 9, 10}                     # 直感 魔力 知力 敏捷性 器用 魅力 命运


def talk_tests():
    m = Machine()
    vm1, vm2 = 0x7000, 0x7100                           # the VM's state segments, [61A0h] and [61A2h]
    m.w16(DS, 0x61A0, vm1)
    m.w16(DS, 0x61A2, vm2)
    hero = m.unit(0, 0, 40)
    m.w16(DS, 0x9973, hero)
    m.w16(DS, 0x9975, REC)
    seg, bp = LOAD + 0x1603, 0xAA00
    for n in range(3000):
        kind = rng.randrange(15)
        sel = rng.choice([0xE0, 0xE3, 0xEB, 0xEC, 0xEF, 0x00, 0x03, 0xDE, 0xDF, 0xF0, 0xFF, 0x1E0])
        rec = rng.choice([0x44, 0x43, 0x45, 0x00, 0x144])
        swap = rng.random() < 0.2
        high = rng.random() < 0.1
        comp = rng.randrange(100)
        s = rng.randrange(1, 101) if kind != 11 else rng.randrange(1, 100)
        m.w16(vm1, 0x58, sel)
        m.w16(vm2, 0xCEA, rec)
        m.w16(REC, hero + 0x11A, comp)
        m.w16(DS, bp + 6, int(swap))
        m.w16(DS, bp - 2, 0x5555)
        m.w16(DS, bp - 0xC, s)
        m.w16(DS, bp - 0xA, int(high))
        m.run(seg, RB.TALK_CHECK_AT, seg * 16 + RB.TALK_CHECK_AT + 5, {"sp": bp - 0x16, "bp": bp, "si": kind})
        want = s
        if not swap and not high and 0xE0 <= sel <= 0xEF:
            if kind in TALK_KINDS:
                want = s * (100 + comp) // 100
            elif kind == 11 and sel == 0xEC and rec == 0x44:
                want = s * (200 + comp) // 200
        got = (m.r16(DS, bp - 0xC), m.r16(DS, bp - 0xA), m.r16(DS, bp - 2), m.mu.reg_read(X.UC_X86_REG_SI))
        count("W16 会话")
        check(got == (want, int(high), 0, kind),
              f"W16 会话 #{n} 种类 {kind} 选择子 {sel:X} 记录 {rec:X} 交换 {swap} COMP {comp} S {s}: "
              f"{got} != {(want, int(high), 0, kind)}")
    print(f"W16 会话：{counts.get('W16 会话', 0)} 例")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    shipped = open(os.path.join(SRC, RB.EXE_NAME), "rb").read()
    old = Machine(skillfix.mend_exe(statfix.apply_to(shipped)))
    w1_tests()
    crit_tests(old)
    hit_tests()
    damage_tests()
    magic_tests()
    seg25_tests()
    seg358_tests()
    growth_tests(old)
    summon_tests()
    battle_start_tests()
    talk_tests()
    print("OK" if not fails else f"{fails} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
