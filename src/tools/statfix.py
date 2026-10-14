#!/usr/bin/env python3
"""The attribute and combat-formula defects of DDS98.EXE, and the edits that mend them (能力值修复).

    statfix.py [DDS98.EXE [ET0001.BIN]]     the state of every site and table entry

Each fix, what the game does without it, and what changes:

装备属性码   25CA:E116 adds an item's single-attribute code (1-0Bh: +1 to 直感 ... 命运) to the
             equipment bonus array, but indexes the array by the item buffer's byte +12h instead of
             the code it has just read. Only a gem carries the code in +12h; the decoder writes a
             constant 0Bh (命运) there for every accessory and nothing for a weapon or armour, so an
             accessory gives 命运 +1 whatever its code says, and a weapon or armour writes one word
             ahead of the array - the base 命运 of the record - on every recompute: 11 items raise
             their wearer's base 命运 by one per battle, level-up, change of equipment... and never give
             the attribute they are coded for. The index is now the code. The codes of four items are
             also set to what their descriptions name, and the six other attribute-coded accessories
             to 命运, which keeps what they gave (ET0001, below).
魔法命中     358E:28EC is handed the sword's magic-hit value (item +34h, 86 swords carry one) and never
             reads it. It now adds it.
魔法回避     358E:2926 is handed the accessory's evasion byte (+33h, which no accessory has) and never
             reads it; the equipment effects 37h/38h (magic evasion +4/+20: バリアーユニット) are
             summed into word 16 of the bonus buffer that 358E:296E then never passes on. 296E now
             passes word 16 and 2926 adds it.
防具特效36h  effect 36h adds the item's own hit value (+22h) to 剣命中 a second time; only three
             armour pieces carry it, and armour has no hit value, so it did nothing. It now adds the
             item's own evasion (+33h) to 剣回避 a second time.
会心武器     ov16:0000 takes the attacker's crit bonus (+23h) from the item numbered by its action's
             +182h: for a sword or gun skill that is the skill number, so the bonus came from an
             unrelated item; for a gun attack it is the bullet, which has none, so the crit value
             every gun carries (46 guns) never counted. It now goes to 25CA:crit_weapon, which takes
             the gun for a gun attack or gun-class skill and the sword for a sword attack or
             sword-class skill (25CA:912E); any other action keeps the item its +182h names.
攻击道具     25CA:995E sets up nothing for an item action, so ov16:2E22/3070/323E look the item's
             number up in the skill table (手榴弾 is 70, ムド) and take the magic hit a previous skill
             action left behind. Its call to 25CA:C1DA for the item now goes to 25CA:item_setup,
             which does what 25CA:91E0 does for a skill: the item's own accuracy, power, fall-off,
             element and added effect become the cached skill header, and the actor's magic hit is
             the action's.
状态道具     25CA:DFF2 takes a status item's status from buffer +11h, which no attack item fills;
             their status is in +17h. It now reads +17h, so 注連縄, 施餓鬼米, 蠱毒皿, 禁縛符,
             悪魔じゃらし, コーンフォーン and マジックＤＪ inflict what they are for.
剧情写能力值  command 23A (1603:A354, fields 19h-23h) writes an attribute's current value and 2DD
             (1603:D50E) then sets every base value to current - equipment - gems, which makes a
             clamp at 100 or a halving by a curse or ゾンビ permanent. 23A now moves the base value by
             the same amount as the current one (1603:set_attr), and 2DD no longer rewrites it. The
             scripts that write attributes (MS001F aptitude test, MS003F incense, MS0008 ウエンディー)
             all commit right after; the debug menu MS00AF writes without committing, so its edits
             now last.
倍率溢出     358E:2E0A multiplies in 16 bits and throws the high word away (cwd), so ×150% turns a
             value of 219 or more into 1 and ×50% one of 656 or more. The product now keeps its high
             word. (Nothing in the shipped data - skill or script - sets the +1C8h bits 23h-25h that
             call for it.)
速度下限     358E:1992 works a party unit's speed out as 4 sqrt(敏捷性) - armour / 4 / sqrt(体力), rounds it
             (1603:40CE) and holds it at 1 or more - with an unsigned compare (1A6E jae), so a negative
             speed (heavy armour on a weak character) passes as 65000-odd, and the battle clock (each
             tick takes 6 + U(0..255) x speed / 256 off the countdown) then lets that character act on
             every tick. The compare is now signed (jge).
附加异常溢出  ov16:0F6E (sword) and ov16:3B3A (gun) compare the added-effect power with the target's
             defence × U(0-40), a product up to 39960 that they read as signed, so a defence of 820 or
             more can turn it negative. They now read it unsigned. (The magic one, ov16:323E, draws
             U(0-30) and stays below 32768.)
灰           358E:3CE4 tells which status of a list a character has by the last one it finds, 0 for
             none - and 灰 is status 0, so it reads as none. Three checks hold 灰 in their list and use
             the answer only as yes or no (one end-of-battle test ANDs bit 0 over the enemies): 灰 死
             瀕死, whether a character is down (358E:3C88, 34 callers); the fourteen statuses that keep
             it from acting (3D36, 26); the seven that keep a member from a share of battle experience
             (3D7C, 8 - ov02 counts and pays with it). They now go through 358E:ash_check, which answers
             1 when 灰 is what the character has. Nothing in the shipped data gives 灰: 358E:35FC sets it
             only when the +1C8h timer 26h runs out (358E:A4D0), which only special effect 22h starts
             (358E:1534) and no skill carries; every other caller passes a status of 1 or more.
经验除零     ov02:0000 divides twice the battle's experience by 358E:4B7C(1), the members who take a
             share; with nobody to take one it divides by zero. It now asks 358E:share_count, which is
             4B7C(1), or 1 when that is 0 - the member loop then adds nothing to anyone.
程序经验     a skill that lands gives its caster 3 EXP in skill 2 (魔法) through 07B1:0534 (ov02:129E) - from
             ov16:2CE4 (one that strikes, 2D8B) and 25CA:AC9E (one that only inflicts a status, AD2B).
             2CE4 sends the sword and gun classes elsewhere and everything else this way, so the eight COMP
             programs (class 3, learn system 32) train 魔法 and COMP gains EXP only from negotiation. Both
             calls now go to 25CA:comp_exp, which turns skill 2 into 3 (COMP) when the caster's action
             (+181h) is a skill (4 or 6) whose class (+182h, read as 2CE4 reads it) is 3, and goes on to
             07B1:0534 with the stack as the caller left it. Programs still pass the magic barriers, which
             stop class 0 only (the user, 2026-10-05). The calls' segment words are relocated; they go
             from 07B1 to 25CA, and the loader and the overlay manager (0871:03B7-03D1) add the same base
             to every relocated word.

The routines go where nothing can reach: 25CA:E2E1-E410, the tail of an unused routine at 25CA:E294
(no near or far call into E291-E4C0, no pointer to its entries anywhere; E2E1-E410 holds none of its
relocated words), 1603:4288-4303, two unused helpers (no call, no pointer, no relocation), and
358E:639C-63F9, an unused near routine (no call, no pointer, no relocation, never traced).

tools/statfix_test.py runs every changed routine, original and fixed, on an emulated CPU with the
game's own tables. Every build carries the fix, with no switch.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm86 import assemble  # noqa: E402
from tables import chunks_bytes, chunks_of, string_table  # noqa: E402

NAME = "能力值修复"
FILE = "DDS98.EXE"
TABLE = "ET0001"
HDR = 0x3800                            # DDS98.EXE's MZ header; file offset = image address + HDR

SEG25 = 0x25CA0
CAVE25 = 0xE2E1                         # 25CA:E2E1-E410
CAVE25_ORIG = bytes.fromhex(
    "8ed8ebec908a0e18002aed8bc1483d28007603e9130103c0932effa700e39052e352e352e352e352e352e352e352e352"
    "e352e352e366e372e37ee38ae396e3a2e30ae40ae40ae40ae40ae40ae40ae40ae40ae40ae40ae40ae40ae40ae4aae3b4"
    "e3bee3c8e3d2e3dce3e6e3f0e3fae302e48b36180081e6ff0003f6c45e0626ff48fee9a400c55e06ff4f0aff4f12e998"
    "00c55e06ff4f0cff4f02e98c00c55e06ff0fff4f0ee9810090c55e06ff4f04ff4f08eb7590c55e06ff4f06ff4f10eb69"
    "90c55e06ff4f0aebcbc45e0626836f0204eb56c45e0626836f0603eb4cc45e0626ff4f08eb4390c45e0626836f0802eb"
    "38c45e062683470e0aeb2ec45e0626836f1202eb24c45e0626836f1204eb1ac45e062683471203eb10c45e0626ff0feb"
    "08c45e0626836f0e03161f5ec9ca0600")
OV16 = 0x62A00                          # file offset of overlay 16's code (ov16:0000)
OV2 = 0x54C00                           # file offset of overlay 2's code (ov02:0000)
SEG35 = 0x358E0
CAVE35 = 0x639C                         # 358E:639C-63F9
CAVE35_ORIG = bytes.fromhex(
    "c80400005756c41e0a2b268b5f0a8bf38c46fe26803cff743d8b7e0657ff76040656e883060bc07417ff76fe566a03e8"
    "9a060bc0750a8e46fe26807c028d740e8e46fe83c60826803cff75d0eb08268a44022ae4eb0233c05e5fc9c20400")
SEG16 = 0x16030
CAVE16 = 0x4288                         # 1603:4288-4303
CAVE16_ORIG = bytes.fromhex(
    "558bec8b4e088b5e0a3bcb7f0f8b56063bd37f152bda3bda7dfaeb0d3bcb7e098b560603da3bd97cfa8bc3c9ca060000"
    "c8080000837e10007d1a8b460a8b560c2b46121b56143b56107c277f1f3b460e7620eb188b46068b56082b46121b5614"
    "3b56107f0d7c053b460e730689460e8956108b460e8b5610c9ca1000")

ROUTINES25 = """
crit_weapon:                    ; far (attacker) -> dx:ax: an item record whose +23h is its crit bonus
    push bp
    mov bp, sp
    les bx, ptr [bp + 6]
    mov al, byte ptr es:[bx + 0x181]
    cmp al, 2
    je cw_gun                   ; a gun attack: +182h holds the bullet
    cmp al, 1
    je cw_sword
    mov ax, word ptr es:[bx + 0x182]
    or ax, ax
    jns cw_item                 ; not a skill: the item the action names, as before
    and ah, 0x7f                ; a skill: the weapon of its class
    push es
    push bx
    push ax
    push cs
    call 0x912e                 ; the skill's class
    pop bx
    pop es
    cmp ax, 2
    je cw_gun
