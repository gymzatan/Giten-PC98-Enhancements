#!/usr/bin/env python3
"""Static operand analysis of the DDS98 script VM.

Dispatcher 1603:5A74 jumps through a 767-entry table at 1603:5AA6 indexed by
command code (page*0x100 + byte; prefixes 1E/1F re-dispatch as 0x2xx/0x1xx).
Handlers read operands only through these primitives on the current frame:

    b  1603:55A0  one byte          w  1603:55B8  word
    d  1603:55D0  dword             T  1603:5534  nested statement (token)
    V  1603:9B28  typed value: a type byte (0..5D) dispatched by the switch in
                  1603:9C94, followed by that type's own operands
    r  1603:848E  word that is added to the frame's read position: a branch
                  target *inside the current record*, relative to the byte
                  after the word. These have to be relocated when text changes
                  length.

Paths are followed through near calls, far calls into main-image segments, and
conditional branches. A function whose paths read different sequences, or that
reads inside a loop, is reported instead of being guessed; those few are
resolved by hand in `ddsvm.py` and the whole corpus parse checks the result.
"""
import collections
import struct
import sys

import capstone

from mz import MZ

VM_SEG = 0x1603
PRIM = {(VM_SEG, 0x55A0): "b", (VM_SEG, 0x55B8): "w", (VM_SEG, 0x55D0): "d",
        (VM_SEG, 0x5534): "T", (VM_SEG, 0x9B28): "V", (VM_SEG, 0x848E): "r"}
# Helpers whose reads depend on the bytes they read, resolved by hand
# (see ddsvm.py for the exact list grammars):
#   L  1603:756E -> EEDC  jump list: entries [c][s] + (s? r : [file][rec]), until c == FF
#   C  1603:72FA          after its r: pairs [b1][b2] until b1 == FF
#   D  1603:D692          after its r: values V until a constant -1
#   S  1603:97E6          selector byte, then V or bV depending on the selector
#   M  1603:C1EA          [b1][b2], then [b3] when b2 is 0 or 2
#   B  1603:C4F2          bytes up to and including FF (read twice, position rewound)
#   X  25CA:0956          [b], then [b][b] when b != 0, else six V
SPECIAL = {(VM_SEG, 0x756E): "L", (VM_SEG, 0x72FA): "rC", (VM_SEG, 0xD692): "rD",
           (VM_SEG, 0x97E6): "S", (VM_SEG, 0xC1EA): "M", (VM_SEG, 0xC4F2): "B",
           (VM_SEG, 0x8844): "rV",          # 8656 -> 848E; the other path is a no-return error call
           (0x25CA, 0x0956): "X"}
# Helpers steered by the constant the command handler pushed last (tracked as
# `lp` by the walker):
#   791C wrappers: [b][b], V only when the argument is 0, then V
#   8770:          r, V, and a second V when the argument is 1        (via 8730)
#   7B2E:          [b][b], then V only when the argument is 0          (via 78FE)
CALC = {0x795E, 0x7982, 0x79D8, 0x79FC, 0x7A20, 0x7A44, 0x7A68, 0x7A8C, 0x7AAC, 0x7ACC, 0x7B80}
PARAM = {(VM_SEG, f): (lambda lp: {0: "bbVV", 1: "bbV"}.get(lp)) for f in CALC}
PARAM[(VM_SEG, 0x8770)] = lambda lp: None if lp is None else ("rVV" if lp == 1 else "rV")
PARAM[(VM_SEG, 0x7B2E)] = lambda lp: {0: "bbV", 1: "bb"}.get(lp)
THUNK_SEG = 0x07B1
CMD_TABLE, CMD_COUNT, CMD_EXIT, REDISPATCH = 0x5AA6, 0x2FF, (VM_SEG, 0x6F1C), (VM_SEG, 0x5A7B)
VAL_FUNC, VAL_TABLE, VAL_COUNT = 0x9C94, 0x9CBC, 0x5E


