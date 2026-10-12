#!/usr/bin/env python3
"""Two-pass 80286 real-mode assembler for the small resident programs of this project.

Source is Intel syntax spelled the way capstone prints it, one statement per line:

    label:                          name equ expr
    mov ax, word ptr [bp - 0xe]     mov byte ptr es:[di], 2
    les bx, ptr [bp + 6]            lcall [old18]
    jmp done                        rep movsw
    db 2, 2, "text", 0              dw label, 0
    resb 32

Numbers: 123, 0x7b, 7bh, 'A'. Expressions may use labels, equ names and
+ - * / % << >> & | ^ ~ ( ). `;` starts a comment. Labels are addresses
(org + offset).

After assembly every instruction is decoded again with capstone and compared
operand by operand; any mismatch aborts the build. An unconditional jmp gets its
short or near form by relaxation; a conditional jump, loop or jcxz whose target
is out of short range is an error, since the 286 has no near conditional jump.

x87 instructions, spelled as capstone prints them (fld qword ptr [bp - 8],
fild word ptr es:[bx + 0x12c], fmul st(1), fdivp st(1), fadd st(1), st(0),
fld1, fsqrt, fnstsw ax, fwait; xword ptr for 80-bit operands), need Asm(...,
fpu=...): "real" emits fwait + the instruction, "emu" the form the MS C 8087
emulator patches at run time - CD 34+i for fwait + escape D8+i, CD 3C xx for one
with a segment override (xx: segment in bits 7-6 - DS 0, SS 1, CS 2, ES 3 -,
18h, the escape's low three bits), CD 3D for a lone fwait (fwait; nop).
"""
import re
import struct

import capstone

R8 = ("al", "cl", "dl", "bl", "ah", "ch", "dh", "bh")
R16 = ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di")
SREG = ("es", "cs", "ss", "ds")
SEG_PREFIX = {"es": 0x26, "cs": 0x2E, "ss": 0x36, "ds": 0x3E}
BASE_ORDER = ("bx", "bp", "si", "di")
RM_CODE = {("bx", "si"): 0, ("bx", "di"): 1, ("bp", "si"): 2, ("bp", "di"): 3,
           ("si",): 4, ("di",): 5, ("bp",): 6, ("bx",): 7}
ALU = ("add", "or", "adc", "sbb", "and", "sub", "xor", "cmp")
SHIFT = {"rol": 0, "ror": 1, "rcl": 2, "rcr": 3, "shl": 4, "shr": 5, "sar": 7}
UNARY = {"not": 2, "neg": 3, "mul": 4, "imul": 5, "div": 6, "idiv": 7}
JCC = {"jo": 0, "jno": 1, "jb": 2, "jae": 3, "je": 4, "jne": 5, "jbe": 6, "ja": 7,
       "js": 8, "jns": 9, "jp": 10, "jnp": 11, "jl": 12, "jge": 13, "jle": 14, "jg": 15}
SHORT_ONLY = {"loop": 0xE2, "loope": 0xE1, "loopne": 0xE0, "jcxz": 0xE3}
IMPLIED = {"nop": 0x90, "ret": 0xC3, "retf": 0xCB, "iret": 0xCF, "pushf": 0x9C, "popf": 0x9D,
           "pusha": 0x60, "popa": 0x61, "cbw": 0x98, "cwd": 0x99, "lahf": 0x9F, "sahf": 0x9E,
           "clc": 0xF8, "stc": 0xF9, "cmc": 0xF5, "cld": 0xFC, "std": 0xFD, "cli": 0xFA,
           "sti": 0xFB, "hlt": 0xF4, "leave": 0xC9, "int3": 0xCC, "xlatb": 0xD7}
STRING_OPS = {"movsb": 0xA4, "movsw": 0xA5, "cmpsb": 0xA6, "cmpsw": 0xA7, "stosb": 0xAA,
              "stosw": 0xAB, "lodsb": 0xAC, "lodsw": 0xAD, "scasb": 0xAE, "scasw": 0xAF}
REP = {"rep": 0xF3, "repne": 0xF2}
# Alternative spellings, including capstone's 32-bit names for 16-bit opcodes.
ALIAS = {"cwde": "cbw", "cdq": "cwd", "pushaw": "pusha", "popaw": "popa", "sal": "shl",
         "xlat": "xlatb", "repe": "rep", "repz": "rep", "repnz": "repne", "loopz": "loope",
         "loopnz": "loopne", "jc": "jb", "jnae": "jb", "jnc": "jae", "jnb": "jae", "jz": "je",
         "jnz": "jne", "jna": "jbe", "jnbe": "ja", "jpe": "jp", "jpo": "jnp", "jnge": "jl",
         "jnl": "jge", "jng": "jle", "jnle": "jg"}
