#!/usr/bin/env python3
"""targetprompt_test.py - the add-on tools/targetprompt.py on the original DDS98.EXE, its two entries run on an
emulated CPU (unicorn) with 25CA:88DC (put a battle message up) and 358E:5236 (a member's unit) replaced by hooks
that note their arguments and return as the game's do, and the add-on put into and taken out of an image:

  * the program: every site holds the original before and the add-on after, nothing else differs, apply_to is
    idempotent and revert gives the original back; overlay 16 is found where tools/mz.py finds it; ov16:1C18 reads
    `mov word [1BBC],0Fh` then the unchanged `mov word [97D2],0`; the three far calls keep their segment words,
    which ov16 relocates; no relocation of the main image falls in 358E:411C-41B5; none of 411C, 4132, 415E occurs
    as a word anywhere in the original file, and no near call, jump or branch of segment 358E lands in
    411C-41B5; the sites lie apart from every site the build's own changes and the patch page's options write
    (their two forms) and from the 再平衡版's;
  * 358E:411C with the flag (cs:415E) clear puts record 0 of MS00D9.BIN up once - 88DC(D9h, 0, -1) - sets the
    flag, then calls 5236 with the member and returns its unit with the caller's stack; with the flag set it goes
    to 5236 alone; 358E:413F clears the flag and goes to 5236;
  * MS00D9.BIN: the game has no such file; message_file is one chunk with record 0, the question (the Chinese in
    the build's character map, the Japanese and the English in the game's own encoding) and a line end;
  * on an image (the Japanese dump): installed() is False; install() writes the sites and the file, installed()
    is True and a second install refuses; remove() gives the image's every file back as it was;
  * on each built image given: every site holds the original and the image has no MS00D9.BIN, install() and
    remove() give its every file back.

    targetprompt_test.py [--image HDI ...]
"""
import argparse
import os
import re
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_16, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ddsfile  # noqa: E402
import targetprompt as tp  # noqa: E402
from fat12 import open_hdi  # noqa: E402
from fat12w import Fat12W  # noqa: E402
from mz import MZ, overlays  # noqa: E402

SRC = os.path.join(WORK, "files", "DDS98")
JP = os.path.join(WORK, "inputs", "Japanese.hdi")
LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP
SEG358 = LOAD + tp.SEG
SEG25 = LOAD + 0x25CA
SENT = 0xD000                           # a hlt the entries' far returns come back to (in DGROUP)
UNIT_RET = (0x1234, 0x5678)             # dx:ax the 5236 hook hands back
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def tmp_copy(blob):
    path = os.path.join(WORK, "build", "_targetprompt_test.exe")
    with open(path, "wb") as f:
        f.write(blob)
    return path


def other_sites():
    """[file offset] every byte of DDS98.EXE the build's own changes, the patch page's options and the 再平衡版
    write."""
    import bagexpand, checkfix, ctxfree, exefix, exekeys, expgap, expshow, holdshow, moonfast, nospace  # noqa
    import rebalance, skillfix, slotorder, statfix, storyfix, vmswap  # noqa
    orig = open(os.path.join(SRC, tp.FILE), "rb").read()
    built = orig
    for step in (exefix.apply_to, storyfix.mend_exe, checkfix.mend_exe, statfix.apply_to, expshow.mend_exe,
                 nospace.apply_to, slotorder.apply_to, ctxfree.apply_to, vmswap.apply_to, bagexpand.apply_to,
                 skillfix.mend_exe, moonfast.mend_exe, exekeys.apply_to, holdshow.apply_to, expgap.mend_exe,
                 rebalance.mend_exe):
        built = step(built)
    return [i for i in range(len(orig)) if orig[i] != built[i]]