class Prog:
    def __init__(self, exe):
        self.m = MZ(exe)
        self.img = bytes(self.m.image)
        self.cap = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
        self.memo = {}

    def insn(self, seg, off):
        lin = seg * 16 + off
        for ins in self.cap.disasm(self.img[lin:lin + 16], off):
            return ins
        return None

    def word(self, seg, off):
        return struct.unpack_from("<H", self.img, seg * 16 + off)[0]

    def switch_targets(self, seg, off, ins):
        """Case labels of an MS C switch: `cmp ax, N` ... `jmp cs:[bx + table]`.

        The bound is the nearest compare against ax within the preceding 24
        bytes; the table holds N+1 near offsets in the same segment.
        """
        b = bytes(ins.bytes)
        if not (b[:3] == b"\x2e\xff\xa7" and len(b) == 5):
            return None
        table = struct.unpack_from("<H", b, 3)[0]
        lin = seg * 16 + off
        back = self.img[lin - 24:lin]
        bound = None
        for k in range(len(back) - 3, -1, -1):
            if back[k] == 0x3D:
                bound = struct.unpack_from("<H", back, k + 1)[0]
                break
            if back[k] == 0x83 and back[k + 1] == 0xF8:
                bound = back[k + 2]
                break
        if bound is None or bound > 0x400:
            return None
        return [self.word(seg, table + 2 * i) for i in range(bound + 1)]

    def walk(self, seg, entry, stops, depth=0, cap=48):
        """Set of (sequence, exit). exit: 'ret' | 'stop@SSSS:OOOO' | problem tag.

        `lp` carries the last immediate pushed on the path (push cs / nop keep
        it), which is how the calculation wrappers in CALC learn their mode.
        """
        out = set()
        todo = [(entry, "", None)]
        seen = set()
        steps = 0
        while todo:
            off, seq, lp = todo.pop()
            steps += 1
            if steps > 20000 or len(out) > cap:
                out.add((seq, "explode"))
                break
            key = (off, seq, lp)
            if key in seen:
                continue
            if len({o for o, _, _ in seen if o == off}) > 6:
                out.add((seq, f"loop@{seg:04X}:{off:04X}"))
                continue
            seen.add(key)
            if (seg, off) in stops:
                out.add((seq, f"stop@{seg:04X}:{off:04X}"))
                continue
            ins = self.insn(seg, off)
            if ins is None:
                out.add((seq, "lost"))
                continue
            nxt, mn, op = off + ins.size, ins.mnemonic, ins.op_str
            if mn in ("ret", "retf", "iret"):
                out.add((seq, "ret"))
                continue
            if mn == "push":
                try:
                    todo.append((nxt, seq, int(op, 0)))
                except ValueError:
                    todo.append((nxt, seq, lp if op == "cs" else None))
                continue
            if mn == "nop":
                todo.append((nxt, seq, lp))
                continue
            if mn in ("call", "lcall"):                      # capstone spells far calls lcall
                tgt = None
                if ins.bytes[0] == 0x9A:                      # far: op_str is "0xSEG, 0xOFF"
                    o, s = struct.unpack_from("<HH", ins.bytes, 1)
                    tgt = (s, o)
                elif ins.bytes[0] == 0xE8:
                    tgt = (seg, int(op, 16) & 0xFFFF)
                if tgt is None:                               # call through a pointer
                    todo.append((nxt, seq, None))
                    continue
                if tgt in PRIM:
                    todo.append((nxt, seq + PRIM[tgt], None))
                    continue
                if tgt in SPECIAL:
                    todo.append((nxt, seq + SPECIAL[tgt], None))
                    continue
                if tgt in PARAM:
                    sig = PARAM[tgt](lp)
                    if sig is None:
                        out.add((seq, f"param?@{tgt[1]:04X}"))
                    else:
                        todo.append((nxt, seq + sig, None))
                    continue
                if tgt[0] == THUNK_SEG or not self.reaches_fetch(tgt):
                    todo.append((nxt, seq, None))              # overlays never fetch (checked below)
                    continue
                if depth >= 8:
                    out.add((seq, f"deep@{tgt[0]:04X}:{tgt[1]:04X}"))
                    continue
                sub = self.function(tgt, depth + 1)
                if isinstance(sub, str):
                    todo.append((nxt, seq + sub, None))
                else:
                    out.add((seq, f"call@{tgt[0]:04X}:{tgt[1]:04X}"))
                continue
            if mn in ("jmp", "ljmp"):
                if ins.bytes[0] == 0xEA:                      # far: op_str is "0xSEG, 0xOFF"
                    o, s = struct.unpack_from("<HH", ins.bytes, 1)
                    if s != seg:
                        out.add((seq, "farjmp"))
                    else:
                        todo.append((o, seq, lp))
                elif ins.bytes[0] in (0xE9, 0xEB):
                    todo.append((int(op, 16) & 0xFFFF, seq, lp))
                else:
                    targets = self.switch_targets(seg, off, ins)
                    if targets is None:
                        out.add((seq, f"indirect@{seg:04X}:{off:04X}"))
                    else:
                        todo.extend((t, seq, None) for t in targets)
                continue
            if mn.startswith("j") or mn.startswith("loop"):
                if op.startswith("0x"):
                    todo.append((int(op, 16) & 0xFFFF, seq, None))
                todo.append((nxt, seq, None))
                continue
            todo.append((nxt, seq, None))
        return out

    def body_calls(self, seg, entry):
        """Direct call targets reachable inside one function (jumps, branches and
        switch tables followed; returns and far jumps end a path)."""
        calls, todo, seen = set(), [entry], set()
        while todo:
            off = todo.pop()
            if off in seen or len(seen) > 6000:
                continue
            seen.add(off)
            ins = self.insn(seg, off)
            if ins is None:
                continue
            nxt, mn, b0 = off + ins.size, ins.mnemonic, ins.bytes[0]
            if mn in ("ret", "retf", "iret"):
                continue
            if b0 == 0x9A:
                o, s = struct.unpack_from("<HH", ins.bytes, 1)
                calls.add((s, o))
            elif b0 == 0xE8:
                calls.add((seg, int(ins.op_str, 16) & 0xFFFF))
            if mn in ("jmp", "ljmp"):
                if b0 in (0xE9, 0xEB):
                    todo.append(int(ins.op_str, 16) & 0xFFFF)
                elif b0 != 0xEA:
                    todo.extend(self.switch_targets(seg, off, ins) or [])
                continue
            if (mn.startswith("j") or mn.startswith("loop")) and ins.op_str.startswith("0x"):
                todo.append(int(ins.op_str, 16) & 0xFFFF)
            todo.append(nxt)
        return calls

    def reaches_fetch(self, addr):
        """True when the static call graph below `addr` contains a fetch primitive.

        Iterative closure over body_calls: a function reaches a fetch exactly
        when some function in its call graph calls a primitive directly.
        """
        memo = self.__dict__.setdefault("_reach", {})
        if addr in memo:
            return memo[addr]
        graph, todo = {}, [addr]
        while todo:
            a = todo.pop()
            if a in graph or a in memo:
                continue
            graph[a] = self.body_calls(*a)
            for t in graph[a]:
                if t not in PRIM and t not in SPECIAL and t not in PARAM and t[0] != THUNK_SEG:
                    todo.append(t)
        direct = {a for a, cs in graph.items()
                  if any(t in PRIM or t in SPECIAL or t in PARAM or memo.get(t) for t in cs)}
        changed = True
        while changed:
            changed = False
            for a, cs in graph.items():
                if a not in direct and any(t in direct for t in cs):
                    direct.add(a)
                    changed = True
        for a in graph:
            memo[a] = a in direct
        return memo[addr]

    def function(self, addr, depth):
        """Single fetch sequence of a function, or a set of problems."""
        if addr in self.memo:
            return self.memo[addr]
        self.memo[addr] = ""                                  # recursion guard
        res = self.walk(addr[0], addr[1], set(), depth)
        seqs = {s for s, e in res if e == "ret"}
        bad = {(s, e) for s, e in res if e != "ret"}
        if not bad and len(seqs) == 1:
            val = seqs.pop()
        elif not bad and not seqs:
            val = ""
        else:
            val = frozenset(res)
        self.memo[addr] = val
        return val


