#!/usr/bin/env python3
"""statfix_test.py - run the routines that tools/statfix.py changes, original and fixed, on an emulated CPU
with the game's own item and skill tables, and check every fix against what it has to do.

Both DDS98.EXE builds are loaded as DOS loads them (load segment, relocations applied) and run with
SS = DS = DGROUP as the game does. ET0001 (items, original or fixed) and ET0004 (skills) sit in free memory
and the memory manager 0871:9326 answers handle 1 with the skill table and any other with the item table.

  装备属性码    358E:23DA (equipment and gem bonuses, through 25CA:E116), twice, for every piece of
                equipment: the fixed game gives +1 to the attribute its (fixed) code names and never touches a
                base value; everything else - multi-attribute codes, gems - comes out as in the original
  魔法命中/回避  358E:28EC and 358E:2926 add their bonus (the original drops it)
  魔法回避来源   358E:296E passes word 16 of the equipment bonuses (effects 37h/38h) to 2926
  防具特效36h   25CA:E4C2 over the three armour pieces with effect 36h adds their evasion a second time
  倍率溢出      358E:2E0A keeps the high word of the product
  速度下限      358E:1992's floor of 1 (from 1A69, the rounded speed in ax) holds a negative speed at 1 where the
                original keeps it as 65000-odd
  会心武器      25CA:crit_weapon for sword and gun attacks, sword-, gun- and magic-class skills, items and
                empty slots; then ov16:0000 itself, overlay 16 loaded and relocated, original and fixed
  攻击道具      25CA:item_setup for all 37 attack items: the header cache, 29C8..29D2 and the pointer it
                returns; 8F0E and 912E answer with the item's own header until 9278 ends the action; any
                other item leaves the cache alone
  状态道具      the decoder leaves +11h empty and puts the status in +17h (what 25CA:DFF2 now reads)
  剧情写能力值   1603:set_attr moves the base value with the current one; the loop of 2DD (1603:D527) no
                longer rewrites the base value
  灰的状态检查   358E:3C88, 3D36 and 3D7C, for every status on its own: the same answer as the original,
                except that 灰 (code 0) now answers 1 instead of 0
  分经验的人数   358E:4B7C(1) no longer counts a member with 灰; ov02:0000 (overlay 2 loaded and relocated),
                over staged party records, pays each counted member 2X/N as the original does, and when
                nobody can take a share it returns without the division by zero the original faults on
  程序经验      25CA:comp_exp, called as 07B1:0534 is (a stub in the thunk's place notes what ov02:129E would
                get): the eight COMP programs in a skill action (4 or 6) earn COMP instead of 魔法, anything else
                goes on as it came, and sp, bp, si, di come back as they were; then the two calls where they
                stand, 25CA:AD2B and ov16:2D8B (overlay 16 relocated), original and fixed
  重定位        no relocated word of DDS98.EXE or of an overlay lies in a changed byte, but the segment words of
                the two far calls 程序经验 points at 25CA"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import statfix  # noqa: E402
import tables  # noqa: E402
from asm86 import assemble  # noqa: E402
from mz import MZ, overlays  # noqa: E402
from unicorn import UC_ARCH_X86, UC_MODE_16, Uc  # noqa: E402
from unicorn import x86_const as X  # noqa: E402

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(WORK, "files", "DDS98")
LOAD = 0x1000
DS = LOAD + 0x48FC
BUF = LOAD + 0x4827                     # the item decoder's buffer segment (4827:0006)
ITEMS, SKILLS, REC, SENT = 0xB000, 0xC000, 0xA000, 0xD000
GEM_BASE = 156                          # DS:2FCE: gem n is item 156 + n (オニキス 157)
ATTR = ["直感", "精神力", "魔力", "知力", "加护", "力量", "体力", "敏捷性", "器用", "魅力", "命运"]
REGS = {"ax": X.UC_X86_REG_AX, "bx": X.UC_X86_REG_BX, "cx": X.UC_X86_REG_CX, "dx": X.UC_X86_REG_DX,
        "si": X.UC_X86_REG_SI, "di": X.UC_X86_REG_DI, "bp": X.UC_X86_REG_BP, "sp": X.UC_X86_REG_SP,
        "es": X.UC_X86_REG_ES}
failures = []


def check(ok, what):
    if not ok:
        failures.append(what)


class Machine:
    def __init__(self, exe, et0001, et0004):
        path = os.path.join(WORK, "build", "_statfix_test.exe")
        open(path, "wb").write(exe)
        image = bytes(MZ(path, base=LOAD).image)
        os.remove(path)
        (items,) = tables.chunks_of(et0001)
        skills = tables.chunks_of(et0004)[0]
        if len(items) > 0x10000 or len(skills) > 0x10000:
            raise SystemExit("表太大，放不下")
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x110000)
        self.mu.mem_write(LOAD * 16, image)
        self.mu.mem_write(ITEMS * 16, items)
        self.mu.mem_write(SKILLS * 16, skills)
        stub, _ = assemble(f"""
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
        """, org=0x9326)
        self.mu.mem_write((LOAD + 0x871) * 16 + 0x9326, stub)
        self.w16(DS, 0x29C0, 1)             # the skill table's handle
        self.w16(DS, 0x2F52, 2)             # the item table's handle
        self.w16(DS, 0x29C8, 0xFFFF)        # no cached skill header
        self.w16(DS, 0x637C, BUF)
        self.w16(DS, 0x2FCE, GEM_BASE)
        self.mu.mem_write(SENT * 16, b"\xf4")

    def w16(self, seg, off, v):
        self.mu.mem_write(seg * 16 + off, struct.pack("<H", v & 0xFFFF))

    def r16(self, seg, off):
        return struct.unpack("<H", self.mu.mem_read(seg * 16 + off, 2))[0]

    def s16(self, seg, off):
        return struct.unpack("<h", self.mu.mem_read(seg * 16 + off, 2))[0]

    def words(self, seg, off, n):
        return list(struct.unpack(f"<{n}h", self.mu.mem_read(seg * 16 + off, 2 * n)))

    def far_call(self, seg, off, args=(), regs=None):
        """Far call to image seg:off, args pushed in the order given; returns (ax, dx)."""
        stack = [0, SENT] + [a & 0xFFFF for a in reversed(args)]
        sp = 0xAB00 - 2 * len(stack)
        self.mu.mem_write(DS * 16 + sp, struct.pack(f"<{len(stack)}H", *stack))
        self._start(seg, off, {"sp": sp, **(regs or {})}, SENT * 16)
        return self.mu.reg_read(X.UC_X86_REG_AX), self.mu.reg_read(X.UC_X86_REG_DX)

    def run(self, seg, off, until, regs):
        """Run from image seg:off with the given registers until image seg:until."""
        self._start(seg, off, regs, (LOAD + seg) * 16 + until)

    def _start(self, seg, off, regs, stop):
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, LOAD + seg), (X.UC_X86_REG_IP, off)):
            self.mu.reg_write(reg, v)
        for name, v in regs.items():
            self.mu.reg_write(REGS[name], v)
        self.mu.emu_start((LOAD + seg) * 16 + off, stop, count=5_000_000)

    def decode(self, item):
        """The decoder's 0x46-byte buffer for one item (25CA:C1DA)."""
        ax, dx = self.far_call(0x25CA, 0xC1DA, (item,))
        check((dx, ax) == (BUF, 6), f"C1DA({item}) 返回 {dx:04X}:{ax:04X}")
        return bytes(self.mu.mem_read(dx * 16 + ax, 0x46))