def program_checks(orig):
    print("== 程序")
    check(tp.state(orig) == "orig", "原版程序各处都是原样")
    fixed = tp.apply_to(orig)
    check(tp.state(fixed) == "fixed", "加装后各处都是新内容")
    check(tp.apply_to(fixed) == fixed, "apply_to 重复执行不变")
    check(tp.apply_to(fixed, revert=True) == orig, "revert 退回原版程序")
    mine = set()
    for at, o, _f in tp.sites(orig):
        mine |= set(range(at, at + len(o)))
    diff = [i for i in range(len(orig)) if orig[i] != fixed[i]]
    check(set(diff) <= mine, f"只有本项的各处有变化（{len(diff)} 字节）")
    others = set(other_sites())
    check(not (others & mine), f"和各个开关、再平衡版改动的字节不重叠（它们共 {len(others)} 字节）")
    path = tmp_copy(orig)
    try:
        ov = overlays(path)[16]
        main = MZ(path)
    finally:
        os.remove(path)
    check(tp.ov_offset(orig) == ov.file_off + ov.hdr, "覆盖段 16 的位置与 tools/mz.py 一致")
    o16 = tp.ov_offset(fixed)
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    ins = list(md.disasm(fixed[o16 + 0x1C18:o16 + 0x1C24], 0x1C18))
    check([f"{i.mnemonic} {i.op_str}" for i in ins] ==
          ["mov word ptr [0x1bbc], 0xf", "mov word ptr [0x97d2], 0"],
          "ov16:1C18 每帧写 [1BBC]=15，接着照旧清 [97D2]")
    for kind, off, _o, _f, _why in tp.SITES:
        if kind == "ov16" and off != 0x1C18:
            check(off + 3 in ov.relocs and off + 1 not in ov.relocs and off + 2 not in ov.relocs,
                  f"ov16:{off:04X} 的段字由覆盖段重定位，偏移字不在重定位里")
    lo, hi = tp.SEG * 16 + 0x411C, tp.SEG * 16 + 0x41B6
    check(not [r for r in main.reloc_set if lo <= r < hi], "358E:411C-41B5 里没有重定位")
    for entry in (0x411C, 0x4132, 0x415E):
        n = len(re.findall(re.escape(struct.pack("<H", entry)), orig))
        check(n == 0, f"整个原版文件里没有 {entry:04X} 这个字（{n}）")
    seg = bytes(main.image[tp.SEG * 16:tp.SEG * 16 + 0x10000])
    into = []
    for i in md.disasm(seg, 0):
        if (i.mnemonic.startswith("j") or i.mnemonic in ("call", "loop", "jcxz")) and i.op_str.startswith("0x"):
            t = int(i.op_str, 16)
            if 0x411C <= t < 0x41B6 and not 0x411C <= i.address < 0x41B6:
                into.append(i.address)
    check(not into, f"358E 段里没有近调用 / 跳转进 411C-41B5（{', '.join(f'{a:04X}' for a in into) or '无'}）")
    return fixed


def run_entry(image, entry, flag):
    """Call 358E:entry with member 3 and the flag; -> (88DC calls, 5236 calls, flag after, dx:ax, sp ok)."""
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 0x100000)
    uc.mem_write(LOAD * 16, image)
    uc.mem_write(DS * 16 + SENT, b"\xf4")
    uc.mem_write(SEG358 * 16 + tp.FLAG, bytes([flag]))
    shown, units = [], []

    def far_ret(pops):
        sp, ss = uc.reg_read(X.UC_X86_REG_SP), uc.reg_read(X.UC_X86_REG_SS)
        ip, cs = struct.unpack("<HH", uc.mem_read(ss * 16 + sp, 4))
        uc.reg_write(X.UC_X86_REG_SP, sp + 4 + pops)
        uc.reg_write(X.UC_X86_REG_CS, cs)
        uc.reg_write(X.UC_X86_REG_IP, ip)

    def hook(_uc, addr, _size, _data):
        sp, ss = uc.reg_read(X.UC_X86_REG_SP), uc.reg_read(X.UC_X86_REG_SS)
        if addr == SEG25 * 16 + tp.SHOW:
            count, rec, fil = struct.unpack("<HHH", uc.mem_read(ss * 16 + sp + 4, 6))
            shown.append((fil, rec, count, uc.reg_read(X.UC_X86_REG_DS)))
            far_ret(6)
        elif addr == SEG358 * 16 + tp.UNIT:
            units.append(struct.unpack("<H", uc.mem_read(ss * 16 + sp + 4, 2))[0])
            uc.reg_write(X.UC_X86_REG_DX, UNIT_RET[0])
            uc.reg_write(X.UC_X86_REG_AX, UNIT_RET[1])
            far_ret(2)

    uc.hook_add(UC_HOOK_CODE, hook)
    for reg, val in ((X.UC_X86_REG_DS, DS), (X.UC_X86_REG_SS, DS), (X.UC_X86_REG_ES, DS)):
        uc.reg_write(reg, val)
    sp = 0xC000 - 2
    uc.mem_write(DS * 16 + sp, struct.pack("<H", 3))                       # the member
    sp -= 4
    uc.mem_write(DS * 16 + sp, struct.pack("<HH", SENT, DS))               # far return to the hlt
    uc.reg_write(X.UC_X86_REG_SP, sp)
    uc.reg_write(X.UC_X86_REG_CS, SEG358)
    uc.reg_write(X.UC_X86_REG_IP, entry)
    uc.emu_start(SEG358 * 16 + entry, DS * 16 + SENT, count=2000)
    dx, ax = uc.reg_read(X.UC_X86_REG_DX), uc.reg_read(X.UC_X86_REG_AX)
    flag_after = uc.mem_read(SEG358 * 16 + tp.FLAG, 1)[0]
    return shown, units, flag_after, (dx, ax), uc.reg_read(X.UC_X86_REG_SP) == 0xC000


