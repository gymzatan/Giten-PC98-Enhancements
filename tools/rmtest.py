#!/usr/bin/env python3
"""Real-mode test bench for the resident programs, on unicorn.

A 1 MB address space with an interrupt vector table. INT 21h is answered by
Python (the services a TSR installer uses plus whatever a test adds to
`dos`), and so is any interrupt a test puts in `hle`; every other software
interrupt goes through the vector table exactly as on the real machine, so a
hooked vector reaches the program under test and its chained "original"
handler can be a stub planted by the test.
"""
import struct

from unicorn import UC_ARCH_X86, UC_HOOK_INTR, UC_MODE_16, Uc
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BP, UC_X86_REG_BX, UC_X86_REG_CS,
                               UC_X86_REG_CX, UC_X86_REG_DI, UC_X86_REG_DS, UC_X86_REG_DX,
                               UC_X86_REG_ES, UC_X86_REG_FLAGS, UC_X86_REG_IP, UC_X86_REG_SI,
                               UC_X86_REG_SP, UC_X86_REG_SS)

REGS = {"ax": UC_X86_REG_AX, "bx": UC_X86_REG_BX, "cx": UC_X86_REG_CX, "dx": UC_X86_REG_DX,
        "si": UC_X86_REG_SI, "di": UC_X86_REG_DI, "bp": UC_X86_REG_BP, "sp": UC_X86_REG_SP,
        "cs": UC_X86_REG_CS, "ds": UC_X86_REG_DS, "es": UC_X86_REG_ES, "ss": UC_X86_REG_SS,
        "ip": UC_X86_REG_IP, "flags": UC_X86_REG_FLAGS}
STOP_SEG, STOP_OFF = 0xF000, 0xFFF0     # the HLT every call returns to
STOP = STOP_SEG * 16 + STOP_OFF


class Machine:
    def __init__(self):
        self.uc = Uc(UC_ARCH_X86, UC_MODE_16)
        self.uc.mem_map(0, 0x100000)
        self.uc.mem_write(STOP, b"\xf4")
        self.uc.hook_add(UC_HOOK_INTR, self._intr)
        self.dos = {0x09: self._dos_print, 0x25: self._dos_setvec, 0x35: self._dos_getvec,
                    0x31: self._dos_tsr, 0x4C: self._dos_exit}
        self.hle = {0x21: self._dos_call}
        self.output = bytearray()
        self.resident = None
        self.exited = None

    # ------------------------------------------------------------- registers
    def __getitem__(self, name):
        return self.uc.reg_read(REGS[name])

    def __setitem__(self, name, value):
        self.uc.reg_write(REGS[name], value & 0xFFFF)

    def read(self, seg, off, n):
        return bytes(self.uc.mem_read(seg * 16 + off, n))

    def write(self, seg, off, data):
        self.uc.mem_write(seg * 16 + off, bytes(data))

    def write_code(self, seg, off, data):
        """Write instructions; unicorn keeps executing stale translations of
        rewritten code unless its block cache is dropped for the range."""
        start = seg * 16 + off
        self.uc.mem_write(start, bytes(data))
        self.uc.ctl_remove_cache(start, start + len(data))

    def word(self, seg, off):
        return struct.unpack("<H", self.read(seg, off, 2))[0]

    def vector(self, n):
        off, seg = struct.unpack("<HH", self.read(0, n * 4, 4))
        return seg, off

    def set_vector(self, n, seg, off):
        self.write(0, n * 4, struct.pack("<HH", off, seg))

    # ------------------------------------------------------------ interrupts
    def _push(self, value):
        sp = (self["sp"] - 2) & 0xFFFF
        self["sp"] = sp
        self.write(self["ss"], sp, struct.pack("<H", value & 0xFFFF))

    def _dos_call(self):
        fn = self.dos.get(self["ax"] >> 8)
        if fn is None:
            raise RuntimeError(f"INT 21h AH={self['ax'] >> 8:02X}h not provided by the bench")
        fn()

    def _intr(self, uc, intno, _data):
        if intno in self.hle:
            self.hle[intno]()
            return
        seg, off = self.vector(intno)
        if seg == 0 and off == 0:
            raise RuntimeError(f"INT {intno:02X}h has no handler")
        self._push(self["flags"])
        self._push(self["cs"])
        self._push(self["ip"])
        self["flags"] = self["flags"] & ~0x0300
        self["cs"] = seg
        self["ip"] = off

    def _dos_print(self):
        seg, off = self["ds"], self["dx"]
        while True:
            ch = self.read(seg, off, 1)[0]
            if ch == 0x24:
                break
            self.output.append(ch)
            off += 1

    def _dos_setvec(self):
        self.set_vector(self["ax"] & 0xFF, self["ds"], self["dx"])

    def _dos_getvec(self):
        seg, off = self.vector(self["ax"] & 0xFF)
        self["es"], self["bx"] = seg, off

    def _dos_tsr(self):
        self.resident = self["dx"]
        self.uc.emu_stop()

    def _dos_exit(self):
        self.exited = self["ax"] & 0xFF
        self.uc.emu_stop()

    # ----------------------------------------------------------------- running
    def load_com(self, seg, code):
        self.write_code(seg, 0, b"\xcd\x20" + bytes(0xFE))
        self.write_code(seg, 0x100, code)
        for r in ("cs", "ds", "es", "ss"):
            self[r] = seg
        self["sp"] = 0xFFFE
        self.write(seg, 0xFFFE, b"\0\0")
        self.com_seg = seg

    def run_com(self, max_steps=100000):
        """Run the loaded program until it exits or goes resident."""
        seg = self.com_seg
        self.uc.emu_start(seg * 16 + 0x100, STOP, count=max_steps)

    def call_int(self, n, stack_seg=0x9000, max_steps=100000, **regs):
        """Raise INT n with the given registers from a scratch caller; returns registers."""
        caller = 0x8F00
        self.write_code(caller, 0, bytes([0xCD, n, 0xEA]) + struct.pack("<HH", STOP_OFF, STOP_SEG))
        self["ss"], self["sp"] = stack_seg, 0xFFF0
        for k, v in regs.items():
            self[k] = v
        self["cs"] = caller
        self.uc.emu_start(caller * 16, STOP, count=max_steps)
        if self["cs"] * 16 + self["ip"] != STOP:
            raise RuntimeError("interrupt handler did not return")
        if self["sp"] != 0xFFF0:
            raise RuntimeError(f"stack not balanced: sp={self['sp']:04X}")
        return {k: self[k] for k in ("ax", "bx", "cx", "dx", "si", "di", "bp", "ds", "es", "flags")}

    def plant_iret_stub(self, seg, off, **sets):
        """An interrupt handler that loads fixed register values and IRETs."""
        code = bytearray()
        for reg, val in sets.items():
            code += bytes([0xB8 + ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di").index(reg)])
            code += struct.pack("<H", val)
        code += b"\xcf"
        self.write_code(seg, off, code)
        return seg, off