def exe_bytes():
    return open(os.path.join(SRC, "DDS98.EXE"), "rb").read()


EXE = exe_bytes()
ET1 = open(os.path.join(SRC, "ET0001.BIN"), "rb").read()
ET4 = open(os.path.join(SRC, "ET0004.BIN"), "rb").read()
FEXE = statfix.apply_to(EXE)
FET1 = statfix.apply_table(ET1)
old = Machine(EXE, ET1, ET4)
new = Machine(FEXE, FET1, ET4)
_b25, _b16, _b35, AT = statfix.routines()
entries = tables.string_table(tables.chunks_of(ET1)[0])
fentries = tables.string_table(tables.chunks_of(FET1)[0])
skills = tables.string_table(tables.chunks_of(ET4)[0])
kind = {i: e[4] for i, e in enumerate(entries) if len(e) > 4}


def name(i):
    e = entries[i]
    return e[tables.ITEM_HEADER[e[4]]:].split(b"\0")[0].decode("cp932", "replace")


# ---- 重定位
mz = MZ(os.path.join(SRC, "DDS98.EXE"))
ovs = overlays(os.path.join(SRC, "DDS98.EXE"))
ov16 = ovs[16]
ov16_code = ov16.file_off + ov16.hdr
check(ov16_code == statfix.OV16, f"overlay 16 的代码在文件 0x{ov16_code:X}，statfix.OV16 是 0x{statfix.OV16:X}")
ov2 = ovs[2]
check(ov2.file_off + ov2.hdr == statfix.OV2, f"overlay 2 的代码在文件 0x{ov2.file_off + ov2.hdr:X}，statfix.OV2 是 "
      f"0x{statfix.OV2:X}")
for label, at, orig, _new in statfix.sites():
    home = [(n, o) for n, o in ovs.items() if o.file_off + o.hdr <= at < o.file_off + o.hdr + len(o.image)]
    if home:
        n, o = home[0]
        code = o.file_off + o.hdr
        span, relocs, where = range(at - code, at - code + len(orig)), o.relocs, f"overlay {n}"
    else:
        span, relocs, where = range(at - statfix.HDR, at - statfix.HDR + len(orig)), mz.reloc_set, "主程序"
    hit = [p for p in relocs if p in span or p + 1 in span]
    if label.startswith("程序经验"):
        # the far call's segment word, relocated, goes from 07B1 to 25CA on purpose: the loader and the overlay
        # manager (0871:03C9) add the same base to every relocated word
        check(hit == [span.start + 7] and _new[7:9] == struct.pack("<H", 0x25CA),
              f"{label}：{where} 的重定位字应当只有远调用的段字（{[hex(p) for p in hit]}）")
        continue
    check(not hit, f"{label}：{where} 的重定位字落在改动的字节里（{[hex(p) for p in hit]}）")

# ---- 装备属性码: 358E:23DA twice over a record whose first slot holds the item
CALLS = 2


def bonuses(m, slot):
    m.mu.mem_write(REC * 16 + 0x88, struct.pack("<11h", *([20] * 11)))
    for k in range(8):
        m.w16(REC, 0x1A2 + 4 * k, slot if k == 0 else 0xFFFF)
    for _ in range(CALLS):
        m.far_call(0x358E, 0x23DA, (REC, 0x88, REC, 0x1A2))
    return m.words(REC, 0x88, 11), m.words(REC, 0x9E, 11), m.words(REC, 0xCA, 11)


