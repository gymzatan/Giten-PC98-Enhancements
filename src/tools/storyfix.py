#!/usr/bin/env python3
"""The dead ends in the game's own event logic, and the edits that mend them.

    storyfix.py [FILE…]     what each fix writes into files/DDS98

Event flags live in 32-byte bitmaps at DS:79E2 + bank*20h (1603:7F10); a new game fills them with
ones, so 1 means "has not happened yet" and progress clears bits. `019 bank bit` sets a flag,
`01A` clears it, `009`/`00B` branch on it, and `103`/`104` branch on a list of [bank][bit] pairs
(a bank byte with 80h means "clear" instead of "set"). A map object - a bridge, an NPC, an event
tile - is on the map only while its own flag is 0 (the walker at 3FBA:0014 skips a set one).

A fix is one of three kinds:
  Fix     swaps the operands of one command for others of the same length;
  Detour  needs commands the record has no room for: a command of the record becomes a jump to a
          block appended to the record (after the block of any fix before it in FIXES), the block
          does what the command did and what the fix adds, so nothing already in the record moves;
  EXE_SITES  bytes of DDS98.EXE's main image, same length.

樹海行方不明
    MS0015/0/04 ends the 中有 chapter: it clears 00:DA, which is the flag for "バールハダド has
    fallen" and nothing else reads or writes, and clears 00:C4, which means 樹海 is not standing in
    護国寺 just now. Only MS0015/0/01, his farewell on the way out of 中有, sets 00:C4 again, and
    護国寺's torii scene MS0061/0/06 asks for 00:C4 before it will show him at all. Leave 中有 by
    トラポート and that farewell never runs: 樹海 never appears, 00:C3 keeps the party out of 中有
    for good, and the only other place that sets 00:C4 is the ceremony that needs 樹海 first.
    The torii asks the wrong question. What it wants to know is whether バールハダド has fallen and
    the five 不動 are not yet finished - 00:DA and 00:BB - and, for the escort to 青の不動, whether
    that last 不動 still wants its eyes - 00:D3. Asking those leaves every flag's value exactly as
    the game sets it and mends the torii however the party left 中有.

後ろ歩きで抜ける (engine)
    A tile event runs only when a move puts the party on a cell other than the one the last tile
    check was made at (DS:2D02..0A, compared by main 3E90E, recorded by 3E95E when a move finds a
    change). When an event sends the party back - the engine's push-back to the cell it came from
    (ov5 0434 -> 3DF4A) or a warp of the script's own (204, as the forward base's guard does) - that
    record still holds the event cell, so a step straight back into it is not a change and nothing
    runs: walking backwards (which needs no turn, and a turn would have re-checked) passes 旧新橋
    at any moon and the guard of ペンタグランマ前線基地. The move routine now records the cell it
    steps off at the start of every step: main 3DDF4 calls 3E950 instead of 3DF22, and 3E950 - code
    nothing calls or points at - is rewritten to save the cell as 3DF22 does and run on into 3E95E.
    So every step onto an event cell is a change, however the party got to where it stepped from.

旧新橋の南で詰む
    With the step above passable, a party that has walked backwards past 旧新橋 (MS0026/0/21) away
    from a new moon ends at the rubble that closes the line to 虎ノ門; coming back, the platform's
    push-back sends it south again, to the cell it came from, and a save made there cannot leave
    except by that same trick. Every ending of the platform away from a new moon (three with the
    music back to 0C, and the branch taken when the wreck is gone, which skips that music) now goes
    through a block that, when the party came from the south (214 on the came-from direction 2),
    warps it to the cell north of the platform facing 銀座 - where the push-back leaves a party
    coming from 銀座.

浄化作戦の再演
    The sickroom of 初台 (M0082 section 8 r6 c10, MS0051/0/06) holds the one meeting that sends the
    party down to Ｂ８Ｆ: it runs while 09:2D is 0 and sets it (@075D). In the escape the food store
    of Ｂ６Ｆ uses 09:2D for "the rations are taken" (MS001C/0/00, and the guard robot of MS001B/0/01
    wants it clear), and the sickroom never looks at the escape flag 00:01: stepping in after the
    food store replays the meeting with the dead heroine and Nishino in it, sets 09:2D so the robot
    asks for food again, and with five rations or more takes them and puts both back in the party.
    The gate at @001D, whose two terms cannot hold where it stands, now asks for 00:01 = 0 and then
    goes to the record's own 「誰もいない」.

和平交渉の先走り
    The colosseum's bedchamber door, MS0012/0/04, starts the peace talks with タケミナカタ as soon as
    00:B2 says ヒルコ has been bombed. The talks are アマテラス's proposal carried by ヤマトタケル,
    which the party only has once it has accepted it (MS0015/0/09 clears 00:F1). Back at 有明
    before that - by トラポート from the バール教団 branch after デカラビア - the talks run with
    neither, clear 00:F2, and the real ones never happen. The door now also needs 00:F1 clear; before
    that the event ends and the engine walks the party back out.

使者の橋
    The Rainbow Bridge stands while 01:0D is 0. オセ's bargain in 黄泉 (MS000F/0/00) first clears
    it, the bombing of ヒルコ (MS0012/0/04 @178C) sets it, and accepting アマテラス's proposal
    (MS0015/0/09, which makes the party her envoys to 有明) clears it again: the bridge the
    bridgehead's welcome to the envoys (MS0061/0/0E) sends them over. Nothing makes the proposal wait
    for the bombing - a party with the 八咫鏡, a sword that cuts the 岩戸's rope and a demon that
    moves the rock can accept it first - and then the bombing takes the bridge away for good: both
    of its endings leave 有明 (into the light to the バール教団 branch, onto the bomb to 黄泉), the
    only ferry (the mutant of MS0012/0/0A) carries a party off the island and not onto it, and the
    talks the envoys were sent for can never be reached. The bombing now leaves the bridge standing
    for a party that is already the envoy (00:F1 clear).

原宿帰りの重傷者
    Back from 原宿 with someone down, the return scene (MS001A/0/02, or 08-0C when it is 西野)
    sends the party into 初台's clinic (MS0052/0/02) the way a collapse does (MS001A/0/06): it
    clears 09:77, so the clinic takes its emergency side and the doctor's plain revival (104C),
    which ends where it stands. The scene written for this return - the doctor's 「ふぅ‥‥」, which
    heals, clears 09:66 and sends the party on to 管理部 (a warp to section 10 r6 c6 and a step) - is
    on the walk-in side, and the return has locked the ways to 管理部 (09:1A, 01:22): the party is
    left with nothing to do but walk into the clinic again, which nothing hints at. The emergency
    side's jump to the doctor now goes through a block: with the summons out (09:21 clear), that
    scene not yet played (09:66 set) and a party that went (09:61 set), it clears 01:4F as every
    revival does and joins the walk-in side at the doctor's portrait; any other emergency goes to
    104C as before.

園田が残る
    爆心地's colosseum (M0088) parts the party from 園田 and 泪 at its receptionist (MS0062/0/03),
    but the duel (MS0062/0/06) asks only 00:1C, which the full moon at HALC clears long before.
    Section 1 has a save terminal past the receptionist and トラポート goes back to the last save,
    so a party that saved there reaches the arena without her, fights アドニス three strong, and
    nothing afterwards takes 園田 away. The duel now also asks whether 園田 is still in the party
    (1A4) - he leaves it at the receptionist and no script brings him back - and while he is, the
    arena is empty, as it is before and after the chapter. (Not the receptionist's own flag 09:5F:
    loading any other map refills bank 9 with 1s (358E:597C), and a party may leave between her
    and the duel.) A party that came in that way still has to pass the guide (MS0062/0/05) on its
    way out, and she sets 00:86, which dismisses the receptionist too - the duel could never happen
    then. The guide now asks the same question first, and while 園田 is along she sends the party
    out to 爆心地's door on the field (205, as MS0060/0/06 does when it sends the party to the
    duel), to come in past the receptionist.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ddsvm import tokenize  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98")
EXE = "DDS98.EXE"
FILLER = b"\x1f\xe0"        # command 1E0: its handler is the dispatcher's plain exit - no operands


class StoryFixError(ValueError):
    pass


def rel_word(field, target):
    """The operand of a branch whose word sits at `field`: the target counts from after the word."""
    return struct.pack("<H", (target - (field + 2)) & 0xFFFF)


def jump(at, target):
    """018 (jump) placed at `at`."""
    return b"\x18" + rel_word(at + 1, target)


class Fix:
    """One command whose operands the fix rewrites, found by what it holds rather than by where it
    sits: a record's offsets move when its text is translated, its operands do not.

    code is the command and tail the operand bytes at the end of it that name the flags; a fix that
    changes the command as well gives fixed_code, which both sites that need it spell in one byte
    (page 0). Original and fixed are the same length, so the record keeps its size and every branch
    in the file still lands where it did.
    """

    def __init__(self, stem, chunk, rid, code, tail, fixed_tail, fixed_code=None, why=""):
        self.stem, self.chunk, self.rid, self.code = stem, chunk, rid, code
        self.fixed_code = code if fixed_code is None else fixed_code
        self.tail, self.fixed_tail = tail, fixed_tail
        self.why = why
        if len(tail) != len(fixed_tail):
            raise StoryFixError(f"{self}: 原始与修复后的操作数长度不同")
        if self.fixed_code != code and max(code, self.fixed_code) > 0xFF:
            raise StoryFixError(f"{self}: 改写命令码只支持单字节命令")

    def __str__(self):
        return f"{self.stem}/{self.chunk}/{self.rid:02X} {self.code:03X}"

    def edits(self, payload, _end):
        """([(offset, original bytes, fixed bytes)], appended bytes) for the record as the game ships
        it (a Detour's block goes at `_end`; this appends nothing). The command has to be there
        exactly once; anything else means the script is not the one this fix was written against and
        nothing may be written."""
        hits = []
        for t in tokenize(payload):
            if t.kind == "text":
                continue
            at = t.end - len(self.tail)
            if t.code == self.code and payload[at:t.end] == self.tail:
                hits.append((t.start, at))
        if len(hits) != 1:
            raise StoryFixError(f"{self}: 这条命令在记录里出现 {len(hits)} 次，应为 1 次")
        start, at = hits[0]
        sites = [(at, self.tail, self.fixed_tail)]
        if self.fixed_code != self.code:
            sites.insert(0, (start, bytes([self.code]), bytes([self.fixed_code])))
        return sites, b""


class Detour:
    """A fix that adds commands: see the module notes. edits() gets the record as the game ships it
    and the offset its block will start at, and returns the same-length changes and the block; the
    block's branches are worked out from where it will sit, so the record's own layout - Japanese or
    translated - is all it needs."""

    def __init__(self, stem, chunk, rid, why):
        self.stem, self.chunk, self.rid, self.why = stem, chunk, rid, why

    def __str__(self):
        return f"{self.stem}/{self.chunk}/{self.rid:02X}"

    def commands(self, payload):
        return [t for t in tokenize(payload) if t.kind != "text"]

    def one(self, found, what):
        if len(found) != 1:
            raise StoryFixError(f"{self}: {what}在记录里出现 {len(found)} 次，应为 1 次")
        return found[0]


class OldShinbashi(Detour):
    """旧新橋 away from a new moon: a party that came from the south is put north of the platform."""

    MUSIC = bytes.fromhex("1f c5 00 0c")            # back to the line's own music
    WARP = bytes.fromhex("1e 04 00 41 00 01 00 00 00 01 00 00")   # 銀座線 section 1 r0 c1, facing N

    def __init__(self):
        super().__init__("MS0026", 0, 0x21, "地铁新桥站旧站台：从南边走进来的队伍放到北边、面朝银座")

    def edits(self, payload, at):
        cmds = self.commands(payload)
        ends = [(t, n) for t, n in zip(cmds, cmds[1:])
                if payload[t.start:t.end] == self.MUSIC and n.code == 0x000 and n.start == t.end]
        if len(ends) != 3:
            raise StoryFixError(f"{self}: 「音乐 0C + 结束」出现 {len(ends)} 次，应为 3 次")
        gone = self.one([t for t in cmds if t.code == 0x00B and payload[t.end - 2:t.end] == b"\x01\x61"],
                        "残骸已取走的分支（00B 01:61）")
        field, target = gone.rel[0]
        if target not in {n.start for _t, n in ends}:
            raise StoryFixError(f"{self}: 残骸已取走的分支没有落在任何一处结束上")
        end_other = at + 4 + 6 + len(self.WARP) + 1
        block = (self.MUSIC
                 + b"\x1e\x14" + rel_word(at + 6, end_other) + b"\x00\x02"   # 214: came from the south?
                 + self.WARP + b"\x00"                                       # yes: north of it, end
                 + b"\x00")                                                  # no: end (push-back)
        sites = [(t.start, payload[t.start:n.end], jump(t.start, at) + FILLER) for t, n in ends]
        # that branch skipped the music as well (the wreck's own music never started), so it joins
        # the block after it
        sites.append((field, payload[field:field + 2], rel_word(field, at + len(self.MUSIC))))
        return sites, block


class ColosseumProposal(Detour):
    """The bedchamber door starts the peace talks only once アマテラス's proposal is accepted."""

    def __init__(self):
        super().__init__("MS0012", 0, 0x04, "临海竞技场：接受天照大神的提议之后才开始和谈")

    def edits(self, payload, at):
        first = self.commands(payload)[0]
        if first.start != 0 or first.code != 0x009 or payload[first.end - 2:first.end] != b"\x00\xb2":
            raise StoryFixError(f"{self}: 记录开头不是 009 00:B2")
        (_field, bombing), = first.rel
        block = (b"\x09" + rel_word(at + 1, bombing) + b"\x00\xb2"            # not bombed yet: as before
                 + b"\x09" + rel_word(at + 6, at + 13) + b"\x00\xf1"          # no proposal: end
                 + jump(at + 10, first.end)                                  # the talks
                 + b"\x00")
        return [(0, payload[:first.end], jump(0, at) + FILLER)], block


class EnvoysBridge(Detour):
    """The bombing takes the Rainbow Bridge away only from a party that is not yet アマテラス's envoy."""

    def __init__(self):
        super().__init__("MS0012", 0, 0x04, "临海竞技场：已接受天照大神提议的队伍，蛭子被炸后彩虹大桥不消失")

    def edits(self, payload, at):
        cmds = self.commands(payload)
        # the 019 01:0D right after ヒルコ's last cry (172 takes his picture down); in a mended record
        # that command is a jump and the block's own 019 follows a 00B, so a second pass finds none
        gone = self.one([t for p, t in zip(cmds, cmds[1:])
                         if payload[t.start:t.end] == b"\x19\x01\x0d" and p.code == 0x172],
                        "蛭子倒下后的 019 01:0D")
        block = (b"\x0b" + rel_word(at + 1, at + 8) + b"\x00\xf1"     # already the envoy: it stays
                 + payload[gone.start:gone.end]                      # otherwise it goes with ヒルコ
                 + jump(at + 8, gone.end))
        return [(gone.start, payload[gone.start:gone.end], jump(gone.start, at))], block


class HarajukuReturn(Detour):
    """初台's clinic gives a party back from 原宿 with its wounded the scene written for it."""

    def __init__(self):
        super().__init__("MS0052", 0, 0x02, "原宿归来有人重伤：诊疗室演为此写的那一幕，再去管理部")

    def edits(self, payload, at):
        cmds = self.commands(payload)
        fork = self.one([t for t in cmds if t.code == 0x104
                         and payload[t.end - 6:t.end] == bytes.fromhex("00 09 09 18 ff ff")],
                        "急救一侧的 104 [00:09 09:18]")
        (_f, doctor), = fork.rel
        to_revival = self.one([t for t in cmds if t.start == doctor and t.code == 0x018], "转去医生急救的 018")
        (_f, revival), = to_revival.rel
        if not any(t.start == revival and t.code == 0x170 for t in cmds):
            raise StoryFixError(f"{self}: 那个 018 没有转到医生急救的开头（显示医生的 170）")
        call = self.one([t for t in cmds if payload[t.start:t.end] == bytes.fromhex("0d 55 08")],
                        "进门一侧医生分支开头的 00D 55:08")
        block = (b"\x09" + rel_word(at + 1, revival) + b"\x09\x21"           # no summons out: as before
                 + b"\x1f\x04" + rel_word(at + 7, at + 18) + bytes.fromhex("09 66 09 61 ff ff")
                 + jump(at + 15, revival)                                   # scene played, or stayed home
                 + b"\x1a\x01\x4f"                                          # what every revival does
                 + jump(at + 21, call.end))                                 # the doctor's portrait, ふぅ
        return [(to_revival.start, payload[to_revival.start:to_revival.end], jump(to_revival.start, at))], block


SONODA = b"\x00\x04\xf5"      # the party member 園田, as 13E/13F/1A3/1A4 name him


class AdonisDuel(Detour):
    """The duel at 爆心地 runs only once the receptionist has parted 園田 from the party."""

    def __init__(self):
        super().__init__("MS0062", 0, 0x06, "爆心地竞技场：园田还在队里（没经过前台）时不开始决斗")

    def edits(self, payload, at):
        first = self.commands(payload)[0]
        if first.start != 0 or first.code != 0x009 or payload[first.end - 2:first.end] != b"\x00\x1c":
            raise StoryFixError(f"{self}: 记录开头不是 009 00:1C")
        (_field, empty), = first.rel
        block = (b"\x09" + rel_word(at + 1, empty) + b"\x00\x1c"         # not the duel's night: as before
                 + b"\x1f\xa4" + rel_word(at + 7, empty) + SONODA         # 園田 still along: nobody there
                 + jump(at + 12, first.end))                              # the duel
        return [(0, payload[:first.end], jump(0, at) + FILLER)], block


class GroundZeroGuide(Detour):
    """The guide on the colosseum floor sends back out a party the receptionist has not seen."""

    WARP_OUT = bytes.fromhex("1e 05 00 54 00 57 00 04")     # 205: the field, at 爆心地's door

    def __init__(self):
        super().__init__("MS0062", 0, 0x05, "爆心地：园田还在队里（没经过前台）时，带路的女恶魔把队伍送回门外")

    def edits(self, payload, at):
        first = self.commands(payload)[0]
        if first.start != 0 or payload[:first.end] != b"\x19\x00\x86":
            raise StoryFixError(f"{self}: 记录开头不是 019 00:86")
        block = (b"\x1f\xa3" + rel_word(at + 2, at + 17) + SONODA         # 園田 parted: as before
                 + self.WARP_OUT + b"\x1f\xe5"                            # otherwise out to the field, end
                 + payload[:first.end] + jump(at + 20, first.end))
        return [(0, payload[:first.end], jump(0, at))], block


FIXES = [
    # 樹海行方不明: the torii shows 樹海 once バールハダド has fallen (00:DA) and the five 不動 are
    # still unfinished (00:BB), rather than asking whether he walked out of 中有 with the party.
    Fix("MS0061", 0, 0x06, 0x104, b"\x00\xc4\x00\xbb\xff\xff", b"\x80\xda\x00\xbb\xff\xff",
        why="护国寺鸟居改看巴力哈达德是否已被打倒"),
    # and the escort to 青の不動 is over when that 不動 has its eyes (00:D3), not when 00:C4 says
    # 樹海 has left 護国寺 - which after トラポート it never stops saying.
    Fix("MS0061", 0, 0x06, 0x103, b"\x00\xcf\x80\xbb\x80\xc4\xff\xff",
        b"\x00\xcf\x80\xbb\x80\xd3\xff\xff",
        why="带路结束条件改看青之不动是否已点睛"),
    # 浄化作戦の再演: a list gate whose two terms can never hold where it stands (09:29 = 0,
    # 09:18 = 1) is made to ask for the escape instead (00:01 = 0) and to go to the record's own
    # 「誰もいない」 (0005, among the commands before the first text, so the branch word is the same
    # in any build).
    Fix("MS0051", 0, 0x06, 0x103, b"\x09\x00\x89\x29\x09\x18\xff\xff",
        b"\xe4\xff\x89\x29\x80\x01\xff\xff",
        why="逃离初台时病房不再重演Ｂ８Ｆ作战会议"),
    OldShinbashi(),
    ColosseumProposal(),
    EnvoysBridge(),
    HarajukuReturn(),
    AdonisDuel(),
    GroundZeroGuide(),
]

# DDS98.EXE, as file offsets: the same in the Japanese executable and in this build's, whose own
# changes (tools/exefix.py, tools/exekeys.py) lie elsewhere.
EXE_SITES = [
    # main 3DDF4: the step's call that saves the cell stepped off (3DF22) goes to 3E950 instead
    (0x415F4, bytes.fromhex("e8 2b 01"), bytes.fromhex("e8 59 0b"),
     "每走一步先记下出发格为「已检查」"),
    # main 3E950 (no caller, no pointer to it anywhere): saves the cell as 3DF22 does, then runs on
    # into 3E95E, which records it as the cell last checked, and returns from there
    (0x42150, bytes.fromhex("6a ff 6a ff 6a ff 6a ff 6a ff e8 8b ff cb"),
     bytes.fromhex("a1 54 99 a3 54 2c a1 56 99 a3 56 2c 90 90"),
     "记录出发格的例程"),
]


def by_file():
    out = {}
    for f in FIXES:
        out.setdefault(f.stem, []).append(f)
    return out


def record_edits(parsed, fixes):
    """{(chunk, record position): (sites, appended bytes)} for a parsed file as the game ships it.
    The sites of a record may come from several fixes, and so may its appended bytes: each block
    goes after the ones before it."""
    out = {}
    for f in fixes:
        positions = [pos for pos, r in enumerate(parsed[f.chunk]) if r.rid == f.rid]
        if len(positions) != 1:
            raise StoryFixError(f"{f}: 块 {f.chunk} 里 id 为 {f.rid:02X} 的记录有 {len(positions)} 条")
        key = (f.chunk, positions[0])
        payload = parsed[f.chunk][positions[0]].payload
        have_sites, have_block = out.get(key, ([], b""))
        sites, block = f.edits(payload, len(payload) + len(have_block))
        out[key] = (have_sites + sites, have_block + block)
    for (ci, pos), (sites, _block) in out.items():
        spans = sorted((off, off + len(a)) for off, a, _b in sites)
        if any(b0 < a1 for (_a0, a1), (b0, _b1) in zip(spans, spans[1:])):
            raise StoryFixError(f"块 {ci} 记录 {pos}: 两处修复改到了同一些字节")
    return out


def mend(payload, sites, block):
    """The record with the fix in: every site's bytes replaced, the block appended."""
    out = bytearray(payload)
    for off, orig, fixed in sites:
        if bytes(out[off:off + len(orig)]) != orig:
            raise StoryFixError(f"第 {off} 字节起不是原版的 {orig.hex(' ')}")
        out[off:off + len(orig)] = fixed
    return bytes(out) + block


def apply_to(parsed, fixes):
    """Mend a parsed file as the game ships it. -> the edits made, as record_edits() gives them."""
    edits = record_edits(parsed, fixes)
    for (ci, pos), (sites, block) in edits.items():
        parsed[ci][pos].payload = mend(parsed[ci][pos].payload, sites, block)
    return edits


def mend_exe(blob, revert=False):
    """DDS98.EXE with the engine fixes in (or out). A site holding neither form stops everything."""
    out = bytearray(blob)
    for off, orig, fixed, _why in EXE_SITES:
        now = bytes(out[off:off + len(orig)])
        if now not in (orig, fixed):
            raise StoryFixError(f"{EXE} 第 {off:#x} 字节起既不是原版也不是修复后的内容")
        out[off:off + len(orig)] = orig if revert else fixed
    return bytes(out)


def main(argv):
    import ddsfile
    wanted = [a.upper() for a in argv]
    for stem, fixes in sorted(by_file().items()):
        if wanted and stem not in wanted:
            continue
        parsed = ddsfile.parse(open(os.path.join(SRC, stem + ".BIN"), "rb").read())
        added = {}
        for f in fixes:
            pos = [p for p, r in enumerate(parsed[f.chunk]) if r.rid == f.rid][0]
            payload = parsed[f.chunk][pos].payload
            sites, block = f.edits(payload, len(payload) + added.get((f.chunk, pos), 0))
            added[(f.chunk, pos)] = added.get((f.chunk, pos), 0) + len(block)
            print(f"{f}  {f.why}")
            for off, orig, fixed in sites:
                print(f"    @{off:04X} {orig.hex(' ')} -> {fixed.hex(' ')}")
            if block:
                print(f"    追加 {len(block)} 字节：{block.hex(' ')}")
    if not wanted or EXE in wanted:
        for off, orig, fixed, why in EXE_SITES:
            print(f"{EXE} @{off:#x}  {why}\n    {orig.hex(' ')} -> {fixed.hex(' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
