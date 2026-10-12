#!/usr/bin/env python3
"""moonfast_test.py - 月相加速 on an emulated CPU (unicorn): the game clock of the original DDS98.EXE and of the
one with tools/moonfast.py's sites in, driven through the same minutes, against a model of each.

The clock runs as shipped: 25CA:8A08 (the only thing that adds game minutes), 8A66, 8B56, 8B08 (the boxes of
ET0019), 8DC8, 8DFE with the C run-time's long multiply, the flag writer 1603:7EFA, and the new routine.
Only what 8B56 and 8A08 ask of the party records, the overlays and the scripts is stubbed, the same in
both programs: the hero's and the party slots' records (358E:507E, 514C) are blank ones, the roster lookup
(overlay thunk 07B1:0330) finds nobody, the per-phase timers (358E:A4D0) change nothing, the script
countdown, the body-part expiry and the heartless girl's drain (1603:C488, 25CA:F4CC, 358E:A378) return at
once, and the memory manager (0871:9326) hands 8B08 the list of ET0019. Checks:
  * a new game (25CA:8954), then thousands of calls of 8A08 - dungeon steps of 3-7 minutes, world-map moves,
    the idle minute, rests of 1440, the story's sleeps of 1520 - with a player who uses ソーマの杯 at
    once and 櫛名田の酒甕 now and then when they can, empties two of the monthly boxes whenever they are
    full, and uses コアシールド now and then: after every call each program's clock, moon, the flags the
    clock writes (00:23-26, 07:FD-FF, 07:F0/F1) and the fifteen box flags are what its model says - the
    patched model decides "passes through the full moon" from the age before the call and the phase
    changes it made, not by the routine's arithmetic;
  * the two programs against each other: コアシールド ends and the boxes fill at the same calls in both;
    the patched moon stands at ⌊T/300⌋ mod 28; each refill of the cup and the jar comes in the patched
    program in a call that ends in a visible full moon or passes through one, no earlier than the
    original's and before its next one, and that full moon began less than 8400 minutes after the
    original's refill - as many in both;
  * the same from a save made without the fix, loaded (25CA:8C86's store at 8CB4) into the patched program,
    and for a player who does nothing but rest, whose every call skips 4 or 5 visible phases;
  * 25CA:8DC8(N) followed by 8A08 of what it returns lands on age N with no minutes into the phase, from
    every age and several minutes into a phase, in both programs;
  * a load keeps the minutes into the phase modulo 300 in the patched program and as they are in the
    original, for the whole range a save can hold;
  * the program differs from the original at the sites alone, none of whose bytes a relocation touches,
    and moonfast.mend_exe(..., revert=True) gives the original file back; コアシールド's description in
    ET0001 turns to the new wording and back, the file keeping its length.

    moonfast_test.py [--image HDI]

With an image, the DDS98.EXE in it is the patched program - every other fix of the build in it too - and
the same file with this fix taken out (moonfast.mend_exe(..., revert=True)) the original.
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
import moonfast  # noqa: E402
import tables  # noqa: E402
from asm86 import assemble  # noqa: E402
from mz import MZ  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP
SP = 0xAB00                             # inside the startup stack
REC, LIST = 0xA000, 0xE000              # the blank records, ET0019's list
SENT = 0xD000                           # a hlt the far returns come back to
FLAGS = moonfast.FLAGS
PHASE, FAST = moonfast.PHASE, moonfast.FAST
ET0019 = open(os.path.join(WORK, "files", "DDS98", "ET0019.BIN"), "rb").read()
BOXES = [(ET0019[i], ET0019[i + 1]) for i in range(2, len(ET0019) - 2, 2)]
OPENED = BOXES[:2]                      # the boxes the player empties whenever they are full
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def image(blob):
    path = os.path.join(WORK, "build", "_moonfast_test.exe")
    with open(path, "wb") as f:
        f.write(blob)
    try:
        return bytes(MZ(path, base=LOAD).image), MZ(path).reloc_set
    finally:
        os.remove(path)


STUBS = {                               # (segment, offset): code; all far functions
    (0x358E, 0x507E): f"mov dx, {REC:#x}\nxor ax, ax\nretf 2",           # the hero's record
    (0x358E, 0x514C): f"mov dx, {REC:#x}\nmov ax, 0x200\nretf 2",        # a party slot's record
    (0x358E, 0xA4D0): "xor ax, ax\nretf 6",                              # the per-phase timers: nothing
    (0x07B1, 0x0330): "mov ax, 0xffff\nretf 2",                          # the roster: nobody
    (0x0871, 0x9326): f"mov dx, {LIST:#x}\nxor ax, ax\nretf 2",          # ET0019's list
    (0x1603, 0xC488): "retf 2",
    (0x25CA, 0xF4CC): "retf",
    (0x358E, 0xA378): "retf 2",
}


class Game:
    def __init__(self, blob):
        img, _relocs = image(blob)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x110000)
        self.mu.mem_write(LOAD * 16, img)
        for (seg, off), text in STUBS.items():
            self.mu.mem_write((LOAD + seg) * 16 + off, assemble(text, org=off)[0])
        self.mu.mem_write(LIST * 16, ET0019[2:])
        self.mu.mem_write(SENT * 16, b"\xf4")
        self.w16(0x22A2, 1)             # ET0019's handle: loaded

    def w16(self, off, v):
        self.mu.mem_write(DS * 16 + off, struct.pack("<H", v & 0xFFFF))

    def r16(self, off):
        return struct.unpack("<H", self.mu.mem_read(DS * 16 + off, 2))[0]

    def byte(self, off):
        return self.mu.mem_read(DS * 16 + off, 1)[0]

    def far(self, seg, off, args=(), regs=None):
        """Far call to image seg:off with args (pushed first to last); -> ax."""
        words = [0, SENT] + [a & 0xFFFF for a in reversed(args)]
        sp = SP - 2 * len(words)
        self.mu.mem_write(DS * 16 + sp, struct.pack(f"<{len(words)}H", *words))
        self.start(seg, off, SENT * 16, {"sp": sp, **(regs or {})})
        if self.mu.reg_read(X.UC_X86_REG_CS) != SENT:
            raise RuntimeError(f"{seg:04X}:{off:04X} did not come back")
        return self.mu.reg_read(X.UC_X86_REG_AX)

    def start(self, seg, off, stop, regs):
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, LOAD + seg), (X.UC_X86_REG_IP, off), (X.UC_X86_REG_BP, 0)):
            self.mu.reg_write(reg, v)
        for name, v in regs.items():
            self.mu.reg_write({"sp": X.UC_X86_REG_SP, "bp": X.UC_X86_REG_BP}[name], v)
        self.mu.emu_start((LOAD + seg) * 16 + off, stop, count=2_000_000)

    def flag(self, g, i):
        return int(bool(self.byte(FLAGS + g * 32 + (i >> 3)) & (0x80 >> (i & 7))))

    def set_flag(self, g, i, v):
        at = DS * 16 + FLAGS + g * 32 + (i >> 3)
        b = self.mu.mem_read(at, 1)[0]
        b = b | (0x80 >> (i & 7)) if v else b & ~(0x80 >> (i & 7))
        self.mu.mem_write(at, bytes([b]))

    def new_game(self):
        """25CA:8954 as the game runs it, then the flags as 1603:7E7E leaves them: groups 0-3 and 5-0Dh
        set, 4, 0Eh and 0Fh clear."""
        self.far(0x25CA, 0x8954)
        for g in range(16):
            self.mu.mem_write(DS * 16 + FLAGS + g * 32, (b"\x00" if g in (4, 14, 15) else b"\xff") * 32)

    def clock(self, m):
        self.far(0x25CA, 0x8A08, (m,))

    def until(self, age):
        """＠月齢計算: 25CA:8DC8(age), the minutes until that age begins."""
        return self.far(0x25CA, 0x8DC8, (age,))

    def load(self, minutes):
        """A save being loaded: 25CA:8C86 from the store of the minutes into the phase (8CB4) on."""
        bp = 0xA000
        self.w16(bp - 0xC, minutes)
        self.start(0x25CA, 0x8CB4, (LOAD + 0x25CA) * 16 + 0x8CBA, {"sp": SP, "bp": bp})
        return self.r16(0x98E8)

    def state(self):
        clk = bytes(self.mu.mem_read(DS * 16 + 0x98E4, 9))     # days (dword), phase minutes, age, hour, minute
        fl = bytes(self.mu.mem_read(DS * 16 + FLAGS, 0x200))

        def f(g, i):
            return int(bool(fl[g * 32 + (i >> 3)] & (0x80 >> (i & 7))))
        days, r = struct.unpack_from("<IH", clk, 0)
        return {"T": days * 1440 + clk[7] * 60 + clk[8], "r": r, "age": clk[6],
                **{f"00:{i:02X}": f(0, i) for i in (0x23, 0x24, 0x25, 0x26)},
                **{f"07:{i:02X}": f(7, i) for i in (0xF0, 0xF1, 0xFD, 0xFE, 0xFF)},
                "boxes": tuple(f(g, i) for g, i in BOXES)}


class Model:
    """What the clock is meant to do. fast=False: the original; fast=True: with the fix."""

    def __init__(self, fast, s):
        self.fast = fast
        self.s = dict(s)

    def clock(self, m):
        s = self.s
        s["T"] += m
        before = s["age"]
        q, s["r"] = divmod(s["r"] + m, FAST if self.fast else PHASE)
        s["age"] = (s["age"] + q) % 28
        s["00:23"], s["00:25"] = int(s["age"] != 14), int(s["age"] != 0)
        if q:
            if s["age"] == 14:
                s["00:24"] = 0
            if s["age"] == 0:
                s["00:26"] = 0
        if not self.fast:
            if q:
                s["07:FD"] = 0
                if s["age"] == 14:
                    s["07:FE"] = s["07:FF"] = 0
                if s["age"] == 15:
                    s["boxes"] = (0,) * len(BOXES)
            return
        if s["T"] % PHASE < m:                 # an original phase began
            s["07:FD"] = 0
            age = s["T"] // PHASE % 28
            if age == 14:
                s["07:F0"] = 0
            if age == 15:
                s["boxes"] = (0,) * len(BOXES)
        if not s["07:F0"] and full_moon(before, q, s["age"]):
            s["07:F0"] = 1
            s["07:FE"] = s["07:FF"] = 0


def full_moon(before, q, after):
    """Whether a call that took the visible moon from age `before` through q phase changes to `after` ends
    in the full moon (age 14) or passes through its start."""
    return after == 14 or any((before + j) % 28 == 14 for j in range(1, q + 1))


def minutes(rng):
    x = rng.random()
    if x < 0.80:
        return rng.randint(3, 7)                # a dungeon step (358E:858C: 3 + U(0..4))
    if x < 0.94:
        return 5 * rng.randint(1, 3)            # a world-map move
    if x < 0.975:
        return 1                                # the idle minute
    if x < 0.995:
        return 1440                             # a rest
    return 1520                                 # a story night


def rests(_rng):
    return 1440


def play(game, model, rng, calls, label, pace=minutes):
    """calls of 8A08 with a player acting between them; -> events {name: [call index]}, a log of
    (T after, age before, phase minutes before, minutes, age after) for every call, and the number of
    calls where the program and its model parted. The player's choices depend on the random stream
    alone, so both programs get the same ones."""
    events = {"shield_end": [], "cup": [], "jar": [], "boxes": []}
    log, bad = [], 0
    for n in range(calls):
        m = pace(rng)
        use_shield = rng.random() < 0.004
        use_jar = rng.random() < 0.5
        before = game.state()
        game.clock(m)
        model.clock(m)
        now = game.state()
        if now != model.s:
            if bad < 5:
                diff = {k: (now[k], model.s[k]) for k in now if now[k] != model.s[k]}
                print(f"  FAIL  {label}：第 {n} 次（+{m} 分钟）程序与模型不同 {diff}")
            bad += 1
        log.append((now["T"], before["age"], before["r"], m, now["age"]))
        if before["07:FD"] and not now["07:FD"]:
            events["shield_end"].append(n)
        if before["07:FE"] and not now["07:FE"]:
            events["cup"].append(n)
        if before["07:FF"] and not now["07:FF"]:
            events["jar"].append(n)
        if any(b and not a for b, a in zip(before["boxes"], now["boxes"])):
            events["boxes"].append(n)
        # the player
        if not now["07:FE"]:
            game.set_flag(7, 0xFE, 1)
        if not now["07:FF"] and use_jar:
            game.set_flag(7, 0xFF, 1)
        for g, i in OPENED:
            if not game.flag(g, i):
                game.set_flag(g, i, 1)
        if use_shield:
            game.set_flag(7, 0xFD, 1)
        model.s = game.state()          # carry on from what the program did and the player
    global fails
    fails += bad
    return events, log, bad


def compare(label, ev_old, ev_new, log_new):
    check(ev_old["shield_end"] == ev_new["shield_end"],
          f"{label}：核心护盾在同样的 {len(ev_old['shield_end'])} 次调用时失效")
    check(ev_old["boxes"] == ev_new["boxes"] and ev_old["boxes"],
          f"{label}：宝箱在同样的 {len(ev_old['boxes'])} 次调用时补满")
    for what in ("cup", "jar"):
        o, p = ev_old[what], ev_new[what]
        paired = len(p) <= len(o) and all(o[k] <= p[k] and (k + 1 >= len(o) or p[k] < o[k + 1])
                                          for k in range(len(p)))
        # the original's last one may still be waiting for a visible full moon when the run ends
        counts = len(p) == len(o) or (len(p) == len(o) - 1 and log_new[-1][0] - log_new[o[-1]][0] < 28 * FAST)
        full = all(full_moon(b, (r + m) // FAST, a) for _t, b, r, m, a in (log_new[k] for k in p))

        def turned_full(k):             # when the visible full moon of call k began
            t, _b, r, m, a = log_new[k]
            return t - ((a - 14) % 28 * FAST + (r + m) % FAST)
        late = max((turned_full(pk) - log_new[ok][0] for ok, pk in zip(o, p)), default=0)
        check(bool(o) and paired and counts and full and late < 28 * FAST,
              f"{label}：{ {'cup': '苏摩之杯', 'jar': '栉名田之酒瓮'}[what]} 原版 {len(o)} 次、加速后 {len(p)} 次，"
              f"每次都在原版那次之后、下一次之前，在可见的满月或经过满月的那次调用；那个满月最晚在原版之后 "
              f"{late} 分钟开始")


if "--image" in sys.argv:
    from fat12 import Fat12, open_hdi
    _raw, _hdr, disk, part = open_hdi(sys.argv[sys.argv.index("--image") + 1])
    fs = Fat12(disk, part)
    entry = fs.find("DDS98/" + moonfast.EXE)
    fixed = fs.read_chain(entry["cluster"], entry["size"])
    orig = moonfast.mend_exe(fixed, revert=True)
    check(fixed == moonfast.mend_exe(fixed), f"{sys.argv[sys.argv.index('--image') + 1]}: 修复已在程序里")
else:
    orig = open(os.path.join(WORK, "files", "DDS98", "DDS98.EXE"), "rb").read()
    fixed = moonfast.mend_exe(orig)

print("the program")
diff = [i for i in range(len(orig)) if orig[i] != fixed[i]]
sites = [(o, o + len(a)) for o, a, _b, _w in moonfast.EXE_SITES]
check(len(orig) == len(fixed) and all(any(lo <= i < hi for lo, hi in sites) for i in diff),
      f"differs from the original in {len(diff)} bytes, all inside the {len(sites)} sites")
_img, relocs = image(orig)
hdr = 0x3800
touched = [o for lo, hi in sites for o in range(lo - hdr - 1, hi - hdr) if o in relocs]
check(not touched, "no relocation touches a byte of any site")
check(moonfast.mend_exe(fixed, revert=True) == orig, "mend_exe(..., revert=True) gives the original back")
check(moonfast.exe_state(orig) == "orig" and moonfast.exe_state(fixed) == "fixed", "exe_state tells them apart")

print("コアシールド's description")
et1 = open(os.path.join(WORK, "files", "DDS98", moonfast.TABLE + ".BIN"), "rb").read()
forms = moonfast.desc_forms()
new_et1 = moonfast.mend_table(et1, forms)
(plain,) = tables.chunks_of(new_et1)
start, _end = moonfast.desc_at(plain)
text = plain[start:].split(b"\0")[0].decode("cp932")
check(len(new_et1) == len(et1) and text.startswith(moonfast.DESC_JP[1]) and text.endswith("無効化する。"),
      f"日文原版：{text}")
check(moonfast.mend_table(new_et1, forms, revert=True) == et1 and moonfast.mend_table(new_et1, forms) == new_et1,
      "改回去与原文件逐字节相同，再改一次不变")

print("a new game, both programs through the same minutes")
CALLS = 60000
old, new = Game(orig), Game(fixed)
for g in (old, new):
    g.new_game()
check(old.state() == new.state(), "新游戏时两边相同")
ev_old, _log, bad_old = play(old, Model(False, old.state()), random.Random(1), CALLS, "原版")
ev_new, log_new, bad_new = play(new, Model(True, new.state()), random.Random(1), CALLS, "加速后")
check(not bad_new and not bad_old, f"{CALLS} 次调用后两边都与各自的模型一致（总计 {old.state()['T']} 分钟）")
compare("新游戏", ev_old, ev_new, log_new)
s_old, s_new = old.state(), new.state()
check(s_old["T"] == s_new["T"], "两边的总分钟数相同")
check(s_new["T"] // FAST % 28 == s_new["age"] and s_new["r"] == s_new["T"] % FAST,
      f"加速后月龄 = ⌊T/{FAST}⌋ mod 28（{s_new['age']}），本相已过 {s_new['r']} 分钟")
check(s_old["T"] // PHASE % 28 == s_old["age"], f"原版月龄 = ⌊T/1520⌋ mod 28（{s_old['age']}）")

print("a save made without the fix, loaded into both programs")
old2, new2 = Game(orig), Game(fixed)
saved = old.state()
for g in (old2, new2):
    g.new_game()
    blob = bytes(old.mu.mem_read(DS * 16 + 0x98E4, 16))
    g.mu.mem_write(DS * 16 + 0x98E4, blob)
    g.mu.mem_write(DS * 16 + FLAGS, bytes(old.mu.mem_read(DS * 16 + FLAGS, 0x200)))
    g.load(saved["r"])
check(old2.state()["r"] == saved["r"] and new2.state()["r"] == saved["r"] % FAST
      and new2.state()["age"] == saved["age"],
      f"读档：原版本相已过 {saved['r']} 分钟，加速后取余为 {new2.state()['r']}，月龄仍是 {saved['age']}")
ev_old, _log, bad_old = play(old2, Model(False, old2.state()), random.Random(2), CALLS, "原版（读档后）")
ev_new, log_new, bad_new = play(new2, Model(True, new2.state()), random.Random(2), CALLS, "加速后（读档后）")
check(not bad_old and not bad_new, "读档后两边仍与各自的模型一致")
compare("读档后", ev_old, ev_new, log_new)

print(f"a player who does nothing but rest (1440 minutes, {1440 // FAST}-{-(-1440 // FAST)} visible phases a time)")
old3, new3 = Game(orig), Game(fixed)
for g in (old3, new3):
    g.new_game()
ev_old, _log, bad_old = play(old3, Model(False, old3.state()), random.Random(3), 3000, "原版（只休息）", rests)
ev_new, log_new, bad_new = play(new3, Model(True, new3.state()), random.Random(3), 3000, "加速后（只休息）", rests)
check(not bad_old and not bad_new, "只休息 3000 次，两边都与各自的模型一致")
compare("只休息", ev_old, ev_new, log_new)

print("＠月齢計算 lands on the age it names")
for label, g, length in (("原版", Game(orig), PHASE), ("加速后", Game(fixed), FAST)):
    g.new_game()
    ok, n = True, 0
    for start_age in range(28):
        for into in (0, 1, length // 2, length - 1):
            for target in range(28):
                g.mu.mem_write(DS * 16 + 0x98EA, bytes([start_age]))
                g.w16(0x98E8, into)
                m = g.until(target)
                g.clock(m)
                want = ((target - start_age - 1) % 28 + 1) * length - into
                ok &= g.byte(0x98EA) == target and g.r16(0x98E8) == 0 and m == want
                n += 1
    check(ok, f"{label}：{n} 种起点，8DC8 给的分钟数都正好走到那个月龄的开头（一相 {length} 分钟）")

print("a load keeps the minutes into the phase")
for label, g, want in (("原版", Game(orig), lambda v: v), ("加速后", Game(fixed), lambda v: v % FAST)):
    g.new_game()
    check(all(g.load(v) == want(v) for v in range(PHASE)),
          f"{label}：0-{PHASE - 1} 读进来都{'不变' if label == '原版' else f'取 {FAST} 的余数'}")

print("FAILED" if fails else "OK", f"({fails} failed)")
sys.exit(1 if fails else 0)