def onehot(i):
    return [1 if k == i else 0 for k in range(11)]


def fmt(arr):
    return " ".join(f"{ATTR[k]}{v:+d}" for k, v in enumerate(arr) if v) or "-"


gear = [i for i, k in sorted(kind.items()) if 11 <= k <= 19]
coded = {}
for i in gear:
    ob, ox, oz = bonuses(old, 0xF800 | i)
    nb, nx, nz = bonuses(new, 0xF800 | i)
    obuf, nbuf = old.decode(i), new.decode(i)
    oc, nc, idx = obuf[0x2C], nbuf[0x2C], obuf[0x12]
    check(nb == [20] * 11, f"#{i} {name(i)}：修复后基础值变了 {nb}")
    check(nz == oz, f"#{i} {name(i)}：宝石加成不同 {fmt(oz)} / {fmt(nz)}")
    if 1 <= nc <= 11:
        coded[i] = (oc, nc)
        wrong = [0] * 11 if idx == 0 else onehot(idx - 1)
        want = [a - w + h for a, w, h in zip(ox, wrong, onehot(nc - 1))]
        check(nx == want, f"#{i} {name(i)}：代码 {nc:#x} 应得 {fmt(want)}，实际 {fmt(nx)}")
        check(nx == onehot(nc - 1), f"#{i} {name(i)}：代码 {nc:#x} 却得 {fmt(nx)}")
        if 1 <= oc <= 11:
            bad = ob[10] - 20
            check(bad == (CALLS if idx == 0 else 0),
                  f"#{i} {name(i)}：原版基础命运 {ob[10]}（+12h = {idx}），与已知的错误不符")
    else:
        check(nx == ox and ob == [20] * 11, f"#{i} {name(i)}：代码 {nc:#x} 修复前后不同")
for n in range(1, 32):
    if GEM_BASE + n >= len(entries) or kind.get(GEM_BASE + n) != 9:
        continue
    o = bonuses(old, (n << 11) | 0x7FF)
    f = bonuses(new, (n << 11) | 0x7FF)
    check(o == f, f"宝石 {n}（#{GEM_BASE + n} {name(GEM_BASE + n)}）修复前后不同")
    check(f[0] == [20] * 11, f"宝石 {n}：基础值变了")
gems = sum(1 for n in range(1, 32) if kind.get(GEM_BASE + n) == 9)

# ---- 魔法命中 / 魔法回避: (魔力+知力)/2 and (知力+加护)/2 plus the bonus, clamped to 1..999
attrs = [10, 11, 30, 21, 30, 10, 10, 10, 10, 10, 10]
for m, label in ((old, "原版"), (new, "修复后")):
    m.mu.mem_write(REC * 16 + 0xE0, struct.pack("<11h", *attrs))
for bonus in (15, 0, -10, -100):
    for fn, base, what in ((0x28EC, 25, "魔法命中"), (0x2926, 25, "魔法回避")):
        got_new = new.far_call(0x358E, fn, (REC, 0xE0, bonus))[0]
        got_old = old.far_call(0x358E, fn, (REC, 0xE0, bonus))[0]
        check(got_new == max(1, base + bonus), f"{what} 加成 {bonus}：修复后 {got_new}")
        check(got_old == base, f"{what} 加成 {bonus}：原版 {got_old}（应不理会加成）")

# ---- 魔法回避来源: 296E's call of 2926 gets [bp-16h], word 16 of the bonus buffer at [bp-36h]
code = bytes(new.mu.mem_read((LOAD + 0x358E) * 16 + 0x2C87, 0x15))
check(code[:3] == bytes.fromhex("ff76ea") and 0x2C8A + 2 + code[4] == 0x2C99 and code[0x12:0x15] == b"\x90\x0e\xe8",
      f"358E:2C87 的改动不是 push [bp-16h] / jmp 2C99：{code.hex(' ')}")
body = bytes(new.mu.mem_read((LOAD + 0x358E) * 16 + 0x2997, 0x10))
check(body[:2] == b"\x6a\x30" and body[4:7] == bytes.fromhex("8d46ca"),
      f"358E:296E 的加成缓冲区不在 [bp-36h]（0x30 字节）：{body.hex(' ')}")
barrier = [i for i in sorted(kind) if kind[i] == 19 and new.decode(i)[0x2C] == 0x38]
for i in barrier:
    new.mu.mem_write(REC * 16 + 0x200, bytes(0x30))
    new.far_call(0x25CA, 0xE4C2, (i, REC, 0x200, 0))
    w = new.words(REC, 0x200, 24)
    check(w[16] == 20 and sum(map(abs, w)) == 20, f"#{i} {name(i)}：E4C2 应只给第 16 字 +20，实际 {w}")
check(len(barrier) == 1, f"效果 38h 的饰品 {len(barrier)} 件")

# ---- 防具特效36h: E4C2(item, buffer, 0) over the pieces with effect 36h
armour36 = [i for i in gear if entries[i][4] in range(14, 19) and old.decode(i)[0x2C] == 0x36]
check(len(armour36) == 3, f"效果 36h 的防具有 {len(armour36)} 件：{armour36}")
control = next(i for i in gear if entries[i][4] == 16 and old.decode(i)[0x2C] not in (0x36, 0x37, 0x38))
for i in armour36 + [control]:
    got = []
    for m in (old, new):
        m.mu.mem_write(REC * 16 + 0x200, bytes(0x30))
        m.far_call(0x25CA, 0xE4C2, (i, REC, 0x200, 0))
        got.append(m.words(REC, 0x200, 24))
    buf = old.decode(i)
    hit, ev = struct.unpack("b", buf[0x22:0x23])[0], struct.unpack("b", buf[0x33:0x34])[0]
    want = list(got[0])
    if i in armour36:
        want[2] -= hit
        want[4] += ev
    check(got[1] == want, f"#{i} {name(i)}：E4C2 原版 {got[0][:9]} 修复后 {got[1][:9]}")