def main():
    p = Prog(sys.argv[1] if len(sys.argv) > 1 else "files/DDS98/DDS98.EXE")
    mode = sys.argv[2] if len(sys.argv) > 2 else "commands"
    if mode == "values":
        # Inside 9C94 the case bodies read with 55A0 etc; 9B28 recursion shows as V.
        PRIM[(VM_SEG, 0x9B28)] = "V"
        for t in range(VAL_COUNT):
            case = p.word(VM_SEG, VAL_TABLE + 2 * t)
            res = p.walk(VM_SEG, case, set())
            print(f"type {t:02X} @1603:{case:04X}  " +
                  " | ".join(f"{s or '-'}→{e}" for s, e in sorted(res)[:6]))
        return
    table = [p.word(VM_SEG, CMD_TABLE + 2 * i) for i in range(CMD_COUNT)]
    by = collections.defaultdict(list)
    for code, h in enumerate(table):
        by[h].append(code)
    # Only the switch exit ends a case: cases may jump into or fall through to
    # code shared with other cases, and those reads belong to this command.
    starts = {CMD_EXIT, (VM_SEG, 0x6F1E)}
    for h, codes in sorted(by.items()):
        if (VM_SEG, h) == CMD_EXIT:
            continue
        res = p.walk(VM_SEG, h, starts | {REDISPATCH})
        cs = ",".join(f"{c:03X}" for c in codes[:6]) + ("…" if len(codes) > 6 else "")
        desc = " | ".join(f"{s or '-'}→{e}" for s, e in sorted(res)[:6])
        print(f"{cs:<30} 1603:{h:04X}  {desc}")


if __name__ == "__main__":
    main()