cw_sword:
    mov ax, word ptr es:[bx + 0x1b6]
    jmp cw_item
cw_gun:
    mov ax, word ptr es:[bx + 0x1ba]
cw_item:
    shl ax, 5
    sar ax, 5                   ; the item number; an empty slot is 0 or -1
    or ax, ax
    jle cw_none
    push ax
    push cs
    call 0xc1da
    jmp cw_done
cw_none:
    mov dx, cs
    mov ax, cw_zero - 0x23
cw_done:
    pop bp
    retf 4
cw_zero:
    db 0

item_setup:                     ; far (item), es:bx = the actor -> dx:ax = the decoded item, as C1DA
    push bp
    mov bp, sp
    push si
    push di
    push word ptr es:[bx + 0x142]   ; [bp - 6]: the actor's magic hit
    push word ptr [bp + 6]
    push cs
    call 0xc1da
    push ss
    pop ds
    push dx
    push ax
    mov es, dx
    mov di, ax
    cmp byte ptr es:[di + 6], 4
    jne is_out                  ; only an attack item goes through the skill formulas
    push cs
    call 0x9278
    mov byte ptr [0x838e], 1    ; the cached skill header, class 0 like the records the item hit
    mov byte ptr [0x838f], 0
    mov bx, 0x8390
    lea si, [di + 7]            ; +02..+08 range and targets
    mov cx, 7
    call is_copy
    lea si, [di + 0x13]         ; +09..+0E accuracy, power, fall-off, element, effect, kind
    mov cx, 6
    call is_copy
    lea si, [di + 0x39]         ; +0F..+13 animation and scripts
    mov cx, 5
    call is_copy
    mov ax, word ptr [bp + 6]
    mov word ptr [0x29c8], ax
    mov al, byte ptr [0x8397]
    sub ah, ah
    mov word ptr [0x29ca], ax
    mov al, byte ptr [0x8398]
    mov word ptr [0x29cc], ax
    mov ax, word ptr [bp - 6]
    mov word ptr [0x29ce], ax
    mov word ptr [0x29d0], ax
    mov word ptr [0x29d2], 1