# ---- 倍率溢出: 358E:2E0A(value, percent), a near procedure
for m in (old, new):
    m.mu.mem_write((LOAD + 0x358E) * 16 + 0xFFF0, b"\xf4")
for value, pct, want_old, want_new in ((250, 150, 1, 375), (219, 150, 1, 328), (218, 150, 327, 327),
                                        (656, 50, 1, 328), (655, 50, 327, 327), (999, 150, 187, 999)):
    got = []
    for m in (old, new):
        sp = 0xAB00 - 6
        m.mu.mem_write(DS * 16 + sp, struct.pack("<3H", 0xFFF0, pct, value))
        m.run(0x358E, 0x2E0A, 0xFFF0, {"sp": sp})
        got.append(m.mu.reg_read(X.UC_X86_REG_AX))
    check(got == [want_old, want_new], f"2E0A {value}×{pct}%：原版 {got[0]} 修复后 {got[1]}（应 {want_old} / {want_new}）")

# ---- 速度下限: 358E:1992's end, from the rounded speed (ax after 1603:40CE) to the value it keeps (si at 1A73)
for speed, want_old, want_new in ((-5, 0xFFFB, 1), (-1, 0xFFFF, 1), (0, 1, 1), (1, 1, 1), (17, 17, 17),
                                  (-32768, 0x8000, 1), (32767, 32767, 32767)):
    got = []
    for m in (old, new):
        m.run(0x358E, 0x1A69, 0x1A73, {"ax": speed & 0xFFFF})
        got.append(m.mu.reg_read(X.UC_X86_REG_SI))
    check(got == [want_old, want_new], f"速度 {speed}：原版 {got[0]} 修复后 {got[1]}（应 {want_old} / {want_new}）")

# ---- 会心武器: 25CA:crit_weapon(attacker) -> dx:ax, whose +23h is the bonus
def crit_of(i):
    return new.decode(i)[0x23]


sword = next(i for i in gear if kind[i] == 11 and crit_of(i))
gun = next(i for i in gear if kind[i] == 12 and crit_of(i))
bullet = next(i for i in sorted(kind) if kind[i] == 13)
item = next(i for i in sorted(kind) if kind[i] == 1)
sword_skill = next(i for i, s in enumerate(skills) if len(s) > 0x0F and s[0] >> 6 == 1)
gun_skill = next(i for i, s in enumerate(skills) if len(s) > 0x0F and s[0] >> 6 == 2)
magic_skill = next(i for i, s in enumerate(skills) if i and len(s) > 0x0F and s[0] >> 6 == 0)


def crit(kind_, act, sword_slot=sword, gun_slot=gun):
    new.mu.mem_write(REC * 16 + 0x181, bytes([kind_]))
    new.w16(REC, 0x182, act)
    new.w16(REC, 0x1B6, sword_slot)
    new.w16(REC, 0x1BA, gun_slot)
    ax, dx = new.far_call(0x25CA, AT["crit_weapon"], (REC, 0))
    return new.mu.mem_read(dx * 16 + ax + 0x23, 1)[0]


for label, args, want in (
        ("枪击（+182h 是子弹）", (2, bullet), crit_of(gun)),
        ("剑击", (1, sword), crit_of(sword)),
        ("剑击，+182h 带特技位", (1, 0x8000 | sword), crit_of(sword)),
        ("剑系特技", (4, 0x8000 | sword_skill), crit_of(sword)),
        ("枪系特技", (4, 0x8000 | gun_skill), crit_of(gun)),
        ("枪系特技（动作 6）", (6, 0x8000 | gun_skill), crit_of(gun)),
        ("道具", (5, item), crit_of(item)),
        ("剑击，剑栏空（7FFh）", (1, 0x7FFF, 0x7FF), 0),
        ("剑击，剑栏空（FFFFh）", (1, 0x7FFF, 0xFFFF), 0),
        ("枪击，枪栏空", (2, bullet, sword, 0xFFFF), 0),
        ("剑击，剑栏带宝石", (1, sword, (3 << 11) | sword), crit_of(sword))):
    got = crit(*args)
    check(got == want, f"会心 {label}：{got}，应为 {want}")
check(crit(4, 0x8000 | magic_skill) == crit_of(sword), "会心 魔法系特技：应取剑（该路径不会算会心）")

# ---- 会心武器 where it is called: ov16:0000(defender, attacker), overlay 16 in memory with its
# relocations applied as the overlay manager does - B₀ = the attacker's weapon's +23h minus the
# defender's five crit resistances (+37h)
OVSEG, DEF = 0x9000, 0xA100


def load_ov16(m, exe):
    path = os.path.join(WORK, "build", "_statfix_test_ov.exe")
    open(path, "wb").write(exe)
    ov = overlays(path)[16]
    os.remove(path)
    image = bytearray(ov.image)
    for p in ov.relocs:
        struct.pack_into("<H", image, p, (struct.unpack_from("<H", image, p)[0] + LOAD) & 0xFFFF)
    m.mu.mem_write(OVSEG * 16, bytes(image))


