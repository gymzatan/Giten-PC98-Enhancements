#!/usr/bin/env python3
"""Which commands name another script record, and which files get named.

1603:836A reads a record reference as two bytes [file][rec]; 857E resolves it,
treating file E0..FF as relative to the running frame and anything lower as
global MS00xx. A command whose handler can reach 836A carries such a reference;
jump lists (L) carry one in every entry whose second byte is 0.

    fileref.py              table of referencing commands, and every global
                            file named anywhere in the shipped corpus
    fileref.py 31           also list the records that name MS0031
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkvm  # noqa: E402
import ddsvm  # noqa: E402
import vmscan  # noqa: E402
from ddscrypt import decrypt  # noqa: E402
from ddsgrammar import COMMANDS  # noqa: E402
from msdump import chunks, records, script_files  # noqa: E402

REF_READER = (vmscan.VM_SEG, 0x836A)


def referencing_commands(prog):
    """{code: signature} for every command whose handler can reach 836A."""
    table = [prog.word(vmscan.VM_SEG, vmscan.CMD_TABLE + 2 * i) for i in range(vmscan.CMD_COUNT)]
    reach = {}

    def reaches(addr):
        seen, todo = set(), [addr]
        while todo:
            a = todo.pop()
            if a in seen:
                continue
            seen.add(a)
            for t in prog.body_calls(*a):
                if t == REF_READER:
                    return True
                if t[0] != vmscan.THUNK_SEG and t not in vmscan.PRIM:
                    todo.append(t)
        return False

    found = {}
    for code, h in enumerate(table):
        if code not in COMMANDS:
            continue
        if h not in reach:
            reach[h] = reaches((vmscan.VM_SEG, h))
        if reach[h]:
            found[code] = COMMANDS[code]
    return found


class _RefReader(ddsvm._Reader):
    """ddsvm's operand reader, additionally remembering jump-list [file][rec]."""
    refs = []

    def op_L(self):
        while True:
            if self.byte() == 0xFF:
                return
            if self.byte():
                self.op_r()
            else:
                _RefReader.refs.append((self.byte(), self.byte()))


def main(want=None):
    prog = vmscan.Prog("files/DDS98/DDS98.EXE")
    refcmds = referencing_commands(prog)
    print("commands whose handler reads a [file][rec] reference:")
    for c, sig in sorted(refcmds.items()):
        print(f"   {c:#05x} {sig!r}")
    undecoded = {c: s for c, s in refcmds.items() if s != "bb" and "L" not in s}
    if undecoded:
        print("   not decoded below (reference position inside the signature unknown): "
              + ", ".join(f"{c:#05x} {s!r}" for c, s in sorted(undecoded.items())))

    ddsvm._Reader = _RefReader
    sizes = checkvm.dictionary_sizes("files/DDS98")
    named = collections.Counter()
    hits = []
    for stem, path in script_files("files/DDS98"):
        name = stem + ".BIN"
        for ci, ch in enumerate(chunks(open(path, "rb").read())):
            for rid, _c, p in records(decrypt(ch)[1]):
                if checkvm.verify(p, sizes, False)[0]:
                    continue
                _RefReader.refs = []
                refs = []
                for t in ddsvm.tokenize(p):
                    if t.kind == "cmd" and refcmds.get(t.code) == "bb":
                        refs.append((t.start, t.code, p[t.end - 2], p[t.end - 1]))
                refs += [(None, "L", f, r) for f, r in _RefReader.refs]
                for at, code, f, r in refs:
                    if f >= 0xE0:
                        continue
                    named[f] += 1
                    if want is not None and f == want:
                        where = f"@{at:#x} {code:#05x}" if at is not None else "jump list"
                        hits.append(f"{name} c{ci} r{rid:02X} {where} -> MS{f:04X} record {r:02X}")
    print(f"\nglobal files named by those commands and by jump lists: {len(named)}")
    print("   " + " ".join(f"{f:02X}x{n}" for f, n in sorted(named.items())))
    if want is not None:
        print(f"\nreferences to MS{want:04X}: {len(hits)}")
        for h in hits[:40]:
            print("   " + h)


if __name__ == "__main__":
    main(int(sys.argv[1], 16) if len(sys.argv) > 1 else None)
