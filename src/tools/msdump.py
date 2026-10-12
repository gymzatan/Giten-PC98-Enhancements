#!/usr/bin/env python3
"""Decrypt every script file (MS*.BIN, ID*.BIN) and write a readable dump per file.

Container (verified on all 162 single-chunk files and 640 chunks of the 38
multi-chunk MS6xxx files):

    file   = chunk+                      chunk = [len:u16][len bytes, ddscrypt]
    chunk  = [count:u16] record*count    (after decryption)
    record = [id:u8][len:u16][payload]
           | [id:u8][FFFF][a:u8][b:u8][len:u16][payload]   (1603:94DA: kept only
                                                            when 806E(b, a) is true)

The payload is script bytecode. In the dump, valid Shift-JIS double-byte
characters print as text and every other byte prints as {XX}.
"""
import glob
import os
import struct
import sys

from ddscrypt import decrypt

# Resource types holding script records in this container: MS (dialogue,
# events, dictionaries) and ID (per-demon negotiation scripts).
SCRIPT_TYPES = ("MS", "ID")


def script_files(src):
    """(stem, path) of every script file, e.g. ("ID00C1", ".../ID00C1.BIN")."""
    out = []
    for t in SCRIPT_TYPES:
        for path in glob.glob(os.path.join(src, f"{t}*.BIN")):
            out.append((os.path.splitext(os.path.basename(path))[0].upper(), path))
    return sorted(out)


def chunks(data):
    pos = 0
    while pos + 2 <= len(data):
        n = struct.unpack_from("<H", data, pos)[0]
        yield data[pos:pos + 2 + n]
        pos += 2 + n


def records(plain):
    count = struct.unpack_from("<H", plain, 0)[0]
    pos = 2
    for _ in range(count):
        rid = plain[pos]
        n = struct.unpack_from("<H", plain, pos + 1)[0]
        cond = None
        if n == 0xFFFF:
            cond = (plain[pos + 3], plain[pos + 4])
            n = struct.unpack_from("<H", plain, pos + 5)[0]
            pos += 7
        else:
            pos += 3
        yield rid, cond, plain[pos:pos + n]
        pos += n
    if pos != len(plain):
        raise ValueError(f"record table ends at {pos}, chunk is {len(plain)}")


def render(b):
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF) and i + 1 < len(b) \
                and (0x40 <= b[i + 1] <= 0x7E or 0x80 <= b[i + 1] <= 0xFC):
            try:
                out.append(b[i:i + 2].decode("cp932"))
                i += 2
                continue
            except UnicodeDecodeError:
                pass
        out.append("{%02X}" % c)
        i += 1
    return "".join(out)


def main(src="files/DDS98", dst="dec/ms"):
    os.makedirs(dst, exist_ok=True)
    nrec = 0
    for name, path in script_files(src):
        lines = []
        for ci, ch in enumerate(chunks(open(path, "rb").read())):
            _, plain = decrypt(ch)
            for rid, cond, payload in records(plain):
                tag = f"chunk {ci} " if ci or len(lines) and lines[0].startswith("chunk") else ""
                c = f" if {cond[1]:02X},{cond[0]:02X}" if cond else ""
                lines.append(f"=== {tag}record {rid:02X} ({len(payload)} B){c}")
                lines.append(render(payload))
                nrec += 1
        with open(os.path.join(dst, name + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    print(f"{nrec} records dumped to {dst}")


if __name__ == "__main__":
    main(*sys.argv[1:])