load_ov16(old, EXE)
load_ov16(new, FEXE)
worn = [i for i in gear if kind[i] in range(14, 20) and new.decode(i)[0x37]]
worn = [next(i for i in worn if kind[i] == k) for k in (15, 16, 17, 18, 19) if any(kind[i] == k for i in worn)]
resist = sum(new.decode(i)[0x37] for i in worn)
for m in (old, new):
    for k in range(5):
        m.w16(DEF, 0x1A2 + 4 * k, 0xF800 | worn[k] if k < len(worn) else 0xFFFF)


def ov_crit(m, kind_, act):
    m.mu.mem_write(REC * 16 + 0x181, bytes([kind_]))
    m.w16(REC, 0x182, act)
    m.w16(REC, 0x1B6, 0xF800 | sword)
    m.w16(REC, 0x1BA, 0xF800 | gun)
    m.w16(DS, 0x29C8, 0xFFFF)
    ax, _dx = m.far_call(OVSEG - LOAD, 0x0000, (REC, 0, DEF, 0))
    return struct.unpack("<h", struct.pack("<H", ax))[0]


for label, args, want_old, want_new in (
        ("剑击", (1, sword), crit_of(sword), crit_of(sword)),
        ("枪击", (2, bullet), crit_of(bullet), crit_of(gun)),
        ("剑系特技", (4, 0x8000 | sword_skill), crit_of(sword_skill), crit_of(sword)),
        ("枪系特技", (4, 0x8000 | gun_skill), crit_of(gun_skill), crit_of(gun))):
    got_old, got_new = ov_crit(old, *args), ov_crit(new, *args)
    check((got_old, got_new) == (want_old - resist, want_new - resist),
          f"ov16:0000 {label}：原版 {got_old} 修复后 {got_new}，应为 {want_old - resist} / {want_new - resist}")
check(resist > 0, f"防具会心抗性 {resist}（{len(worn)} 件）")

# ---- 攻击道具: item_setup(item) with es:bx = the actor
attack = [i for i in sorted(kind) if kind[i] == 4]
check(len(attack) == 37, f"攻击道具 {len(attack)} 件")


def setup(m, i, magic_hit=37):
    m.w16(REC, 0x142, magic_hit)
    m.w16(DS, 0x29C8, 0xFFFF)
    m.w16(DS, 0x29CE, 99)
    m.w16(DS, 0x29D0, 88)
    m.w16(DS, 0x29D2, 5)
    m.mu.mem_write(DS * 16 + 0x838E, b"\xee" * 20)
    ax, dx = m.far_call(0x25CA, AT["item_setup"], (i,), {"es": REC, "bx": 0})
    return (dx, ax), bytes(m.mu.mem_read(DS * 16 + 0x838E, 20)), [m.r16(DS, 0x29C8 + 2 * k) for k in range(6)]


for i in attack:
    ret, hdr, cache = setup(new, i)
    e = entries[i]
    want = bytes([1, 0]) + e[5:0x17]
    check(ret == (BUF, 6), f"#{i} {name(i)}：item_setup 返回 {ret[0]:04X}:{ret[1]:04X}")
    check(hdr == want, f"#{i} {name(i)}：特技头 {hdr.hex(' ')}，应为 {want.hex(' ')}")
    check(cache == [i, want[9], want[10], 37, 37, 1], f"#{i} {name(i)}：29C8..29D2 = {cache}")
    ax, dx = new.far_call(0x25CA, 0x8F0E, (i,))
    check((dx, ax) == (DS, 0x838E), f"#{i} {name(i)}：8F0E 没有给出缓存的特技头")
    check(new.far_call(0x25CA, 0x912E, (i,))[0] == 0, f"#{i} {name(i)}：912E 不是 0（魔法类）")
    new.far_call(0x25CA, 0x9278)
    ax, dx = new.far_call(0x25CA, 0x8F0E, (i,))
    check((dx, ax) != (DS, 0x838E), f"#{i} {name(i)}：9278 之后 8F0E 仍给出缓存")
    check(skills[i][0] >> 6 == 0, f"#{i} {name(i)}：原版查到的特技 #{i} 不是魔法类（改后路径会不同）")
for i in (1, bullet, sword):
    ret, hdr, cache = setup(new, i)
    check(ret == (BUF, 6) and hdr == b"\xee" * 20 and cache == [0xFFFF, cache[1], cache[2], 99, 88, 5],
          f"#{i} {name(i)}：非攻击道具却动了特技头缓存 {cache}")

# ---- 状态道具: the decoder's +11h and +17h for every attack item
status_items = []
for i in attack:
    buf = new.decode(i)
    check(buf[0x11] == 0, f"#{i} {name(i)}：解码后 +11h = {buf[0x11]}")
    check(buf[0x17] == entries[i][0x10], f"#{i} {name(i)}：解码后 +17h = {buf[0x17]}，记录里是 {entries[i][0x10]}")
    if buf[0x14] == 0:
        status_items.append(i)
check(status_items == [74, 77, 79, 82, 91, 95, 106], f"威力 0 的攻击道具：{status_items}")
check(all(new.decode(i)[0x17] for i in status_items), "有威力 0 的攻击道具没有状态")
code = bytes(new.mu.mem_read((LOAD + 0x25CA) * 16 + 0xE01B, 3))
check(code == bytes.fromhex("a0c588"), f"25CA:E01B 不是 mov al, [88C5h]：{code.hex(' ')}")