def entry_checks(fixed):
    print("== 两个入口（unicorn）")
    path = tmp_copy(fixed)
    try:
        image = bytes(MZ(path, base=LOAD).image)
    finally:
        os.remove(path)
    check(image[tp.SEG * 16 + tp.FLAG] == 0, "程序里的标志初值为 0")
    shown, units, flag, ret, sp_ok = run_entry(image, tp.CAVE, 0)
    check(shown == [(tp.MSG_NO, tp.RECORD, 0xFFFF, DS)], f"选对象第一帧：88DC(D9h, 0, -1) 恰好一次（{shown}）")
    check(units == [3] and ret == UNIT_RET and sp_ok and flag == 1,
          "接着以同一成员调用 5236，返回它的单位，栈平衡，标志置 1")
    shown, units, flag, ret, sp_ok = run_entry(image, tp.CAVE, 1)
    check(not shown and units == [3] and ret == UNIT_RET and sp_ok and flag == 1, "标志已置：只调用 5236")
    shown, units, flag, ret, sp_ok = run_entry(image, tp.CLEAR, 1)
    check(not shown and units == [3] and ret == UNIT_RET and sp_ok and flag == 0, "菜单的入口：清标志，再调用 5236")


def message_checks():
    print("== MS00D9.BIN")
    check(not os.path.exists(os.path.join(SRC, tp.MSG_FILE)), "原版没有这个文件")
    for label, charmap, english in (("日文", None, False), ("英文", None, True)):
        parsed = ddsfile.parse(tp.message_file(charmap, english))
        ok = (len(parsed) == 1 and len(parsed[0]) == 1 and parsed[0][0].rid == tp.RECORD
              and parsed[0][0].cond is None and parsed[0][0].payload == tp.payload(charmap, english)
              and parsed[0][0].payload.endswith(b"\x0a\x00"))
        check(ok, f"{label}：一个块，记录 0 是问话加换行")
    check(tp.payload(None, True) == b"Use on whom?\n\x00" and
          tp.payload(None, False) == "誰に使いますか？\n".encode("cp932") + b"\x00", "日文、英文的问话")


def image_checks():
    print("== 镜像上加装与卸载（日文 dump）")
    raw, hdr, disk, part = open_hdi(JP)
    fs = Fat12W(disk, part)
    before = {n: bytes(fs.read_chain(e["cluster"], e["size"])) for n, e in fs.walk()}
    check(tp.installed(fs) is False, "未加装")
    tp.install(fs, tp.message_file(None))
    check(tp.installed(fs) is True and tp.read(fs, f"DDS98/{tp.MSG_FILE}") == tp.message_file(None),
          "加装后：程序改好，MS00D9.BIN 在")
    try:
        tp.install(fs, tp.message_file(None))
        check(False, "第二次加装被拒绝")
    except tp.TargetPromptError:
        check(True, "第二次加装被拒绝")
    tp.remove(fs)
    after = {n: bytes(fs.read_chain(e["cluster"], e["size"])) for n, e in fs.walk()}
    check(after == before, "卸载后每个文件都和原来一样")


def built_checks(path):
    print(f"== 构建的镜像：{os.path.basename(path)}")
    raw, hdr, disk, part = open_hdi(path)
    fs = Fat12W(disk, part)
    before = {n: bytes(fs.read_chain(e["cluster"], e["size"])) for n, e in fs.walk()}
    exe = tp.read(fs, f"{tp.DIR}/{tp.FILE}")
    check(tp.state(exe) == "orig" and tp.installed(fs) is False, "程序各处都是原样，没有 MS00D9.BIN（未加装）")
    tp.install(fs, tp.message_file(None))
    check(tp.installed(fs) is True and tp.state(tp.read(fs, f"{tp.DIR}/{tp.FILE}")) == "fixed", "加装后程序改好")
    tp.remove(fs)
    after = {n: bytes(fs.read_chain(e["cluster"], e["size"])) for n, e in fs.walk()}
    check(after == before, "卸载后每个文件都和原来一样")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--image", action="append", default=[])
    a = ap.parse_args()
    orig = open(os.path.join(SRC, tp.FILE), "rb").read()
    fixed = program_checks(orig)
    entry_checks(fixed)
    message_checks()
    image_checks()
    for path in a.image:
        built_checks(path)
    print(f"{'全部通过' if not fails else f'{fails} 项失败'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