TOKEN = re.compile(r"\s*(0[xX][0-9a-fA-F]+|[0-9][0-9a-fA-F]*[hH]\b|\d+|'[^']'"
                   r"|[A-Za-z_.$?@][\w.$?@]*|<<|>>|[-+*/%&|^~()])")
NAME = r"[A-Za-z_.$?@][\w.$?@]*"
# x87: memory forms {mnemonic: {operand size: (escape, reg field)}}
FPU_MEM = {"fld": {"dword": (0xD9, 0), "qword": (0xDD, 0), "xword": (0xDB, 5)},
           "fst": {"dword": (0xD9, 2), "qword": (0xDD, 2)},
           "fstp": {"dword": (0xD9, 3), "qword": (0xDD, 3), "xword": (0xDB, 7)},
           "fild": {"word": (0xDF, 0), "dword": (0xDB, 0), "qword": (0xDF, 5)},
           "fist": {"word": (0xDF, 2), "dword": (0xDB, 2)},
           "fistp": {"word": (0xDF, 3), "dword": (0xDB, 3), "qword": (0xDF, 7)},
           "fldcw": {"word": (0xD9, 5)}, "fnstcw": {"word": (0xD9, 7)}, "fnstsw": {"word": (0xDD, 7)}}
FPU_ARITH = ("fadd", "fmul", "fcom", "fcomp", "fsub", "fsubr", "fdiv", "fdivr")    # reg field = index
for _k, _m in enumerate(FPU_ARITH):
    FPU_MEM[_m] = {"dword": (0xD8, _k), "qword": (0xDC, _k)}
    FPU_MEM["fi" + _m[1:]] = {"word": (0xDE, _k), "dword": (0xDA, _k)}
# register forms: one operand st(i) (escape, base of the second byte); "fadd st(1), st(0)" is FPU_REG2
FPU_REG1 = {**{m: (0xD8, 0xC0 + 8 * k) for k, m in enumerate(FPU_ARITH)},
            **{m + "p": (0xDE, b) for m, b in (("fadd", 0xC0), ("fmul", 0xC8), ("fsubr", 0xE0), ("fsub", 0xE8),
                                                 ("fdivr", 0xF0), ("fdiv", 0xF8))},
            "fld": (0xD9, 0xC0), "fxch": (0xD9, 0xC8), "fst": (0xDD, 0xD0), "fstp": (0xDD, 0xD8)}
FPU_REG2 = {"fadd": 0xC0, "fmul": 0xC8, "fsubr": 0xE0, "fsub": 0xE8, "fdivr": 0xF0, "fdiv": 0xF8}    # DC xx+i
FPU_IMPLIED = {"fld1": b"\xd9\xe8", "fldz": b"\xd9\xee", "fchs": b"\xd9\xe0", "fabs": b"\xd9\xe1",
               "ftst": b"\xd9\xe4", "fxam": b"\xd9\xe5", "fsqrt": b"\xd9\xfa", "frndint": b"\xd9\xfc",
               "fscale": b"\xd9\xfd", "fcompp": b"\xde\xd9"}
FPU_NAMES = set(FPU_MEM) | set(FPU_REG1) | set(FPU_IMPLIED) | {"fwait"}
EMU_SEG = {"ds": 0, "ss": 1, "cs": 2, "es": 3}


def emu_to_real(code):
    """The bytes the 8087 emulator leaves in place of its INT 34h..3Dh forms (fwait + the instruction)."""
    out = bytearray(code)
    i = 0
    while i < len(out) - 1:
        if out[i] == 0xCD and 0x34 <= out[i + 1] <= 0x3B:
            out[i], out[i + 1] = 0x9B, 0xD8 + out[i + 1] - 0x34
            i += 2
        elif out[i] == 0xCD and out[i + 1] == 0x3D:
            out[i], out[i + 1] = 0x9B, 0x90
            i += 2
        elif out[i] == 0xCD and out[i + 1] == 0x3C and i + 2 < len(out):
            b = out[i + 2]
            seg = {v: k for k, v in EMU_SEG.items()}[b >> 6]
            out[i], out[i + 1], out[i + 2] = 0x9B, SEG_PREFIX[seg], 0xD8 | (b & 7)
            i += 3
        else:
            i += 1
    return bytes(out)


class AsmError(Exception):
    pass


class Reg:
    def __init__(self, name):
        self.name = name
        self.size = 8 if name in R8 else 16
        self.code = (R8 if self.size == 8 else R16).index(name)


class SReg:
    def __init__(self, name):
        self.name = name
        self.code = SREG.index(name)


class FReg:
    def __init__(self, index):
        self.index = index        # st(index)


class Mem:
    def __init__(self, size, seg, bases, disp, kw=None):
        self.size = size          # 8, 16, "far" or None
        self.seg = seg            # explicit override or None
        self.bases = bases        # e.g. ("bx", "si")
        self.disp = disp          # expression text or None
        self.kw = kw              # the size word as written (byte word dword qword xword far) or None