# ---- 剧情写能力值: set_attr, then the loop of 2DD
for field, value, e0, b0 in ((0x19 + 5, 101, 100, 99), (0x19, 45, 50, 47), (0x19 + 10, 51, 50, 47)):
    new.mu.mem_write(REC * 16 + 0x88, struct.pack("<11h", *([47] * 11)))
    new.mu.mem_write(REC * 16 + 0xE0, struct.pack("<11h", *([50] * 11)))
    k = field - 0x19
    new.w16(REC, 0x88 + 2 * k, b0)
    new.w16(REC, 0xE0 + 2 * k, e0)
    bp = 0x9000
    new.w16(DS, bp - 6, REC)
    new.w16(DS, bp - 4, value)
    new.run(0x1603, AT["set_attr"], 0xA718, {"bp": bp, "si": 0, "di": field, "sp": 0x8F00})
    e, b = new.s16(REC, 0xE0 + 2 * k), new.s16(REC, 0x88 + 2 * k)
    check((e, b) == (value, b0 + value - e0), f"23A {ATTR[k]} {e0}→{value}：E {e}，基础 {b}")
    others = [v for j, v in enumerate(new.words(REC, 0x88, 11)) if j != k]
    check(others == [47] * 10, f"23A {ATTR[k]}：别的基础值变了")
