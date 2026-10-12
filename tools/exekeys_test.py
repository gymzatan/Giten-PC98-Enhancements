#!/usr/bin/env python3
"""exekeys_test.py - run the game's own routines that tools/exekeys.py changes, on an emulated CPU, with
the keyboard played by the test.

Both the original DDS98.EXE and the patched one are loaded as DOS loads them (load segment, relocations
applied). INT 21h is answered by the test from a key queue: AH=0Bh says whether a key waits, AH=08h and
AH=06h (DL=FF) take one, AH=0Ch empties the queue - and every call is logged.

  main 0x2B5F6  the map screen's key reader, entered with a near call: for every key it must return the
                button number the numeric keypad gives - W Z A D Q E S in either case like 8 2 4 6 7 9 5
                - and FFFF for anything else; the original must give the same for 1-9 and FFFF for letters
  main 0x2E0E4  one frame of a wait, entered with a far call, for modes 1 and 2 with the masks the game
                uses: the wait ends when the frame reaches main 0x2E147 (the call that ends it). Enter and
                Space must end it, other keys must not (and are used up), buttons must work as before
  main 0x2E150  setting a wait up: modes 1 and 2 must empty the queue before the state is pushed, modes
                0 and 3 must leave it, and AX must still be 1 at the call of main 0x2DD40"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exekeys  # noqa: E402
import unicorn as uc  # noqa: E402
from unicorn import x86_const as X  # noqa: E402
from mz import MZ  # noqa: E402

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(WORK, "files", "DDS98", "DDS98.EXE")
LOAD = 0x1000
DGROUP = 0x48FC
STACK_SEG, STACK_TOP = 0x9000, 0xFF00
SENTINEL_SEG, SENTINEL_OFF = 0x0800, 0x0010
TABLE = {"1": 6, "2": 2, "3": 4, "4": 3, "5": 5, "6": 1, "7": 6, "8": 0, "9": 4}
LETTERS = {"w": "8", "z": "2", "a": "4", "d": "6", "q": "7", "e": "9", "s": "5"}
failures = []


def check(ok, what):
    if not ok:
        failures.append(what)


class Machine:
    def __init__(self, exe_bytes):
        path = os.path.join(WORK, "build", "_exekeys_test.exe")
        open(path, "wb").write(exe_bytes)
        mz = MZ(path)
        image = bytearray(mz.image)
        for r in mz.relocs:
            struct.pack_into("<H", image, r, (struct.unpack_from("<H", image, r)[0] + LOAD) & 0xFFFF)
        os.remove(path)
        self.mu = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_16)
        self.mu.mem_map(0, 0x100000)
        self.mu.mem_write(LOAD * 16, bytes(image))
        self.mu.mem_write(SENTINEL_SEG * 16 + SENTINEL_OFF, b"\xcb")      # retf, never run: we stop there
        self.queue, self.log = [], []
        self.mu.hook_add(uc.UC_HOOK_INTR, self._interrupt)
        self.stops = set()
        self.reached = None
        self.mu.hook_add(uc.UC_HOOK_CODE, self._code)

    def _interrupt(self, mu, intno, _data):
        if intno != 0x21:
            raise RuntimeError(f"INT {intno:02X}")
        ah = mu.reg_read(X.UC_X86_REG_AH)
        ax = mu.reg_read(X.UC_X86_REG_AX)
        flags = mu.reg_read(X.UC_X86_REG_FLAGS)
        self.log.append(ah)
        if ah == 0x0B:
            mu.reg_write(X.UC_X86_REG_AL, 0xFF if self.queue else 0)
        elif ah == 0x08:
            mu.reg_write(X.UC_X86_REG_AL, self.queue.pop(0) if self.queue else 0)
        elif ah == 0x06:
            if mu.reg_read(X.UC_X86_REG_DL) != 0xFF:
                raise RuntimeError("AH=06h with DL other than FF")
            if self.queue:
                mu.reg_write(X.UC_X86_REG_AL, self.queue.pop(0))
                flags &= ~0x40
            else:
                mu.reg_write(X.UC_X86_REG_AL, 0)
                flags |= 0x40
            mu.reg_write(X.UC_X86_REG_FLAGS, flags)
        elif ah == 0x0C:
            if ax & 0xFF not in (0, 1, 6, 7, 8, 0xA) or ax & 0xFF:
                raise RuntimeError(f"AH=0Ch with AL={ax & 0xFF:02X}")
            self.queue.clear()
        else:
            raise RuntimeError(f"INT 21h AH={ah:02X}")

    def _code(self, mu, address, _size, _data):
        if address in self.stops:
            self.reached = address
            mu.emu_stop()

    def w16(self, ds_off, value):
        self.mu.mem_write((DGROUP + LOAD) * 16 + ds_off, struct.pack("<H", value))

    def run(self, seg, off, far, stops, limit=100000):
        """Run from seg:off (seg as the image numbers it) until a stop address or the return. A far call
        returns to the sentinel; a near one to offset FFF0 of the same segment, which is never run - the
        code hook stops at it first."""
        mu = self.mu
        cs = seg + LOAD
        sp = STACK_TOP
        ret = [SENTINEL_SEG, SENTINEL_OFF] if far else [0xFFF0]
        for word in ret:
            sp -= 2
            mu.mem_write(STACK_SEG * 16 + sp, struct.pack("<H", word))
        back = SENTINEL_SEG * 16 + SENTINEL_OFF if far else cs * 16 + 0xFFF0
        self.stops = set(stops) | {back}
        for reg, val in ((X.UC_X86_REG_SS, STACK_SEG), (X.UC_X86_REG_SP, sp), (X.UC_X86_REG_DS, DGROUP + LOAD),
                         (X.UC_X86_REG_ES, DGROUP + LOAD), (X.UC_X86_REG_CS, cs), (X.UC_X86_REG_IP, off),
                         (X.UC_X86_REG_AX, 0), (X.UC_X86_REG_SI, 0x1234), (X.UC_X86_REG_BP, 0x5000)):
            mu.reg_write(reg, val)
        self.reached = None
        mu.emu_start(cs * 16 + off, 0, count=limit)
        if self.reached is None:
            raise RuntimeError(f"{seg:04X}:{off:04X} ran {limit} instructions without stopping")
        return self.reached


def key_reader(machine, key):
    """What main 0x2B5F6 returns with `key` waiting (None: no key)."""
    machine.queue = [] if key is None else [key]
    machine.log = []
    seg = 0x25CA
    machine.run(seg, 0x2B5F6 - seg * 16, far=False, stops=())
    return machine.mu.reg_read(X.UC_X86_REG_AX)


def wait_frame(machine, mode, mask, buttons, keys, count=5):
    """Whether one frame of main 0x2E0E4 ends the wait; and the keys left."""
    seg = 0x25CA
    machine.w16(0x78C8, mode)
    machine.w16(0x78CA, mask)
    machine.w16(0x78CC, count)
    machine.w16(0x98F8, buttons)
    machine.w16(0x14D6, 0xFFFF)                  # no prompt blinking
    machine.queue = list(keys)
    machine.log = []
    end = (seg + LOAD) * 16 + (0x2E147 - seg * 16)
    reached = machine.run(seg, 0x2E0E4 - seg * 16, far=True, stops={end})
    return reached == end, list(machine.queue)


def wait_setup(machine, mode):
    """(INT 21h functions called, AX) when main 0x2E150 reaches its call of main 0x2DD40."""
    seg = 0x25CA
    machine.queue = [0x0D, 0x20, ord("w")]
    machine.log = []
    mu = machine.mu
    # 0x2E150(window, count, mask, mode): the caller pushed mode, mask, count, window, then the far return
    frame = [0xFFFF, 0, 0xFFFF, mode]
    sp = STACK_TOP
    for word in reversed(frame):
        sp -= 2
        mu.mem_write(STACK_SEG * 16 + sp, struct.pack("<H", word))
    at = (seg + LOAD) * 16 + (0x2E15A - seg * 16)
    for word in (SENTINEL_SEG, SENTINEL_OFF):
        sp -= 2
        mu.mem_write(STACK_SEG * 16 + sp, struct.pack("<H", word))
    machine.stops = {at}
    for reg, val in ((X.UC_X86_REG_SS, STACK_SEG), (X.UC_X86_REG_SP, sp), (X.UC_X86_REG_DS, DGROUP + LOAD),
                     (X.UC_X86_REG_CS, seg + LOAD), (X.UC_X86_REG_IP, 0x2E150 - seg * 16), (X.UC_X86_REG_AX, 0x5555)):
        mu.reg_write(reg, val)
    machine.reached = None
    mu.emu_start((seg + LOAD) * 16 + (0x2E150 - seg * 16), 0, count=1000)
    return list(machine.log), mu.reg_read(X.UC_X86_REG_AX), list(machine.queue)


original = open(PATH, "rb").read()
patched = exekeys.apply_to(original)
check(exekeys.state(original) == "orig" and exekeys.state(patched) == "patched", "state() does not tell the two apart")
old, new = Machine(original), Machine(patched)

keys = [None] + [ord(c) for c in "123456789"] + [ord(c) for c in "wzadqesWZADQES"] \
    + [ord(c) for c in "0xXjk "] + [0x0D, 0x17, 0x1A, 0x08, 0x0B, 0xB1]
for k in keys:
    got_old, got_new = key_reader(old, k), key_reader(new, k)
    ch = None if k is None else chr(k)
    want = 0xFFFF
    if ch is not None and ch in TABLE:
        want = TABLE[ch]
    if ch is not None and ch.lower() in LETTERS:
        want = TABLE[LETTERS[ch.lower()]]
    want_old = TABLE[ch] if ch is not None and ch in TABLE else 0xFFFF
    name = "无" if k is None else repr(ch)
    check(got_new == want, f"改后读键 {name}：得到 {got_new:04X}，应为 {want:04X}")
    check(got_old == want_old, f"原版读键 {name}：得到 {got_old:04X}，应为 {want_old:04X}")

frames = 0
for mode, mask in ((1, 2), (1, 0xFFFF), (2, 0xFFFF)):
    frames += 10
    for label, buttons, keys_in, want_new, want_old in (
            ("没有输入", 0, [], False, False),
            ("左键按下", 4, [], mask & 2 != 0, mask & 2 != 0),
            ("左键按住", 1, [], mask & 1 != 0, mask & 1 != 0),
            ("右键按住", 0x10, [], True, True),
            ("Enter", 0, [0x0D], True, False),
            ("空格", 0, [0x20], True, False),
            ("其他键", 0, [ord("x")], False, False),
            ("数字键", 0, [ord("8")], False, False)):
        end_new, left_new = wait_frame(new, mode, mask, buttons, keys_in)
        end_old, left_old = wait_frame(old, mode, mask, buttons, keys_in)
        check(end_new == want_new, f"改后 模式{mode} 掩码{mask:04X} {label}：{'结束' if end_new else '不结束'}")
        check(end_old == want_old, f"原版 模式{mode} 掩码{mask:04X} {label}：{'结束' if end_old else '不结束'}")
        if keys_in and not buttons:
            check(left_new == [], f"改后 模式{mode} {label}：按键没有被取走")
    end_new, _ = wait_frame(new, mode, mask, 0, [ord("x"), 0x0D])
    check(not end_new, f"改后 模式{mode}：一帧只取一个键")
    end_new, _ = wait_frame(new, mode, mask, 0, [0x0D])
    check(end_new, f"改后 模式{mode}：前一帧取走其他键后，Enter 仍然结束")

for mode in (0, 1, 2, 3):
    log_new, ax_new, left_new = wait_setup(new, mode)
    log_old, ax_old, left_old = wait_setup(old, mode)
    flush = mode in (1, 2)
    check(ax_new == 1 and ax_old == 1, f"模式{mode}：调用 0x2DD40 时 AX 应为 1（改后 {ax_new:04X}，原版 {ax_old:04X}）")
    check((log_new == [0x0C]) == flush and (left_new == []) == flush,
          f"模式{mode}：改后 INT 21h {[hex(x) for x in log_new]}，剩余按键 {left_new}")
    check(log_old == [] and len(left_old) == 3, f"模式{mode}：原版不应碰键盘")

block, labels = exekeys.routines()
print(f"例程 {len(block.rstrip(b'\x90'))} 字节，入口 " + "，".join(f"{k} 0x{v:05X}" for k, v in labels.items()))
if failures:
    print("\n".join("  " + f for f in failures))
    print(f"未通过：{len(failures)} 项")
    sys.exit(1)
print(f"通过：读键 {len(keys)} 种，等待 {frames} 种，设置 4 种")