class Imm:
    def __init__(self, expr):
        self.expr = expr


class FarImm:
    def __init__(self, seg, off):
        self.seg = seg
        self.off = off


class Stmt:
    def __init__(self, kind, line, text, **kw):
        self.kind = kind
        self.line = line
        self.text = text
        self.__dict__.update(kw)


def _strip_comment(line):
    quote = None
    for k, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == ";":
            return line[:k]
    return line


def split_operands(text):
    out, cur, depth, quote = [], "", 0, None
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _parse_mem_inner(inner):
    terms, cur, depth, sign = [], "", 0, "+"
    for ch in inner:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if depth == 0 and ch in "+-":
            if cur.strip():
                terms.append((sign, cur.strip()))
                sign = ch
            elif ch == "-":
                sign = "-" if sign == "+" else "+"
            cur = ""
            continue
        cur += ch
    if cur.strip():
        terms.append((sign, cur.strip()))
    bases, disp = [], []
    for sign, t in terms:
        if t.lower() in BASE_ORDER:
            if sign != "+":
                raise AsmError(f"negative base register in [{inner}]")
            bases.append(t.lower())
        else:
            disp.append(f"{sign}({t})")
    bases = tuple(sorted(bases, key=BASE_ORDER.index))
    if bases and bases not in RM_CODE:
        raise AsmError(f"invalid base/index combination [{inner}]")
    return bases, ("".join(disp) if disp else None)


def parse_operand(text):
    t = text.strip()
    size = kw = None
    m = re.match(r"^(?:(byte|word|dword|qword|xword|tbyte|far)\s+)?ptr\s+(.*)$", t, re.I)
    if m:
        kw = (m.group(1) or "").lower() or None
        kw = "xword" if kw == "tbyte" else kw
        size = {"byte": 8, "word": 16}.get(kw or "", "far")
        t = m.group(2).strip()
    m = re.match(r"^(?:(es|cs|ss|ds)\s*:\s*)?\[(.*)\]$", t, re.I)
    if m:
        bases, disp = _parse_mem_inner(m.group(2))
        return Mem(size, m.group(1).lower() if m.group(1) else None, bases, disp, kw)
    if size is not None:
        raise AsmError(f"ptr without a memory operand: {text}")
    low = t.lower()
    m = re.match(r"^st(?:\s*\(\s*([0-7])\s*\))?$", low)
    if m:
        return FReg(int(m.group(1) or 0))
    if low in R8 or low in R16:
        return Reg(low)
    if low in SREG:
        return SReg(low)
    m = re.match(r"^([^:\[\]']+):([^:\[\]']+)$", t)
    if m:
        return FarImm(m.group(1).strip(), m.group(2).strip())
    return Imm(t)