is_out:
    pop ax
    pop dx
    add sp, 2
    pop di
    pop si
    pop bp
    retf 2
is_copy:
    mov al, byte ptr es:[si]
    mov byte ptr [bx], al
    inc si
    inc bx
    loop is_copy
    ret

comp_exp:                       ; far, in place of 07B1:0534 (ov02:129E: amount, skill, unit; retf 8)
    sub sp, 4                   ; room for the thunk's address
    push bp
    mov bp, sp
    mov ax, cs
    sub ax, 0x25ca - 0x07b1
    mov word ptr [bp + 4], ax
    mov word ptr [bp + 2], 0x534
    cmp word ptr [bp + 0xc], 2  ; magic EXP
    jne ce_go
    les bx, ptr [bp + 0xe]      ; the caster
    mov al, byte ptr es:[bx + 0x181]
    and al, 0xfd
    cmp al, 4                   ; a skill action (4 or 6)
    jne ce_go
    mov ax, word ptr es:[bx + 0x182]
    add ax, ax
    sar ax, 1                   ; the skill, read as 2CE4 reads it
    push ax
    push cs
    call 0x912e                 ; its class
    cmp ax, 3
    jne ce_go
    mov word ptr [bp + 0xc], 3  ; a COMP program: COMP EXP
ce_go:
    pop bp
    retf                        ; on to 07B1:0534, the return address and arguments as the caller left them