for m, rewrites in ((old, True), (new, False)):
    base = [30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
    eq = [5] * 11
    cur = [60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70]
    m.mu.mem_write(REC * 16 + 0x88, struct.pack("<11h", *base))
    m.mu.mem_write(REC * 16 + 0x9E, struct.pack("<11h", *eq))
    m.mu.mem_write(REC * 16 + 0xB4, bytes(22))
    m.mu.mem_write(REC * 16 + 0xCA, struct.pack("<11h", *([2] * 11)))
    m.mu.mem_write(REC * 16 + 0xE0, struct.pack("<11h", *cur))
    bp = 0x9000
    m.w16(DS, bp - 2, REC)
    m.run(0x1603, 0xD527, 0xD54B, {"bp": bp, "di": 0, "sp": 0x8F00})
    got = m.words(REC, 0x88, 11)
    want = [c - 5 - 2 for c in cur] if rewrites else base
    check(got == want, f"2DD 循环（{'原版' if rewrites else '修复后'}）：基础值 {got}，应为 {want}")

# ---- 灰的状态检查 and 分经验的人数: six party records handed out by a stub of the slot lookup 358E:514C
# (put back afterwards); the status test 3CE4 and 35DC, the head count 4B7C, overlay 2 (loaded and relocated
# like overlay 16) and the C run-time's division run as shipped
PARTY, OV2SEG, NEAR_STOP = 0xE000, 0x8000, 0xFFF0
ASH = {0x3C88: [0x00, 0x01, 0x02], 0x3D36: [0x15, 0x06, 0x19, 0x0D, 0x0A, 0x03, 0x02, 0x01, 0x00, 0x14,
                                             0x0C, 0x05, 0x04, 0x13],
       0x3D7C: [0x02, 0x01, 0x00, 0x03, 0x04, 0x05, 0x06]}
EXCLUDED = [0x02, 0x01, 0x00, 0x03, 0x04, 0x05, 0x06]         # DS:2426, in its order
stub514c = assemble(f"""
    push bp
    mov bp, sp
    mov bx, word ptr [bp + 6]
    shl bx, 1
    shl bx, 1
    mov ax, word ptr [bx + 0xf000]
    mov dx, word ptr [bx + 0xf002]
    pop bp
    retf 2
""", org=0x514C)[0]
saved514c = {id(m): bytes(m.mu.mem_read((LOAD + 0x358E) * 16 + 0x514C, len(stub514c))) for m in (old, new)}
masks = bytes(new.mu.mem_read(DS * 16 + 0x42, 8))


def load_ov2(m, exe):
    path = os.path.join(WORK, "build", "_statfix_test_ov2.exe")
    open(path, "wb").write(exe)
    ov = overlays(path)[2]
    os.remove(path)
    image = bytearray(ov.image)
    for p in ov.relocs:
        struct.pack_into("<H", image, p, (struct.unpack_from("<H", image, p)[0] + LOAD) & 0xFFFF)
    m.mu.mem_write(OV2SEG * 16, bytes(image))
    m.mu.mem_write((LOAD + 0x358E) * 16 + 0x514C, stub514c)


def stage(m, members):
    """members: six (level, experience, [status codes]) or None for an empty slot."""
    for i, mem in enumerate(members):
        if mem is None:
            m.w16(DS, 0xF000 + 4 * i, 0)
            m.w16(DS, 0xF002 + 4 * i, 0)
            continue
        level, exp, statuses = mem
        rec = bytearray(0x200)
        rec[0x6B] = level
        struct.pack_into("<I", rec, 0x6E, exp)
        for c in statuses:
            rec[0x156 + (c >> 3)] |= masks[c & 7]
        m.mu.mem_write(PARTY * 16 + i * 0x200, bytes(rec))
        m.w16(DS, 0xF000 + 4 * i, i * 0x200)
        m.w16(DS, 0xF002 + 4 * i, PARTY)


def exp_of(m, i):
    return struct.unpack("<I", bytes(m.mu.mem_read(PARTY * 16 + i * 0x200 + 0x6E, 4)))[0]


def share_out(m, total):
    """ov02:0000(total), a near procedure; None when it faults (a division by zero)."""
    stack = [NEAR_STOP, total & 0xFFFF, total >> 16]
    sp = 0xAB00 - 2 * len(stack)
    m.mu.mem_write(DS * 16 + sp, struct.pack(f"<{len(stack)}H", *stack))
    try:
        m.run(OV2SEG - LOAD, 0x0000, NEAR_STOP, {"sp": sp, "bp": 0})
    except Exception:  # noqa: BLE001 - unicorn's error for the CPU exception
        return None
    return True


for m, exe in ((old, EXE), (new, FEXE)):
    load_ov2(m, exe)
# every single status on its own, through each of the three checks
for wrapper, codes in ASH.items():
    for status in range(0x23):
        got = []
        for m in (old, new):
            stage(m, [(10, 0, [status])] + [None] * 5)
            ax, _dx = m.far_call(0x358E, wrapper, (PARTY, 0x156))      # the status bits of record 0
            got.append(ax)
        want_old = status if status in codes else 0
        want_new = (1 if status == 0 else status) if status in codes else 0
        check(got == [want_old, want_new], f"358E:{wrapper:04X} 状态 {status:02X}：原版 {got[0]} 修复后 {got[1]}，"
              f"应为 {want_old} / {want_new}")
# the head count and the share-out
for label, members, total in (
        ("三人，其中一人化灰", [(10, 1000, []), (11, 2000, [0x00]), (12, 5000, []), None, None, None], 90),
        ("五人，死、石化、中毒各一", [(10, 1000, []), (11, 2000, [0x01]), (9, 800, [0x04]), (12, 5000, [0x0F]),
                                   (8, 900, []), None], 91),
        ("全员不能领：死、石化、麻痹", [(10, 1000, [0x01]), (11, 2000, [0x04]), (12, 5000, [0x05]), None, None,
                                     None], 60),
        ("只剩化灰的人：死、灰、麻痹", [(10, 1000, [0x01]), (11, 2000, [0x00]), (12, 5000, [0x05]), None, None,
                                     None], 60)):
    for m, ash_counts in ((old, True), (new, False)):
        stage(m, members)
        counted = [i for i, mem in enumerate(members) if mem and (
            not any(c in mem[2] for c in EXCLUDED if c) and (ash_counts or 0x00 not in mem[2]))]
        n, _dx = m.far_call(0x358E, 0x4B7C, (1,))
        check(n == len(counted), f"{label}（{'原版' if ash_counts else '修复后'}）：4B7C(1) = {n}，应为 {len(counted)}")
        before = [exp_of(m, i) if mem else None for i, mem in enumerate(members)]
        ok = share_out(m, total)
        if not counted:
            check((ok is None) == ash_counts,
                  f"{label}（{'原版' if ash_counts else '修复后'}）：发放{'没有' if ok else ''}除以零")
            if ok:
                check(all(exp_of(m, i) == before[i] for i, mem in enumerate(members) if mem),
                      f"{label}（修复后）：没人能领，却有人得到经验")
            continue
        share = 2 * total // len(counted)
        for i, mem in enumerate(members):
            if mem:
                want = share if i in counted else 0
                check(exp_of(m, i) - before[i] == want,
                      f"{label}（{'原版' if ash_counts else '修复后'}）：第 {i} 人得到 {exp_of(m, i) - before[i]}，"
                      f"应为 {want}")
for m in (old, new):
    m.mu.mem_write((LOAD + 0x358E) * 16 + 0x514C, saved514c[id(m)])

# ---- 程序经验: the thunk 07B1:0534 (ov02:129E: amount, skill, unit; retf 8) jumps to a stub that notes the
# arguments it is entered with (DS:F100..F106) and counts its calls (F108); put back afterwards
NOTE = 0xF800
note = assemble("""
    push bp
    mov bp, sp
    push ax
    mov ax, word ptr [bp + 6]
    mov word ptr [0xf100], ax
    mov ax, word ptr [bp + 8]
    mov word ptr [0xf102], ax
    mov ax, word ptr [bp + 0xa]
    mov word ptr [0xf104], ax
    mov ax, word ptr [bp + 0xc]
    mov word ptr [0xf106], ax
    inc word ptr [0xf108]
    pop ax
    pop bp
    retf 8
""", org=0)[0]
THUNK = (LOAD + 0x07B1) * 16 + 0x534
saved_thunk = {id(m): bytes(m.mu.mem_read(THUNK, 5)) for m in (old, new)}
for m in (old, new):
    m.mu.mem_write(NOTE * 16, note)
    m.mu.mem_write(THUNK, b"\xea" + struct.pack("<HH", 0, NOTE))
programs = [i for i, s in enumerate(skills) if len(s) > 0x0F and s[0] >> 6 == 3 and s[1] == 32]
check(programs == list(range(158, 166)), f"COMP 程序（第 3 类、系统 32）：{programs}")


UNIT = 0x40                             # the caster at REC:0040, so the pointer's offset is checked too


def staged(m, kind_, act):
    m.mu.mem_write(REC * 16 + UNIT + 0x181, bytes([kind_]))
    m.w16(REC, UNIT + 0x182, act)
    m.w16(DS, 0x29C8, 0xFFFF)
    m.w16(DS, 0xF108, 0)
    m.mu.mem_write(DS * 16 + 0xF100, bytes(8))


def noted(m):
    return [m.r16(DS, 0xF100 + 2 * k) for k in range(5)]


# comp_exp itself, called as the two sites call 07B1:0534
for label, kind_, act, skill, amount, want in (
        [(f"程序 #{i}", 4, 0x8000 | i, 2, 3, 3) for i in programs]
        + [(f"程序 #{i}（动作 6）", 6, 0x8000 | i, 2, 3, 3) for i in programs]
        + [("程序，经验量 7", 4, 0x8000 | 158, 2, 7, 3),
           ("程序，+182h 无特技位", 4, 158, 2, 3, 3),
           ("魔法", 4, 0x8000 | magic_skill, 2, 3, 2),
           ("剑系特技", 4, 0x8000 | sword_skill, 2, 3, 2),
           ("道具，编号同程序", 5, 158, 2, 3, 2),
           ("剑击", 1, sword, 2, 3, 2)]
        + [(f"程序，技能 {k}", 4, 0x8000 | 158, k, 3, k) for k in (0, 1, 3)]):
    staged(new, kind_, act)
    new.far_call(0x25CA, AT["comp_exp"], (REC, UNIT, skill, amount), {"bp": 0x1234, "si": 0x5678, "di": 0x9ABC})
    regs = [new.mu.reg_read(r) for r in (X.UC_X86_REG_SP, X.UC_X86_REG_BP, X.UC_X86_REG_SI, X.UC_X86_REG_DI,
                                         X.UC_X86_REG_DS)]
    check(noted(new) == [amount, want, UNIT, REC, 1], f"comp_exp {label}：129E 收到 {noted(new)}，"
          f"应为 {[amount, want, UNIT, REC, 1]}")
    check(regs == [0xAB00, 0x1234, 0x5678, 0x9ABC, DS], f"comp_exp {label}：返回时 sp bp si di ds = "
          + " ".join(f"{v:04X}" for v in regs))
# the two calls where they stand: 25CA:AD23-AD30 (status-only path; unit [bp+0Ch]:di) and ov16:2D83-2D90 (the
# damage path; unit [bp+0Ch]:si), original and fixed
bp = 0x9000
for label, kind_, act, want_new in (("程序", 4, 0x8000 | 160, 3), ("程序（动作 6）", 6, 0x8000 | 165, 3),
                                    ("魔法", 4, 0x8000 | magic_skill, 2), ("道具", 5, 160, 2)):
    for where, seg, start, stop, unit in (("25CA:AD2B", 0x25CA, 0xAD23, 0xAD30, "di"),
                                          ("ov16:2D8B", OVSEG - LOAD, 0x2D83, 0x2D90, "si")):
        for m, want in ((old, 2), (new, want_new)):
            staged(m, kind_, act)
            m.w16(DS, bp + 0xC, REC)
            m.run(seg, start, stop, {"bp": bp, "sp": 0x8F00, unit: UNIT})
            sp = m.mu.reg_read(X.UC_X86_REG_SP)
            check(noted(m) == [3, want, UNIT, REC, 1] and sp == 0x8F00,
                  f"{where} {label}（{'原版' if m is old else '修复后'}）：129E 收到 {noted(m)}，sp {sp:04X}，"
                  f"应为 {[3, want, UNIT, REC, 1]}，8F00")
for m in (old, new):
    m.mu.mem_write(THUNK, saved_thunk[id(m)])

# ---- the data behind the descriptions
swords_mh = sum(1 for i in gear if kind[i] == 11 and new.decode(i)[0x34])
guns_crit = sum(1 for i in gear if kind[i] == 12 and new.decode(i)[0x23])
acc_ev = sum(1 for i in gear if kind[i] == 19 and new.decode(i)[0x33])
mev = [i for i in gear if new.decode(i)[0x2C] in (0x37, 0x38)]
changed = {i: c for i, c in coded.items() if c[0] != c[1]}
print(f"装备 {len(gear)} 件、宝石 {gems} 种；单属性代码 {len(coded)} 件，其中改码 {len(changed)} 件："
      + "，".join(f"#{i} {name(i)} {a:#x}→{b:#x}" for i, (a, b) in changed.items()))
print(f"带魔法命中的剑 {swords_mh} 把；带会心的枪 {guns_crit} 把；带回避的饰品 {acc_ev} 件；效果 37h/38h："
      + "，".join(f"#{i} {name(i)} {new.decode(i)[0x2C]:#x}" for i in mev))
print(f"效果 36h 的防具：" + "，".join(f"#{i} {name(i)}" for i in armour36))
print(f"会心测试：剑 #{sword} {name(sword)} {crit_of(sword)}，枪 #{gun} {name(gun)} {crit_of(gun)}，"
      f"子弹 #{bullet} {name(bullet)} {crit_of(bullet)}；剑系特技 #{sword_skill}，枪系特技 #{gun_skill}；"
      f"ov16:0000 的守方穿 {len(worn)} 件会心抗性共 {resist} 的防具")
print(f"新增例程：25CA {len(_b25.rstrip(b'\x90'))} / {len(statfix.CAVE25_ORIG)} 字节，"
      f"1603 {len(_b16.rstrip(b'\x90'))} / {len(statfix.CAVE16_ORIG)} 字节，"
      f"358E {len(_b35.rstrip(b'\x90'))} / {len(statfix.CAVE35_ORIG)} 字节，入口 "
      + "，".join(f"{k} {v:04X}" for k, v in AT.items() if not k.startswith(("cw_", "is_", "ce_")) or k == "cw_zero"))
if failures:
    print("\n".join("  " + f for f in failures))
    print(f"未通过：{len(failures)} 项")
    sys.exit(1)
print(f"通过：装备 {len(gear)} 件，宝石 {gems} 种，攻击道具 {len(attack)} 件，会心 12 种，程序 {len(programs)} 个，其余各项")