def _signed16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class Asm:
    def __init__(self, source, org=0x100, consts=None, fpu=None):
        if fpu not in (None, "emu", "real"):
            raise AsmError(f"fpu must be None, 'emu' or 'real', not {fpu!r}")
        self.fpu = fpu
        self.org = org
        self.consts = dict(consts or {})
        self.stmts = []
        self.label_names = set()
        self.labels = {}
        self.near_jmp = set()
        self._parse(source)

    # ---------------------------------------------------------------- parsing
    def _parse(self, source):
        for lineno, raw in enumerate(source.splitlines(), 1):
            line = _strip_comment(raw).strip()
            m = re.match(rf"^({NAME}):\s*(.*)$", line)
            if m and m.group(1).lower() not in R8 + R16 + SREG:
                name = m.group(1)
                if name in self.label_names or name in self.consts:
                    raise AsmError(f"line {lineno}: {name} defined twice")
                self.label_names.add(name)
                self.stmts.append(Stmt("label", lineno, raw, name=name))
                line = m.group(2).strip()
            if not line:
                continue
            m = re.match(rf"^({NAME})\s+equ\s+(.*)$", line, re.I)
            if m:
                if m.group(1) in self.consts or m.group(1) in self.label_names:
                    raise AsmError(f"line {lineno}: {m.group(1)} defined twice")
                self.consts[m.group(1)] = self._const(m.group(2), lineno)
                continue
            word, rest = re.match(r"^(\S+)\s*(.*)$", line).groups()
            word = ALIAS.get(word.lower(), word.lower())
            prefix = None
            if word in REP:
                prefix = word
                word, rest = re.match(r"^(\S+)\s*(.*)$", rest).groups()
                word = ALIAS.get(word.lower(), word.lower())
                if word not in STRING_OPS:
                    raise AsmError(f"line {lineno}: {prefix} before {word}")
            rest = rest.strip()
            if word in ("db", "dw"):
                items = []
                for item in split_operands(rest):
                    if item.startswith('"'):
                        if word != "db" or not item.endswith('"') or len(item) < 2:
                            raise AsmError(f"line {lineno}: bad string {item}")
                        items.append(item[1:-1].encode("ascii"))
                    else:
                        items.append(item)
                self.stmts.append(Stmt(word, lineno, raw, items=items))
                continue
            if word == "resb":
                self.stmts.append(Stmt("resb", lineno, raw, count=self._const(rest, lineno)))
                continue
            force = None
            ops = []
            for k, o in enumerate(split_operands(rest)):
                mm = re.match(r"^(short|near)\s+(.*)$", o, re.I)
                if mm and k == 0:
                    force = mm.group(1).lower()
                    o = mm.group(2)
                try:
                    ops.append(parse_operand(o))
                except AsmError as e:
                    raise AsmError(f"line {lineno}: {e}") from None
            self.stmts.append(Stmt("insn", lineno, raw, mnem=word, prefix=prefix, ops=ops,
                                   force=force))

    def _const(self, expr, lineno):
        try:
            v, lab = self.value(expr, labels_allowed=False)
        except AsmError as e:
            raise AsmError(f"line {lineno}: {e}") from None
        return v

    # ------------------------------------------------------------ expressions
    def value(self, expr, labels_allowed=True):
        """Value of an expression, and whether it refers to a label."""
        text, pos, out, lab = expr.strip(), 0, [], False
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m:
                raise AsmError(f"bad expression: {expr}")
            tok, pos = m.group(1), m.end()
            if tok[0] == "'":
                out.append(str(ord(tok[1])))
            elif tok[0].isdigit():
                if tok.lower().startswith("0x"):
                    out.append(str(int(tok, 16)))
                elif tok[-1] in "hH":
                    out.append(str(int(tok[:-1], 16)))
                else:
                    out.append(str(int(tok, 10)))
            elif re.match(NAME, tok):
                if tok in self.consts:
                    out.append(str(self.consts[tok]))
                elif tok in self.label_names and labels_allowed:
                    lab = True
                    out.append(str(self.labels.get(tok, 0)))
                else:
                    raise AsmError(f"unknown symbol {tok} in {expr}")
            elif tok == "/":
                out.append("//")
            else:
                out.append(tok)
        try:
            return eval(" ".join(out), {"__builtins__": {}}, {}), lab
        except Exception as e:
            raise AsmError(f"bad expression: {expr} ({e})") from None

    def _imm(self, op, bits):
        if not isinstance(op, Imm):
            raise AsmError("immediate expected")
        v, _ = self.value(op.expr)
        if not -(1 << (bits - 1)) <= v < (1 << bits):
            raise AsmError(f"{op.expr} = {v} does not fit in {bits} bits")
        return struct.pack("<B" if bits == 8 else "<H", v & ((1 << bits) - 1))

    def _fits8(self, op):
        v, lab = self.value(op.expr)
        return not lab and -128 <= _signed16(v) <= 127 and -0x8000 <= v <= 0xFFFF

    # --------------------------------------------------------------- encoding
    def _modrm(self, reg_field, rm):
        """(segment prefix, modrm and displacement) for a reg field and an r/m operand."""
        if isinstance(rm, Reg):
            return b"", bytes([0xC0 | reg_field << 3 | rm.code])
        if not isinstance(rm, Mem):
            raise AsmError("register or memory operand expected")
        default = "ss" if "bp" in rm.bases else "ds"
        prefix = bytes([SEG_PREFIX[rm.seg]]) if rm.seg and rm.seg != default else b""
        v, lab = self.value(rm.disp) if rm.disp else (0, False)
        if not -0x8000 <= v <= 0xFFFF:
            raise AsmError(f"displacement {rm.disp} out of range")
        if not rm.bases:
            return prefix, bytes([0x06 | reg_field << 3]) + struct.pack("<H", v & 0xFFFF)
        code = RM_CODE[rm.bases]
        if not lab and v == 0 and rm.bases != ("bp",):
            return prefix, bytes([code | reg_field << 3])
        if not lab and -128 <= _signed16(v) <= 127:
            return prefix, bytes([0x40 | code | reg_field << 3, v & 0xFF])
        return prefix, bytes([0x80 | code | reg_field << 3]) + struct.pack("<H", v & 0xFFFF)

    @staticmethod
    def _size(op, want=None):
        size = op.size if isinstance(op, Reg) else (op.size if isinstance(op, Mem) and
                                                    op.size in (8, 16) else None)
        if want is not None and size is not None and size != want:
            raise AsmError("operand size mismatch")
        return size or want

    def _need_size(self, op):
        size = self._size(op)
        if size is None:
            raise AsmError("operand size unknown; write byte ptr or word ptr")
        return size

    def _encode(self, i, st, addr):
        if st.kind == "db":
            return b"".join(x if isinstance(x, bytes) else self._imm(Imm(x), 8) for x in st.items)
        if st.kind == "dw":
            return b"".join(self._imm(Imm(x), 16) for x in st.items)
        if st.kind == "resb":
            return bytes(st.count)
        try:
            if st.prefix:
                return bytes([REP[st.prefix]]) + self._insn(i, st, addr + 1)
            return self._insn(i, st, addr)
        except AsmError as e:
            raise AsmError(f"line {st.line}: {st.text.strip()}: {e}") from None

    def _insn(self, i, st, addr):
        mn, ops = st.mnem, st.ops
        n = len(ops)
        if mn in FPU_NAMES or (mn == "fnstsw" and n == 1 and isinstance(ops[0], Reg)):
            return self._fpu(mn, ops)
        if mn in IMPLIED and n == 0:
            return bytes([IMPLIED[mn]])
        if mn in STRING_OPS and n == 0:
            return bytes([STRING_OPS[mn]])
        if mn in ALU and n == 2:
            return self._alu(ALU.index(mn), *ops)
        if mn == "test" and n == 2:
            return self._test(*ops)
        if mn == "mov" and n == 2:
            return self._mov(*ops)
        if mn in ("push", "pop") and n == 1:
            return self._pushpop(mn, ops[0])
        if mn in ("inc", "dec") and n == 1:
            return self._incdec(mn, ops[0])
        if mn in UNARY and n == 1:
            size = self._need_size(ops[0])
            pre, mrm = self._modrm(UNARY[mn], ops[0])
            return pre + bytes([0xF6 if size == 8 else 0xF7]) + mrm
        if mn == "imul" and n == 3:
            return self._imul3(*ops)
        if mn in SHIFT and n == 2:
            return self._shift(SHIFT[mn], *ops)
        if mn in ("lea", "les", "lds") and n == 2:
            reg, mem = ops
            if not (isinstance(reg, Reg) and reg.size == 16 and isinstance(mem, Mem)):
                raise AsmError(f"{mn} needs a 16-bit register and memory")
            pre, mrm = self._modrm(reg.code, mem)
            return pre + bytes([{"lea": 0x8D, "les": 0xC4, "lds": 0xC5}[mn]]) + mrm
        if mn == "xchg" and n == 2:
            return self._xchg(*ops)
        if mn == "in" and n == 2:
            return self._inout(0xE4, ops[0], ops[1])
        if mn == "out" and n == 2:
            return self._inout(0xE6, ops[1], ops[0])
        if mn == "int" and n == 1:
            return b"\xcd" + self._imm(ops[0], 8)
        if mn in ("ret", "retf") and n == 1:
            return bytes([0xC2 if mn == "ret" else 0xCA]) + self._imm(ops[0], 16)
        if mn == "enter" and n == 2:
            return b"\xc8" + self._imm(ops[0], 16) + self._imm(ops[1], 8)
        if mn in ("jmp", "call") and n == 1:
            return self._jmpcall(i, st, mn, ops[0], addr)
        if mn in ("ljmp", "lcall"):
            return self._far(mn, ops)
        if mn in JCC and n == 1:
            return self._short(0x70 + JCC[mn], ops[0], addr)
        if mn in SHORT_ONLY and n == 1:
            return self._short(SHORT_ONLY[mn], ops[0], addr)
        raise AsmError(f"unsupported instruction form: {mn} with {n} operand(s)")

    def _alu(self, n, dst, src):
        if isinstance(src, Imm):
            size = self._need_size(dst)
            if isinstance(dst, Reg) and dst.code == 0:
                return bytes([n * 8 + (4 if size == 8 else 5)]) + self._imm(src, size)
            pre, mrm = self._modrm(n, dst)
            if size == 8:
                return pre + b"\x80" + mrm + self._imm(src, 8)
            if self._fits8(src):
                return pre + b"\x83" + mrm + bytes([self.value(src.expr)[0] & 0xFF])
            return pre + b"\x81" + mrm + self._imm(src, 16)
        if isinstance(src, Reg):
            size = self._size(dst, src.size)
            pre, mrm = self._modrm(src.code, dst)
            return pre + bytes([n * 8 + (0 if size == 8 else 1)]) + mrm
        if isinstance(dst, Reg) and isinstance(src, Mem):
            size = self._size(src, dst.size)
            pre, mrm = self._modrm(dst.code, src)
            return pre + bytes([n * 8 + (2 if size == 8 else 3)]) + mrm
        raise AsmError("bad operands")

    def _test(self, a, b):
        if isinstance(a, Imm):
            a, b = b, a
        if isinstance(b, Imm):
            size = self._need_size(a)
            if isinstance(a, Reg) and a.code == 0:
                return bytes([0xA8 if size == 8 else 0xA9]) + self._imm(b, size)
            pre, mrm = self._modrm(0, a)
            return pre + bytes([0xF6 if size == 8 else 0xF7]) + mrm + self._imm(b, size)
        if isinstance(a, Mem):
            a, b = b, a
        if not isinstance(a, Reg):
            raise AsmError("bad operands")
        size = self._size(b, a.size)
        pre, mrm = self._modrm(a.code, b)
        return pre + bytes([0x84 if size == 8 else 0x85]) + mrm

    def _mov(self, dst, src):
        if isinstance(dst, SReg):
            if dst.name == "cs":
                raise AsmError("mov cs is not allowed")
            self._size(src, 16)
            pre, mrm = self._modrm(dst.code, src)
            return pre + b"\x8e" + mrm
        if isinstance(src, SReg):
            self._size(dst, 16)
            pre, mrm = self._modrm(src.code, dst)
            return pre + b"\x8c" + mrm
        if isinstance(src, Imm):
            if isinstance(dst, Reg):
                return bytes([(0xB0 if dst.size == 8 else 0xB8) + dst.code]) + self._imm(src, dst.size)
            size = self._need_size(dst)
            pre, mrm = self._modrm(0, dst)
            return pre + bytes([0xC6 if size == 8 else 0xC7]) + mrm + self._imm(src, size)
        if isinstance(dst, Reg) and isinstance(src, Mem):
            size = self._size(src, dst.size)
            if dst.code == 0 and not src.bases:
                pre, mrm = self._modrm(0, src)
                return pre + bytes([0xA0 if size == 8 else 0xA1]) + mrm[1:]
            pre, mrm = self._modrm(dst.code, src)
            return pre + bytes([0x8A if size == 8 else 0x8B]) + mrm
        if isinstance(src, Reg):
            size = self._size(dst, src.size)
            if isinstance(dst, Mem) and src.code == 0 and not dst.bases:
                pre, mrm = self._modrm(0, dst)
                return pre + bytes([0xA2 if size == 8 else 0xA3]) + mrm[1:]
            pre, mrm = self._modrm(src.code, dst)
            return pre + bytes([0x88 if size == 8 else 0x89]) + mrm
        raise AsmError("bad operands")

    def _pushpop(self, mn, op):
        if isinstance(op, Reg):
            if op.size != 16:
                raise AsmError(f"{mn} needs a 16-bit register")
            return bytes([(0x50 if mn == "push" else 0x58) + op.code])
        if isinstance(op, SReg):
            if mn == "pop" and op.name == "cs":
                raise AsmError("pop cs is not allowed")
            return bytes([(0x06 if mn == "push" else 0x07) + op.code * 8])
        if isinstance(op, Imm) and mn == "push":
            if self._fits8(op):
                return bytes([0x6A, self.value(op.expr)[0] & 0xFF])
            return b"\x68" + self._imm(op, 16)
        if isinstance(op, Mem):
            self._size(op, 16)
            pre, mrm = self._modrm(6 if mn == "push" else 0, op)
            return pre + (b"\xff" if mn == "push" else b"\x8f") + mrm
        raise AsmError("bad operand")

    def _incdec(self, mn, op):
        k = 0 if mn == "inc" else 1
        if isinstance(op, Reg) and op.size == 16:
            return bytes([(0x40 if k == 0 else 0x48) + op.code])
        size = self._need_size(op)
        pre, mrm = self._modrm(k, op)
        return pre + bytes([0xFE if size == 8 else 0xFF]) + mrm

    def _imul3(self, dst, src, imm):
        if not (isinstance(dst, Reg) and dst.size == 16 and isinstance(imm, Imm)):
            raise AsmError("imul r16, r/m16, imm expected")
        self._size(src, 16)
        pre, mrm = self._modrm(dst.code, src)
        if self._fits8(imm):
            return pre + b"\x6b" + mrm + bytes([self.value(imm.expr)[0] & 0xFF])
        return pre + b"\x69" + mrm + self._imm(imm, 16)

    def _shift(self, n, dst, cnt):
        size = self._need_size(dst)
        pre, mrm = self._modrm(n, dst)
        w = 0 if size == 8 else 1
        if isinstance(cnt, Reg) and cnt.name == "cl":
            return pre + bytes([0xD2 + w]) + mrm
        if isinstance(cnt, Imm):
            v, lab = self.value(cnt.expr)
            if not lab and v == 1:
                return pre + bytes([0xD0 + w]) + mrm
            return pre + bytes([0xC0 + w]) + mrm + self._imm(cnt, 8)
        raise AsmError("shift count must be cl or an immediate")

    def _xchg(self, a, b):
        if isinstance(a, Reg) and isinstance(b, Reg) and a.size == b.size == 16 and \
                (a.code == 0) != (b.code == 0):
            return bytes([0x90 + (b.code if a.code == 0 else a.code)])
        if isinstance(a, Mem):
            a, b = b, a
        if not isinstance(a, Reg):
            raise AsmError("bad operands")
        size = self._size(b, a.size)
        pre, mrm = self._modrm(a.code, b)
        return pre + bytes([0x86 if size == 8 else 0x87]) + mrm

    def _inout(self, base, acc, port):
        if not (isinstance(acc, Reg) and acc.code == 0):
            raise AsmError("in/out needs al or ax")
        w = 0 if acc.size == 8 else 1
        if isinstance(port, Reg) and port.name == "dx":
            return bytes([base + 8 + w])
        return bytes([base + w]) + self._imm(port, 8)

    def _jmpcall(self, i, st, mn, op, addr):
        if isinstance(op, (Reg, Mem)):
            self._size(op, 16)
            pre, mrm = self._modrm(4 if mn == "jmp" else 2, op)
            return pre + b"\xff" + mrm
        if not isinstance(op, Imm):
            raise AsmError("bad branch target")
        v, _ = self.value(op.expr)
        if mn == "call":
            return b"\xe8" + struct.pack("<H", (v - (addr + 3)) & 0xFFFF)
        near = st.force == "near" or i in self.near_jmp
        if not near:
            disp = v - (addr + 2)
            if -128 <= disp <= 127:
                return bytes([0xEB, disp & 0xFF])
            if st.force == "short":
                if self.final:
                    raise AsmError(f"short jump out of range ({disp})")
            elif self.relax:
                self.near_jmp.add(i)
                self.grew = True
            return bytes([0xEB, 0])
        return b"\xe9" + struct.pack("<H", (v - (addr + 3)) & 0xFFFF)

    def _far(self, mn, ops):
        if len(ops) == 1 and isinstance(ops[0], Mem):
            pre, mrm = self._modrm(5 if mn == "ljmp" else 3, ops[0])
            return pre + b"\xff" + mrm
        if len(ops) == 1 and isinstance(ops[0], FarImm):
            seg, off = Imm(ops[0].seg), Imm(ops[0].off)
        elif len(ops) == 2 and all(isinstance(o, Imm) for o in ops):
            seg, off = ops
        else:
            raise AsmError(f"{mn} needs memory or seg:off")
        return bytes([0xEA if mn == "ljmp" else 0x9A]) + self._imm(off, 16) + self._imm(seg, 16)

    def _fpu(self, mn, ops):
        """An x87 instruction in the form self.fpu asks for."""
        if self.fpu is None:
            raise AsmError("x87 instruction without Asm(..., fpu='emu' or 'real')")
        pre = b""
        if mn == "fwait" and not ops:
            return b"\xcd\x3d" if self.fpu == "emu" else b"\x9b"
        if mn == "fnstsw" and len(ops) == 1 and isinstance(ops[0], Reg):
            if ops[0].name != "ax":
                raise AsmError("fnstsw takes ax or a word in memory")
            esc, rest = 0xDF, b"\xe0"
        elif mn in FPU_IMPLIED and not ops:
            esc, rest = FPU_IMPLIED[mn][0], FPU_IMPLIED[mn][1:]
        elif len(ops) == 1 and isinstance(ops[0], Mem) and mn in FPU_MEM:
            forms = FPU_MEM[mn]
            kw = ops[0].kw
            if kw not in forms:
                raise AsmError(f"{mn} takes {' / '.join(forms)} ptr, not {kw or 'no size'}")
            esc, reg = forms[kw]
            pre, mrm = self._modrm(reg, ops[0])
            rest = mrm
        elif len(ops) == 1 and isinstance(ops[0], FReg) and mn in FPU_REG1:
            esc, base = FPU_REG1[mn]
            rest = bytes([base + ops[0].index])
        elif len(ops) == 2 and all(isinstance(o, FReg) for o in ops) and mn in FPU_REG2 and ops[1].index == 0:
            esc, rest = 0xDC, bytes([FPU_REG2[mn] + ops[0].index])
        else:
            raise AsmError(f"unsupported x87 form: {mn} with {len(ops)} operand(s)")
        if self.fpu == "real":
            return b"\x9b" + pre + bytes([esc]) + rest
        if pre:
            seg = {v: k for k, v in SEG_PREFIX.items()}[pre[0]]
            return bytes([0xCD, 0x3C, EMU_SEG[seg] << 6 | 0x18 | (esc & 7)]) + rest
        return bytes([0xCD, 0x34 + esc - 0xD8]) + rest

    def _short(self, opcode, op, addr):
        if not isinstance(op, Imm):
            raise AsmError("bad branch target")
        disp = self.value(op.expr)[0] - (addr + 2)
        if not -128 <= disp <= 127:
            if self.final:
                raise AsmError(f"short branch out of range ({disp})")
            return bytes([opcode, 0])
        return bytes([opcode, disp & 0xFF])

    # --------------------------------------------------------------- assembly
    def _pass(self):
        addr, out, listing, labels = self.org, bytearray(), [], {}
        for i, st in enumerate(self.stmts):
            if st.kind == "label":
                labels[st.name] = addr
                continue
            code = self._encode(i, st, addr)
            listing.append((addr, code, st))
            out += code
            addr += len(code)
        return bytes(out), listing, labels

    def build(self):
        """Assemble; returns the code and fills self.labels and self.listing."""
        self.final = False
        self.relax = False
        self.labels = {}
        for attempt in range(100):
            self.grew = False
            _code, _listing, labels = self._pass()
            if labels == self.labels and not self.grew:
                break
            self.labels = labels
            self.relax = True
        else:
            raise AsmError("jump sizes do not converge")
        self.final = True
        code, self.listing, labels = self._pass()
        assert labels == self.labels
        self._verify()
        return code

    # ----------------------------------------------------------- verification
    def _canon(self, mnem, prefix, ops):
        mnem = ALIAS.get(mnem, mnem)
        if prefix:
            prefix = ALIAS.get(prefix, prefix)
        if mnem in STRING_OPS:
            return prefix, mnem, ()
        if mnem in ("lcall", "ljmp") and len(ops) == 2 and all(isinstance(o, Imm) for o in ops):
            ops = [FarImm(ops[0].expr, ops[1].expr)]
        is8 = any((isinstance(o, Reg) and o.size == 8) or (isinstance(o, Mem) and o.size == 8)
                  for o in ops)
        mask = 0xFF if is8 else 0xFFFF
        out = []
        for o in ops:
            if isinstance(o, Reg):
                out.append(("r", o.name))
            elif isinstance(o, FReg):
                out.append(("st", o.index))
            elif isinstance(o, SReg):
                out.append(("s", o.name))
            elif isinstance(o, Imm):
                out.append(("i", self.value(o.expr)[0] & mask))
            elif isinstance(o, FarImm):
                out.append(("f", self.value(o.seg)[0] & 0xFFFF, self.value(o.off)[0] & 0xFFFF))
            else:
                default = "ss" if "bp" in o.bases else "ds"
                disp = self.value(o.disp)[0] & 0xFFFF if o.disp else 0
                out.append(("m", o.seg or default, o.bases, disp, o.size if o.size in (8, 16) else None,
                            o.kw if mnem in FPU_NAMES else None))
        if mnem in ("xchg", "test"):
            out.sort(key=repr)
        return prefix, mnem, out

    @staticmethod
    def _same(a, b):
        if a[:2] != b[:2] or len(a[2]) != len(b[2]):
            return False
        for x, y in zip(a[2], b[2]):
            if x[0] == "m" and y[0] == "m":
                if x[:4] != y[:4] or (x[4] and y[4] and x[4] != y[4]) or x[5] != y[5]:
                    return False
            elif x != y:
                return False
        return True

    def _verify(self):
        cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
        for addr, code, st in self.listing:
            if st.kind != "insn":
                continue
            if st.mnem in FPU_NAMES or st.mnem == "fnstsw":
                real = emu_to_real(code) if self.fpu == "emu" else code
                dec = list(cs.disasm(real, addr))
                text = " ".join(f"{d.mnemonic} {d.op_str}" for d in dec)
                if st.mnem == "fwait":
                    want = ["wait", "nop"] if self.fpu == "emu" else ["wait"]
                    if [d.mnemonic for d in dec] != want or sum(d.size for d in dec) != len(real):
                        raise AsmError(f"line {st.line}: {st.text.strip()} -> {code.hex()} decodes as {text!r}")
                    continue
                if len(dec) != 2 or dec[0].mnemonic != "wait" or sum(d.size for d in dec) != len(real):
                    raise AsmError(f"line {st.line}: {st.text.strip()} -> {code.hex()} decodes as {text!r}")
                dec = dec[1:]
            else:
                dec = list(cs.disasm(code, addr))
                text = " ".join(f"{d.mnemonic} {d.op_str}" for d in dec)
                if len(dec) != 1 or dec[0].size != len(code):
                    raise AsmError(f"line {st.line}: {st.text.strip()} -> {code.hex()} decodes as {text!r}")
            mnem, prefix = dec[0].mnemonic, None
            if " " in mnem:
                prefix, mnem = mnem.split(" ", 1)
            ops = [] if mnem in STRING_OPS else [parse_operand(o) for o in split_operands(dec[0].op_str)]
            want = self._canon(st.mnem, st.prefix, st.ops)
            got = self._canon(mnem, prefix, ops)
            if not self._same(want, got):
                raise AsmError(f"line {st.line}: {st.text.strip()} -> {code.hex()} decodes as {text!r}")

    def listing_text(self):
        return "\n".join(f"{addr:04X}  {code.hex():<20} {st.text.strip()}" for addr, code, st in self.listing)


def assemble(source, org=0x100, consts=None):
    """(code bytes, labels) for a source text."""
    a = Asm(source, org, consts)
    code = a.build()
    return code, a.labels