"""

ROUTINES16 = """
set_attr:                       ; 23A, fields 19h-23h: si = record, [bp-6] its segment, di = field
    mov es, word ptr [bp - 6]
    mov bx, di
    shl bx, 1
    add bx, si
    mov ax, word ptr [bp - 4]
    mov cx, word ptr es:[bx + 0xae]
    mov word ptr es:[bx + 0xae], ax
    sub ax, cx
    add word ptr es:[bx + 0x56], ax
    jmp near 0xa718
"""

ROUTINES35 = """
ash_check:                      ; 3CE4's arguments and answer, but 灰 (code 0) in the list counts: 1
    push bp
    mov bp, sp
    push word ptr [bp + 0xc]
    push word ptr [bp + 0xa]
    push word ptr [bp + 8]
    push word ptr [bp + 6]
    push cs
    call 0x3ce4                 ; the last code of the list the character has - 0 for none, or for 灰
    or ax, ax
    jne ac_done
    les bx, ptr [bp + 6]
ac_scan:                        ; is 灰 in the list?
    mov cx, word ptr es:[bx]
    inc bx
    inc bx
    cmp cx, -1
    je ac_done
    jcxz ac_ash
    jmp ac_scan
ac_ash:
    push word ptr [bp + 0xc]
    push word ptr [bp + 0xa]
    push 0
    push cs
    call 0x35dc                 ; 1 when the character has 灰
ac_done:
    pop bp
    retf 8

share_count:                    ; 4B7C for ov02:0000, never 0: the divisor of each member's share
    push bp
    mov bp, sp
    push word ptr [bp + 6]
    push cs
    call 0x4b7c
    or ax, ax
    jne sc_done
    inc ax                      ; nobody takes a share: the member loop adds nothing whatever it is
sc_done:
    pop bp
    retf 2
