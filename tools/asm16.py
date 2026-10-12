#!/usr/bin/env python3
"""Minimal label-aware 16-bit byte emitter for building small .COM probes."""
import struct


class Asm:
    def __init__(self, org=0x100):
        self.code = bytearray()
        self.labels = {}
        self.fixups = []
        self.org = org

    def db(self, *bs):
        for b in bs:
            if isinstance(b, (bytes, bytearray)):
                self.code.extend(b)
            else:
                self.code.append(b & 0xFF)
        return self

    def label(self, n):
        self.labels[n] = len(self.code)
        return self

    def call(self, n):
        self.db(0xE8)
        self.fixups.append((len(self.code), n, 2))
        self.db(0, 0)
        return self

    def jmp(self, n):
        self.db(0xE9)
        self.fixups.append((len(self.code), n, 2))
        self.db(0, 0)
        return self

    def jcc_short(self, opcode, n):
        self.db(opcode)
        self.fixups.append((len(self.code), n, 1))
        self.db(0)
        return self

    def lea_si(self, n):
        """mov si, imm16 -> label address (org-relative)."""
        self.db(0xBE)
        self.fixups.append((len(self.code), n, "abs"))
        self.db(0, 0)
        return self

    def build(self):
        for pos, name, size in self.fixups:
            t = self.labels[name]
            if size == "abs":
                struct.pack_into("<H", self.code, pos, self.org + t)
            elif size == 1:
                rel = t - (pos + 1)
                assert -128 <= rel <= 127, f"{name}: {rel}"
                self.code[pos] = rel & 0xFF
            else:
                struct.pack_into("<h", self.code, pos, t - (pos + 2))
        return bytes(self.code)


# Shared subroutines --------------------------------------------------------
def add_print_helpers(a: Asm):
    """print_hex: AL as 2 hex digits (needs CL=4). putc: DL. newline."""
    a.label("print_hex")
    a.db(0x8A, 0xE0)            # mov ah,al
    a.db(0xD2, 0xE8)            # shr al,cl
    a.call("nib")
    a.db(0x8A, 0xC4)            # mov al,ah
    a.call("nib")
    a.db(0xC3)

    a.label("nib")
    a.db(0x24, 0x0F)            # and al,0x0F
    a.db(0x04, 0x30)            # add al,'0'
    a.db(0x3C, 0x39)            # cmp al,'9'
    a.db(0x76, 0x02)            # jbe +2
    a.db(0x04, 0x07)            # add al,7
    a.db(0x8A, 0xD0)            # mov dl,al
    a.db(0x50)                  # push ax
    a.db(0xB4, 0x02)            # mov ah,2
    a.db(0xCD, 0x21)
    a.db(0x58)                  # pop ax
    a.db(0xC3)

    a.label("crlf")
    a.db(0x50)
    a.db(0xB2, 0x0D, 0xB4, 0x02, 0xCD, 0x21)
    a.db(0xB2, 0x0A, 0xB4, 0x02, 0xCD, 0x21)
    a.db(0x58)
    a.db(0xC3)
