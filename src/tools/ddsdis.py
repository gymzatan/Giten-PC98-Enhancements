#!/usr/bin/env python3
"""Disassemble DDS98 script records.

    ddsdis.py MS0031.BIN [chunk] [record]

Text runs are shown as strings, commands as `@offset code(signature) bytes`,
branch operands with their absolute target. Parsing stops at the first error
and prints what was read up to there.
"""
import os
import sys

from ddscrypt import decrypt
from ddsgrammar import COMMANDS
from ddsvm import ParseError, iter_tokens
from msdump import chunks, records


def show(payload, out=sys.stdout):
    text = bytearray()
    text_at = 0

    def flush():
        if text:
            out.write(f"  {text_at:04X}  \"{text.decode('cp932', 'replace')}\"\n")
            text.clear()

    try:
        for t in iter_tokens(payload):
            if t.kind == "text":
                if not text:
                    text_at = t.start
                text += payload[t.start:t.end]
                continue
            flush()
            raw = payload[t.start:t.end].hex(" ").upper()
            sig = COMMANDS.get(t.code)
            name = f"{t.code:03X}" + ("(?)" if sig is None else f"({sig})")
            extra = "".join(f" ->{target:04X}" for _, target in t.rel)
            if t.dict_ref:
                extra += f" dict{t.dict_ref[0]}[{t.dict_ref[1]}]"
            out.write(f"  {t.start:04X}  {name:<14} {raw}{extra}\n")
        flush()
    except ParseError as e:
        flush()
        out.write(f"  !! {e}\n")


def main(path, chunk=None, record=None):
    data = open(path, "rb").read()
    for ci, ch in enumerate(chunks(data)):
        if chunk is not None and ci != int(chunk):
            continue
        for rid, cond, payload in records(decrypt(ch)[1]):
            if record is not None and rid != int(record, 16):
                continue
            print(f"=== {os.path.basename(path)} chunk {ci} record {rid:02X} ({len(payload)} B)"
                  + (f" cond={cond}" if cond else ""))
            show(payload)


if __name__ == "__main__":
    main(*sys.argv[1:])