"""

# ET0001 entries: (item, kind, offset of the attribute code in the entry, original, fixed, name)
TABLE_EDITS = (
    (212, 11, 0x16, 0x05, 0x03, "ロータスワンド"),       # 魔法の威力 -> 魔力
    (625, 17, 0x11, 0x06, 0x0A, "愛の翼"),               # 魅力を増す -> 魅力
    (714, 19, 0x09, 0x04, 0x02, "銀のヒランヤ"),         # 精神力を上昇させる -> 精神力
    (715, 19, 0x09, 0x06, 0x0B, "太宰府の御守り"),
    (716, 19, 0x09, 0x04, 0x0B, "銀の腕時計"),
    (719, 19, 0x09, 0x0A, 0x0B, "英美の指輪"),
    (720, 19, 0x09, 0x07, 0x0B, "ブレスレット"),
    (721, 19, 0x09, 0x07, 0x08, "琥珀のブローチ"),       # 素早さの魔力 -> 敏捷性
    (722, 19, 0x09, 0x07, 0x0B, "銀のイヤリング"),
    (723, 19, 0x09, 0x07, 0x0B, "紫水晶のペンダント"),
)


class StatFixError(ValueError):
    pass


def routines():
    """(25CA block, 1603 block, 358E block, {label: offset in its segment}), each padded with NOPs to
    the length of what it replaces."""
    code25, lab25 = assemble(ROUTINES25, org=CAVE25)
    code16, lab16 = assemble(ROUTINES16, org=CAVE16)
    code35, lab35 = assemble(ROUTINES35, org=CAVE35)
    if len(code25) > len(CAVE25_ORIG) or len(code16) > len(CAVE16_ORIG) or len(code35) > len(CAVE35_ORIG):
        raise StatFixError("例程超出可用空间")
    labels = dict(lab25)
    labels.update(lab16)
    labels.update(lab35)
    return (code25 + b"\x90" * (len(CAVE25_ORIG) - len(code25)),
            code16 + b"\x90" * (len(CAVE16_ORIG) - len(code16)),
            code35 + b"\x90" * (len(CAVE35_ORIG) - len(code35)), labels)


def _near(org, text):
    return assemble(text, org=org)[0]


def sites():
    """[(name, file offset, original bytes, fixed bytes)], every pair the same length."""
    b25, b16, b35, at = routines()
    crit = struct.pack("<H", at["crit_weapon"])
    return [
        ("装备属性码", HDR + SEG25 + 0xE1D4, bytes.fromhex("8b36180081e6ff00"),
         _near(0xE1D4, "mov si, cx\n" + "nop\n" * 6)),
        ("魔法命中", HDR + 0x358E0 + 0x28FE, bytes.fromhex("992bc2d1f8"),
         _near(0x28FE, "sar ax, 1\nadd ax, word ptr [bp + 6]")),
        ("魔法回避", HDR + 0x358E0 + 0x2938, bytes.fromhex("992bc2d1f8"),
         _near(0x2938, "sar ax, 1\nadd ax, word ptr [bp + 6]")),
        ("魔法回避来源", HDR + 0x358E0 + 0x2C87, bytes.fromhex("268b87b201"),
         _near(0x2C87, "push word ptr [bp - 0x16]\njmp 0x2c99")),
        ("防具特效36h", HDR + SEG25 + 0xE606, bytes.fromhex("8cc026a02800988e460a26014404eb3c"),
         bytes.fromhex("8cc026a03900988e460a26014408eb3c")),
        ("倍率溢出", HDR + 0x358E0 + 0x2E16, bytes.fromhex("99"), bytes.fromhex("90")),
        ("速度下限", HDR + 0x358E0 + 0x1A6E, bytes.fromhex("7303"), bytes.fromhex("7d03")),
        ("剑附加异常溢出", OV16 + 0x1058, bytes.fromhex("8bc799"), bytes.fromhex("31d290")),
        ("枪附加异常溢出", OV16 + 0x3C01, bytes.fromhex("8bc699"), bytes.fromhex("31d290")),
        ("会心武器", OV16 + 0x00E9,
         bytes.fromhex("c45e0a268b87820103c03d02007c1b268b87820103c0d1f8509adac1"),
         bytes.fromhex("c45e0a0653") + b"\x90" * 20 + b"\x9a" + crit),
        ("攻击道具", HDR + SEG25 + 0x9D1B, bytes.fromhex("e8bc24"),
         _near(0x9D1B, f"call {at['item_setup']:#x}")),
        ("状态道具", HDR + SEG25 + 0xE01B, bytes.fromhex("a0bf88"), bytes.fromhex("a0c588")),
        ("剧情写能力值", HDR + SEG16 + 0xA464,
         bytes.fromhex("8b46fc8bde8e46fa8bcf03cf03d9268987ae00e99e02"),
         _near(0xA464, f"jmp near {at['set_attr']:#x}\n" + "nop\n" * 19)),
        ("剧情提交", HDR + SEG16 + 0xD543, bytes.fromhex("0107"), bytes.fromhex("9090")),
        ("新增例程(25CA)", HDR + SEG25 + CAVE25, CAVE25_ORIG, b25),
        ("新增例程(1603)", HDR + SEG16 + CAVE16, CAVE16_ORIG, b16),
    ] + [
        # push ds / push <list> / nop / push cs / call 3CE4, the call now to ash_check
        (f"灰的状态检查({call - 0xF:04X})", HDR + SEG35 + call - 6,
         struct.pack("<BBHBB", 0x1E, 0x68, lst, 0x90, 0x0E) + _near(call, "call 0x3ce4"),
         struct.pack("<BBHBB", 0x1E, 0x68, lst, 0x90, 0x0E) + _near(call, f"call {at['ash_check']:#x}"))
        for call, lst in ((0x3C97, 0x23D0), (0x3D45, 0x23D8), (0x3D8B, 0x2426))
    ] + [
        ("分经验的人数", OV2 + 0x000B, bytes.fromhex("6a019a7c4b"),      # up to the relocated segment
         bytes.fromhex("6a019a") + struct.pack("<H", at["share_count"])),
    ] + [
        # push 2 / push 3 / lcall 07B1:0534, the call (offset and relocated segment) now to 25CA:comp_exp
        (f"程序经验({where})", at_file, bytes.fromhex("6a026a039a3405b107"),
         bytes.fromhex("6a026a039a") + struct.pack("<HH", at["comp_exp"], 0x25CA))
        for where, at_file in (("25CA:AD27", HDR + SEG25 + 0xAD27), ("ov16:2D87", OV16 + 0x2D87))
    ] + [
        ("新增例程(358E)", HDR + SEG35 + CAVE35, CAVE35_ORIG, b35),
    ]


def state(blob):
    """'orig' or 'fixed' - every site has to be in the same one."""
    seen = set()
    for name, at, orig, new in sites():
        if len(orig) != len(new):
            raise StatFixError(f"{name}：原版与修复后的长度不同")
        here = bytes(blob[at:at + len(orig)])
        if here == orig:
            seen.add("orig")
        elif here == new:
            seen.add("fixed")
        else:
            raise StatFixError(f"{name}（文件 0x{at:06X}）：{here[:16].hex(' ')} 既不是原版也不是修复后的字节")
    if len(seen) != 1:
        raise StatFixError(f"{FILE} 只改了一部分")
    return seen.pop()


def apply_to(blob, revert=False):
    """The executable with every site in the wanted state."""
    state(blob)
    out = bytearray(blob)
    for _name, at, orig, new in sites():
        want = orig if revert else new
        out[at:at + len(want)] = want
    return bytes(out)


def entry_state(entry, kind, off, orig, fixed, name):
    if len(entry) <= max(off, 4) or entry[4] != kind:
        raise StatFixError(f"{name}：这一条不是第 {kind} 类物品")
    if entry[off] == orig:
        return "orig"
    if entry[off] == fixed:
        return "fixed"
    raise StatFixError(f"{name}：属性码是 {entry[off]:#04x}，既不是原版也不是修复后的值")


def table_state(blob):
    (plain,) = chunks_of(blob)
    entries = string_table(plain)
    seen = {entry_state(entries[i], k, o, a, b, n) for i, k, o, a, b, n in TABLE_EDITS}
    if len(seen) != 1:
        raise StatFixError(f"{TABLE} 只改了一部分")
    return seen.pop()


def apply_table(blob, revert=False):
    """ET0001.BIN with every listed code in the wanted state: the bytes flipped where they stand and
    the chunk encrypted again (the file keeps its length)."""
    table_state(blob)
    (plain,) = chunks_of(blob)
    out = bytearray(plain)
    for i, _k, o, a, b, _n in TABLE_EDITS:
        at = struct.unpack_from("<H", plain, 2 + 2 * i)[0]
        out[at + o] = a if revert else b
    return chunks_bytes([bytes(out)])


def main(argv):
    exe = argv[0] if argv else os.path.join("files", "DDS98", FILE)
    et = argv[1] if len(argv) > 1 else os.path.join("files", "DDS98", TABLE + ".BIN")
    blob = open(exe, "rb").read()
    print(f"{exe}：{'已修复' if state(blob) == 'fixed' else '原版'}")
    for name, at, orig, new in sites():
        print(f"  {name}  文件 0x{at:06X}  {len(orig)} 字节")
        if len(orig) <= 16:
            print(f"      原 {orig.hex(' ')}\n      新 {new.hex(' ')}")
    tb = open(et, "rb").read()
    print(f"{et}：{'已修复' if table_state(tb) == 'fixed' else '原版'}")
    for i, k, o, a, b, n in TABLE_EDITS:
        print(f"  #{i} {n}（第 {k} 类，+{o:02X}）{a:#04x} -> {b:#04x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
