#!/usr/bin/env python3
"""Load a DOS MZ executable image with relocations applied, and disassemble it.

Addresses are image-relative: segment S, offset O lives at linear S*16+O, and
relocated segment words get `base` added, so with base=0 every segment value in
the code is directly the image segment.
"""
import struct

import capstone


class MZ:
    def __init__(self, path, base=0):
        d = open(path, "rb").read()
        (cblp, cp, crlc, cparhdr, self.minalloc, self.maxalloc, self.ss, self.sp,
         _csum, self.ip, self.cs, lfarlc) = struct.unpack_from("<12H", d, 2)
        self.hdr = cparhdr * 16
        end = (cp - 1) * 512 + (cblp or 512)
        self.image = bytearray(d[self.hdr:end])
        self.overlay = d[end:]
        self.base = base
        self.relocs = []
        for i in range(crlc):
            off, seg = struct.unpack_from("<HH", d, lfarlc + i * 4)
            p = seg * 16 + off
            self.relocs.append(p)
            v = struct.unpack_from("<H", self.image, p)[0]
            struct.pack_into("<H", self.image, p, (v + base) & 0xFFFF)
        self.reloc_set = set(self.relocs)
        self.cap = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
        self.cap.detail = False

    def lin(self, seg, off):
        return seg * 16 + off

    def file_off(self, lin):
        return self.hdr + lin

    def disasm(self, seg, off, count=40, stop_at_ret=False):
        """Disassemble starting at seg:off. Capstone is given the *offset* as the
        address so that near branch targets print as offsets within `seg`."""
        start = self.lin(seg, off)
        code = bytes(self.image[start:start + count * 8])
        out = []
        for ins in self.cap.disasm(code, off):
            lin = self.lin(seg, ins.address)
            reloc = any(p in self.reloc_set for p in range(lin, lin + ins.size))
            out.append((ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, reloc))
            if len(out) >= count or (stop_at_ret and ins.mnemonic in ("ret", "retf", "iret")):
                break
        return out

    def show(self, seg, off, count=40, stop_at_ret=False):
        for a, hx, mn, op, reloc in self.disasm(seg, off, count, stop_at_ret):
            print(f"{seg:04X}:{a:04X}  {hx:<16} {mn:<7} {op}{'   ; <reloc>' if reloc else ''}")


class Overlay:
    """One MS LINK overlay module: an MZ chunk appended after the main image.

    Its code is disassembled with offsets starting at 0 (the module's own
    segment); relocated words hold segment values in the main image's space.
    """

    def __init__(self, data, file_off):
        (cblp, cp, crlc, cparhdr, _mina, _maxa, _ss, _sp, _cs, _ip, _cs2, lfarlc,
         self.number) = struct.unpack_from("<13H", data, file_off + 2)
        self.file_off = file_off
        self.hdr = cparhdr * 16
        end = (cp - 1) * 512 + (cblp or 512)
        self.image = bytearray(data[file_off + self.hdr:file_off + end])
        self.relocs = set()
        for i in range(crlc):
            off, seg = struct.unpack_from("<HH", data, file_off + lfarlc + i * 4)
            self.relocs.add(seg * 16 + off)
        self.cap = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)

    def image_off(self, file_pos):
        return file_pos - self.file_off - self.hdr

    def show(self, off, count=40, stop_at_ret=False):
        code = bytes(self.image[off:off + count * 8])
        n = 0
        for ins in self.cap.disasm(code, off):
            reloc = any(p in self.relocs for p in range(ins.address, ins.address + ins.size))
            print(f"ov{self.number:02d}:{ins.address:04X}  {ins.bytes.hex():<16} "
                  f"{ins.mnemonic:<7} {ins.op_str}{'   ; <reloc>' if reloc else ''}")
            n += 1
            if n >= count or (stop_at_ret and ins.mnemonic in ("ret", "retf")):
                break


def overlays(path):
    """All overlay modules of an MS LINK overlaid executable, by number."""
    data = open(path, "rb").read()
    main = MZ(path)
    pos = (main.hdr + len(main.image) + 511) & ~511
    found = {}
    while pos + 0x20 < len(data):
        if data[pos:pos + 2] == b"MZ":
            ov = Overlay(data, pos)
            found[ov.number] = ov
            pos = (pos + ov.hdr + len(ov.image) + 511) & ~511
        else:
            pos += 512
    return found
