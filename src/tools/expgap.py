#!/usr/bin/env python3
"""Experience by level gap (等级差经验): each member's share of a battle's experience grows with how far
below the enemies they stand and shrinks with how far above.

    expgap.py               what the patch writes into files/DDS98

The rule (the user, 2026-09-30, 「等级差距越大分得经验越多的系统，每个队员单独算」; 2026-10-06, 「改成真5的机制，
保留split」: 真・女神転生V's level-gap factor, the game's own split kept)
    Every enemy defeated counts on its own. A member of level l gets, for an enemy of level L that gave
    E experience, E x 2^(g / 5) with g = L - l held to -10..10: five levels below it twice, ten and more
    four times; five levels above it half, ten and more a quarter. The factor is taken to 1/4096
    (FACTORS[g] = round(4096 x 2^(g / 5)), exact at g = 0, -+5, -+10). Each member is reckoned on its own,
    then divided as the game divides: member's share = 2 x (sum over the enemies of E x FACTORS[g]) /
    (4096 x N), rounded down, with N the members who take a share (358E:4B7C(1)). A member level with
    every enemy gets exactly the original 2X/N. Who takes a share (status, level 99) is the game's test,
    untouched.

How the game shares experience out (tools/expshow.py has the whole story)
    Every enemy defeated adds its +6Eh to the dword DS:9B0C (25CA:AA37-AA46, es:si the enemy); the
    payout ov02:0000 doubles the sum, divides it by 358E:4B7C(1), and for each party slot fetches the
    member (358E:514C(slot), ov02:0029) and hands it the quotient (ov02:005C: no member, a status of
    DS:2426, or level 99 -> nothing). DS:9B0C is cleared after the payout (ov02:03B1) and when the
    level-up screen closes (ov02:04F1), and nowhere else: a fight the party flees keeps its defeats' sum
    for the next won one. No save file holds it (the savers ov03:0977.. write other blocks).

The patch
    The defeat (25CA:AA37) calls HOOK in 1603's cave, which adds the experience to DS:9B0C as before and
    to BUCKETS[min(L, 99)], 100 dwords of the enemy levels; when DS:9B0C is 0 before the add, the buckets
    are emptied first, and GAIN counts them only while DS:9B0C is not 0 (a fight won without a defeat
    leaves the last one's buckets behind), so they are always the sum's breakdown. GAIN sums bucket x
    FACTORS[g] in 48 bits (a dword times a factor up to 4 x 4096 outgrows 32 bits from a sum of 2^18) and
    divides by N x 2048 in three steps. The
    payout's slot lookup at ov02:0029 is turned to MEMBER: it fetches the member through 358E:514C and
    writes that member's own share (GAIN) into ov02:0000's frame where the common quotient was, so
    ov02:005C hands each member its own amount. The talk outcome that would add a demon's +6Eh to
    DS:9B0C (1603:E2D3) is never reached (tools/expshow.py); it would not reach the buckets.

    The summary line (经验值显示修复's index 4 of 1603:A71C) shows the protagonist's own gain - roster
    member 0 (358E:507E(0)), 0 when the game's test keeps him from a share - and says so: 「主角获得 X 点
    ＥＸＰ」, 「主人公は X ＥＸＰ獲得！」 in the Japanese original. This part sits on 经验值显示修复's
    own sites, so the patch needs that fix in and is taken out before it.

Where the code goes
    1603:4F20-53A0 is a cluster of routines that only call one another: run/reachable.py finds no near
    or far call, jump, pointer or pushed offset reaching any of its entries (4F20, 4FC2, 531E, 537A), and
    the whole-program trace (run/uncovered.py) never enters it. Relocated words sit at 4F30 and 513C, so
    BUCKETS, HOOK and FACTORS take 4F32-513B and GAIN / SHOWN / MEMBER 513E-52B6. Calls into 358E go by pushing
    a return address and the target and a retf (358E = CS + 1F8Bh), the defeat's stub reaches 1603 the
    same way (1603 = CS - 0FC7h), and ov02:0029 keeps its relocated far call with the segment word
    turned from 358E to 1603 - the loader adds the load segment to it just the same.

It is off in the 原版's image and built into the 再平衡版's; 汉化补丁.html offers it as an option for either
(tools/options.py). tools/expgap_test.py runs the defeat, the payout and the summary's reader on an emulated CPU
against the rule above.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import expshow  # noqa: E402
from asm86 import assemble  # noqa: E402
from mz import overlays  # noqa: E402
from storyfix import StoryFixError  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98")
EXE = "DDS98.EXE"
NAME = "等级差经验"
NEEDS = expshow.NAME                    # the summary's reader and wording are that fix's sites
CHARS = set("主角获得")                 # the Chinese wording: make.py gives them codes in every build
HDR, SEG16, SEG25 = 0x3800, 0x16030, 0x25CA0
GAP_MAX, LEVELS = 10, 100               # the gap counts -10..10 levels; buckets for levels 0..99
SCALE_BITS = 12                         # the factors in units of 1/4096
FACTORS = [round((1 << SCALE_BITS) * 2 ** (g / 5)) for g in range(-GAP_MAX, GAP_MAX + 1)]   # 2^(g/5)

BUCKETS = 0x4F32                        # 100 dwords, 4F32-50C1
CODE1_AT, CODE1_END = 0x50C2, 0x513C    # HOOK and FACTORS, up to the relocated word at 513C
CODE2_AT, CODE2_END = 0x513E, 0x52B7    # GAIN, SHOWN and MEMBER, up to the relocated word at 52B7

CODE1 = f"""
hook:                           ; far, from 25CA:AA37: es:si the enemy defeated, ds = DGROUP
    mov ax, word ptr [0x9b0c]
    or ax, word ptr [0x9b0e]
    jne hook_add
    push es                     ; a new sum: empty the buckets (ax = 0)
    push di
    push cx
    push cs
    pop es
    mov di, {BUCKETS:#x}
    mov cx, {LEVELS * 2}
    cld
    rep stosw
    pop cx
    pop di
    pop es
hook_add:
    mov ax, word ptr es:[si + 0x6e]
    mov dx, word ptr es:[si + 0x70]
    add word ptr [0x9b0c], ax
    adc word ptr [0x9b0e], dx
    push bx
    mov bl, byte ptr es:[si + 0x6b]
    xor bh, bh
    cmp bx, {LEVELS - 1}
    jbe hook_level
    mov bx, {LEVELS - 1}
hook_level:
    shl bx, 1
    shl bx, 1
    add word ptr cs:[bx + {BUCKETS:#x}], ax
    adc word ptr cs:[bx + {BUCKETS + 2:#x}], dx
    pop bx
    retf
factors:                        ; FACTORS: 4096 x 2^(g/5) for the gaps -10 .. 10
    dw {", ".join(str(f) for f in FACTORS)}
"""
CODE1_BYTES, CODE1_LABELS = assemble(CODE1, org=CODE1_AT)

CODE2 = f"""
gain:                           ; near: [bp+4] unit offset, [bp+6] its segment -> dx:ax its share
    push bp
    mov bp, sp
    sub sp, 10                  ; [bp-6] [bp-4] [bp-2] W bits 0-15 16-31 32-47, [bp-8] 2048N, [bp-10] the level
    push si
    push di
    mov ax, word ptr [0x9b0c]   ; no sum: the buckets are a past one's
    or ax, word ptr [0x9b0e]
    je gain_zero
    les si, dword ptr [bp + 4]
    mov ax, es
    or ax, si
    jne gain_unit
gain_zero:
    xor ax, ax
    cwd
    jmp near gain_out
gain_unit:
    mov al, byte ptr es:[si + 0x6b]
    xor ah, ah
    mov word ptr [bp - 10], ax
    push 1                      ; 358E:4B7C(1): the members who take a share
    push cs
    push gain_n
    mov ax, cs
    add ax, 0x1f8b
    push ax
    push 0x4b7c
    retf
gain_n:
    or ax, ax
    je gain_zero
    shl ax, {SCALE_BITS - 1}
    mov word ptr [bp - 8], ax
    xor ax, ax
    mov word ptr [bp - 6], ax
    mov word ptr [bp - 4], ax
    mov word ptr [bp - 2], ax
    xor di, di                  ; the enemy level
gain_level:
    mov bx, di
    shl bx, 1
    shl bx, 1
    mov ax, word ptr cs:[bx + {BUCKETS:#x}]
    mov dx, word ptr cs:[bx + {BUCKETS + 2:#x}]
    mov cx, ax
    or cx, dx
    je gain_next
    mov bx, di
    sub bx, word ptr [bp - 10]  ; the gap, held to -10 .. 10
    cmp bx, {-GAP_MAX}
    jge gain_above
    mov bx, {-GAP_MAX}
gain_above:
    cmp bx, {GAP_MAX}
    jle gain_k
    mov bx, {GAP_MAX}
gain_k:
    shl bx, 1
    mov cx, word ptr cs:[bx + {CODE1_LABELS['factors'] + 2 * GAP_MAX:#x}]
    mov bx, dx
    mul cx                      ; the bucket times its factor into W, 48 bits
    add word ptr [bp - 6], ax
    adc word ptr [bp - 4], dx
    adc word ptr [bp - 2], 0
    mov ax, bx
    mul cx
    add word ptr [bp - 4], ax
    adc word ptr [bp - 2], dx
gain_next:
    inc di
    cmp di, {LEVELS}
    jb gain_level
    mov cx, word ptr [bp - 8]   ; W / 2048N = 2W / 4096N, its low 32 bits
    mov ax, word ptr [bp - 2]
    xor dx, dx
    div cx
    mov ax, word ptr [bp - 4]
    div cx
    mov bx, ax
    mov ax, word ptr [bp - 6]
    div cx
    mov dx, bx
gain_out:
    pop di
    pop si
    mov sp, bp
    pop bp
    ret 4

shown:                          ; near -> dx:ax what the protagonist takes from this battle
    push si
    push 0                      ; 358E:507E(0): roster member 0
    push cs
    push shown_unit
    mov ax, cs
    add ax, 0x1f8b
    push ax
    push 0x507e
    retf
shown_unit:
    mov si, ax
    or ax, dx
    je shown_zero
    mov es, dx
    cmp byte ptr es:[si + 0x6b], 0x63
    jae shown_zero
    push dx
    push dx
    lea ax, [si + 0x156]
    push ax
    push cs
    push shown_status
    mov ax, cs
    add ax, 0x1f8b
    push ax
    push 0x3d7c                 ; 358E:3D7C(status bits): ov02:005C's test
    retf
shown_status:
    pop dx
    or ax, ax
    jne shown_zero
    push dx
    push si
    call gain
    pop si
    ret
shown_zero:
    xor ax, ax
    cwd
    pop si
    ret

member:                         ; far, for 358E:514C(slot) at ov02:0029; bp is ov02:0000's frame
    push bp
    mov bp, sp
    push si
    push di
    push word ptr [bp + 6]
    push cs
    push member_got
    mov ax, cs
    add ax, 0x1f8b
    push ax
    push 0x514c
    retf
member_got:
    mov si, ax
    mov di, dx
    push dx
    push ax
    call gain
    mov bx, word ptr [bp]       ; ov02:0000's frame: its share at [bx+4] / [bx+6]
    mov word ptr ss:[bx + 4], ax
    mov word ptr ss:[bx + 6], dx
    mov ax, si
    mov dx, di
    pop di
    pop si
    pop bp
    retf 2
"""
CODE2_BYTES, CODE2_LABELS = assemble(CODE2, org=CODE2_AT)

STUB_AT = 0xAA37                        # 25CA: the defeat's add to DS:9B0C, 16 bytes
STUB_ORIG = bytes.fromhex("26 8b 44 6e 26 8b 54 70 01 06 0c 9b 11 16 0e 9b")
STUB = assemble(f"""
    push cs
    push 0xaa45
    mov ax, cs
    sub ax, 0xfc7
    push ax
    push {CODE1_LABELS['hook']:#x}
    retf
    nop
    nop
""", org=STUB_AT)[0]

CALL_AT = 0x0029                        # ov02: lcall 358E:514C in the payout's loop
CALL_ORIG = bytes.fromhex("9a 4c 51 8e 35")
CALL = bytes([0x9A]) + CODE2_LABELS["member"].to_bytes(2, "little") + (0x1603).to_bytes(2, "little")

SHARE = assemble(f"""
share:                          ; A71C, index above 3: ax = index - 3, bp = A71C's frame
    dec ax
    jne share_none
    call {CODE2_LABELS['shown']:#x}
    jmp near 0xa756             ; leave, ret 2
share_none:
    xor ax, ax
    jmp near 0xa755             ; cdq, leave, ret 2
""", org=expshow.SHARE_AT)[0]
SHARE = SHARE + b"\x90" * (len(expshow.SHARE_CODE) - len(SHARE))

for _name, _code, _at, _end in (("HOOK / FACTORS", CODE1_BYTES, CODE1_AT, CODE1_END),
                                ("GAIN / SHOWN / MEMBER", CODE2_BYTES, CODE2_AT, CODE2_END)):
    if _at + len(_code) > _end:
        raise StoryFixError(f"{_name} 超出了 1603:{_at:04X}-{_end - 1:04X}")
if len(STUB) != len(STUB_ORIG) or len(SHARE) != len(expshow.SHARE_CODE):
    raise StoryFixError("改写的长度与原来不同")


def _main_orig(at, length):
    blob = open(os.path.join(SRC, EXE), "rb").read()
    return blob[HDR + SEG16 + at:HDR + SEG16 + at + length]


def _ov02_file(at):
    ov = overlays(os.path.join(SRC, EXE))[2]
    return ov.file_off + ov.hdr + at


EXE_SITES = [
    (HDR + SEG25 + STUB_AT, STUB_ORIG, STUB,
     "打倒敌人时（25CA:AA37）：经验照旧加进 DS:9B0C，同时按敌人等级记进新例程的分级表"),
    (_ov02_file(CALL_AT), CALL_ORIG, CALL,
     "发放经验的循环（ov02:0029）：取队员改走新例程，它把这个队员自己的份额写给 ov02:005C"),
    (HDR + SEG16 + BUCKETS, _main_orig(BUCKETS, CODE1_END - BUCKETS),
     bytes(4 * LEVELS) + CODE1_BYTES + _main_orig(CODE1_AT + len(CODE1_BYTES), CODE1_END - CODE1_AT - len(CODE1_BYTES)),
     "按敌人等级的经验表、记账例程与等级差倍率表（放在没有任何入口的 1603:4F32-513B）"),
    (HDR + SEG16 + CODE2_AT, _main_orig(CODE2_AT, len(CODE2_BYTES)), CODE2_BYTES,
     "新例程：按等级差算每个队员的份额、发放时换上它、主角这一战得多少（放在没有任何入口的 1603:513E 起）"),
]
# on 经验值显示修复's routine: its fixed form is this patch's starting point
NEEDS_SITES = [
    (HDR + SEG16 + expshow.SHARE_AT, expshow.SHARE_CODE, SHARE,
     "结算那行的数值（经验值显示修复的 1603:4805）：改为主角这一战实得的经验"),
]
if len(EXE_SITES[2][1]) != len(EXE_SITES[2][2]):
    raise StoryFixError("分级表与例程的长度不对")


class Line:
    """The summary's experience line, from 经验值显示修复's form to this patch's, in whichever version the
    record holds: forms are (fixed by that fix, this patch) pairs of the same length, one per version,
    and exactly one of the first has to be in the record, once, on token boundaries."""

    def __init__(self, stem, chunk, rid, forms, why=""):
        self.stem, self.chunk, self.rid, self.forms, self.why = stem, chunk, rid, forms, why
        if any(len(a) != len(b) for a, b in forms):
            raise StoryFixError(f"{self}: 两种写法的字节数不同")

    def __str__(self):
        return f"{self.stem}/{self.chunk}/{self.rid:02X} 文字"

    def edits(self, payload, end):
        return expshow.Wording.edits(self, payload, end)


def by_file(charmap=None, english=False):
    """The script edit, made on 经验值显示修复's record. The Chinese wording is encoded with the build's
    charmap, so it is known only to a build; without one only the Japanese original's can be found."""
    value = b"\x1f\x02\x4f\x00\x04"                                   # 4F0004, that fix's reading
    forms = [(b"\x04\x19" + value + b"\x03\x0f" + "ずつ獲得した".encode("cp932"),   # 〈一行〉たちは X ＥＸＰ…
              "主人公は".encode("cp932") + value + b"\x03\x0f" + "獲得！".encode("cp932"))]
    if english:
        forms = [(b"Each gets ", b"Hero gets ")]
    if charmap is not None:
        from textbuild import encode_plain
        forms.append((b"\x04\x19" + encode_plain("各获得", charmap), encode_plain("主角获得", charmap)))
    return {expshow.STEM: [Line(expshow.STEM, expshow.CHUNK, expshow.RECORD, forms,
                                why="结算的经验值那一行改说主角：「主角获得 X 点ＥＸＰ」／「主人公は X ＥＸＰ獲得！」")]}


def apply_to(parsed, fixes):
    """Rewrite the summary's record of a parsed file that holds 经验值显示修复's form. -> the edits made,
    as storyfix.record_edits() gives them."""
    return expshow.apply_to(parsed, fixes)


def mend_exe(blob, revert=False):
    """DDS98.EXE with the patch in (or out). Its own sites hold the original or the patch; the summary's
    routine has to hold 经验值显示修复's form or this patch's. Anything else stops everything."""
    out = bytearray(blob)
    for off, orig, fixed, _why in EXE_SITES + NEEDS_SITES:
        now = bytes(out[off:off + len(orig)])
        if now not in (orig, fixed):
            raise StoryFixError(f"{EXE} 第 {off:#x} 字节起既不是起点也不是改后的内容"
                                + ("（需要先启用经验值显示修复）" if (off, orig, fixed, _why) in NEEDS_SITES else ""))
        out[off:off + len(orig)] = orig if revert else fixed
    return bytes(out)


def main(argv):
    for off, orig, fixed, why in EXE_SITES + NEEDS_SITES:
        print(f"{EXE} {off:#07x} ({len(orig)} 字节) {why}")
        if len(orig) <= 24:
            print(f"    {orig.hex(' ')}\n -> {fixed.hex(' ')}")
    print(f"HOOK {CODE1_LABELS['hook']:04X} FACTORS {CODE1_LABELS['factors']:04X} "
          f"(到 {CODE1_AT + len(CODE1_BYTES):04X}，上限 {CODE1_END:04X})  "
          f"GAIN {CODE2_LABELS['gain']:04X} SHOWN {CODE2_LABELS['shown']:04X} MEMBER {CODE2_LABELS['member']:04X} "
          f"(到 {CODE2_AT + len(CODE2_BYTES):04X}，上限 {CODE2_END:04X})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
