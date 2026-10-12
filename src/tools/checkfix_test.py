#!/usr/bin/env python3
"""checkfix_test.py - 剧情检定修复's experience handler on an emulated CPU (unicorn), in the original
DDS98.EXE and with tools/checkfix.py's sites in.

Command 23A (1603:A354) is entered after its three operands are read, at its dispatch (1603:A382), with
what they leave there: di the field, si and [bp-6] the character record, [bp-4] and dx the value
(1603:9B28's dx:ax). The run stops at the command's exit 1603:A718. Checks:
  * field 50h writes nothing in the original and the whole dword at +6Eh in the mended program -
    values above FFFFh included - and nothing else in the record;
  * fields 0Ah (Macca, +72h) and 0Ch (MAG, +76h), whose handlers the new one copies, write the same
    in both;
  * a field with no handler (0Bh) still writes nothing;
  * the field table 1603:A398 differs in field 50h's entry alone;
  * checkfix.mend_exe(..., revert=True) gives the original file back.
"""
import os
import struct
import sys

from unicorn import UC_ARCH_X86, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import checkfix  # noqa: E402
from mz import MZ  # noqa: E402

LOAD = 0x1000
SEG = LOAD + 0x1603
FRAME, REC = 0x9000, 0xA000             # the stack segment of 23A's frame, the record's segment
BP = 0x0100
DISPATCH, EXIT = 0xA382, 0xA718
TABLE, FIELDS = 0xA398, 0x54
RECORD = bytes((i * 7 + 3) & 0xFF for i in range(0x200))
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def image(blob):
    path = os.path.join(WORK, "build", "_checkfix_test.exe")
    with open(path, "wb") as f:
        f.write(blob)
    img = bytes(MZ(path, base=LOAD).image)
    os.remove(path)
    return img


def dispatch(img, field, value):
    """The record after 23A's dispatch for one field and value, and where the run stopped."""
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x110000)
    mu.mem_write(LOAD * 16, img)
    mu.mem_write(REC * 16, RECORD)
    mu.mem_write(FRAME * 16 + BP - 6, struct.pack("<3H", REC, value & 0xFFFF, value >> 16))
    for reg, v in ((X.UC_X86_REG_CS, SEG), (X.UC_X86_REG_IP, DISPATCH), (X.UC_X86_REG_SS, FRAME),
                   (X.UC_X86_REG_SP, BP - 0x0C), (X.UC_X86_REG_BP, BP), (X.UC_X86_REG_DS, FRAME),
                   (X.UC_X86_REG_ES, 0), (X.UC_X86_REG_SI, 0), (X.UC_X86_REG_DI, field),
                   (X.UC_X86_REG_AX, value & 0xFFFF), (X.UC_X86_REG_DX, value >> 16)):
        mu.reg_write(reg, v)
    mu.emu_start(SEG * 16 + DISPATCH, SEG * 16 + EXIT, count=200)
    at = (mu.reg_read(X.UC_X86_REG_CS), mu.reg_read(X.UC_X86_REG_IP))
    return bytes(mu.mem_read(REC * 16, len(RECORD))), at


def with_dword(off, value):
    out = bytearray(RECORD)
    out[off:off + 4] = struct.pack("<I", value)
    return bytes(out)


src = open(os.path.join(checkfix.SRC, checkfix.EXE), "rb").read()
mended = checkfix.mend_exe(src)
old, new = image(src), image(mended)

print("命令 23A 按字段分派（1603:A382 起，停在出口 1603:A718）")
for value in (0x0000_4E20, 0x0001_2345, 0x00FF_FFFF):
    for label, img, want in (("原版", old, RECORD), ("修复后", new, with_dword(0x6E, value))):
        got, at = dispatch(img, 0x50, value)
        check(at == (SEG, EXIT) and got == want,
              f"{label} 字段 50h 写 {value:#010x}：+6Eh = {struct.unpack_from('<I', got, 0x6E)[0]:#010x}"
              f"{'，其余不变' if got[:0x6E] + got[0x72:] == RECORD[:0x6E] + RECORD[0x72:] else '，别处也被改了'}")
for field, off, name in ((0x0A, 0x72, "魔货"), (0x0C, 0x76, "ＭＡＧ")):
    for label, img in (("原版", old), ("修复后", new)):
        got, at = dispatch(img, field, 0x0003_0201)
        check(at == (SEG, EXIT) and got == with_dword(off, 0x0003_0201),
              f"{label} 字段 {field:02X}h（{name}）写进 +{off:X}h")
for label, img in (("原版", old), ("修复后", new)):
    got, at = dispatch(img, 0x0B, 0x1234)
    check(at == (SEG, EXIT) and got == RECORD, f"{label} 字段 0Bh（没有处理例程）什么都不写")

print("字段表 1603:A398")
base = SEG * 16 - LOAD * 16 + TABLE
t_old = struct.unpack_from(f"<{FIELDS}H", old, base)
t_new = struct.unpack_from(f"<{FIELDS}H", new, base)
diff = [i for i in range(FIELDS) if t_old[i] != t_new[i]]
check(diff == [0x50 - 0x0A] and t_old[0x46] == EXIT and t_new[0x46] == checkfix.EXP_AT,
      f"只有字段 50h 的入口不同：{t_old[0x46]:04X} -> {t_new[0x46]:04X}")

print("还原")
check(checkfix.mend_exe(mended, revert=True) == src, "关闭后与原版逐字节相同")
check(checkfix.mend_exe(mended) == mended, "再次启用不再改动")

print(f"失败 {fails} 项")
sys.exit(1 if fails else 0)
