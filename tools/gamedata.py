#!/usr/bin/env python3
"""What the editor knows: every editable record of a disk image, the tables their numbers point into,
and the edit table laid on top.

Three things are told apart for every field:

  原始    what the game shipped, out of tools/gamebase.json, which the editor carries with it — so
          the names in both languages, the line the game prints about a record, and the original
          numbers are the same whichever image is opened, and an image somebody has already changed
          is still read against what the game shipped
  镜像    what the opened image holds right now
  改后    what the edit table wants written

The box the user types in shows the last of those, and where the table says nothing about a field it
shows what the image holds, so an untouched editor writes nothing. An entry is kept as the pair
(shipped value, wanted value) whenever the wanted value is not both the shipped one and the one the
image already holds — so putting a field back to the game's own number in an image that carries a
change is itself something to write, not the absence of a change.

An image is only needed to write one. With none open the editor still holds every record, every name
and every number the game shipped, and a table can be made, saved and opened; the boxes then show
what the table asks for, and the shipped value where it asks for nothing.
"""
import base64
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balance  # noqa: E402
import etfields  # noqa: E402
import gameimage  # noqa: E402
import p2fields  # noqa: E402
import records  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)


def shipped(name, source):
    """A file that travels with the program: out of the bundle when packaged, out of the tree here."""
    base = getattr(sys, "_MEIPASS", None)
    return os.path.join(base, name) if base else source


def app_dir():
    """Where the program lives, and where an edit table is saved unless told otherwise."""
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else WORK


ENUMS_PATH = shipped("p2enums.json", os.path.join(HERE, "p2enums.json"))
MOON_PATH = shipped("moon.json", os.path.join(HERE, "moon.json"))
GAMEBASE_PATH = shipped("gamebase.json", os.path.join(HERE, "gamebase.json"))
# the editor is built once per edition (tools/mkeditor.py packs edition.json into each exe): what its title adds,
# in the two languages, and how its moon graph turns an ET0003 value v into the day's damage multiplier - 2v/100 in
# 原版 (25CA:8E68), √(v/50) in 再平衡版 (tools/rebalance.py W9)
EDITIONS = {"main": ("", ""), "rebalance": ("（再平衡版）", "（再平衡版）")}
# both editions' editors and tables sit in one folder of the release (the user, 2026-10-07: 「全部放根目录，加后缀
# 区分」), so each exe reads the table named after its edition; run from the tree, the work table
TABLE_NAMES = {"main": "balance（原版）.json", "rebalance": "balance（再平衡版）.json"}


def default_table(edition):
    """The edit table the editor of this edition opens by default."""
    if getattr(sys, "frozen", False):
        return os.path.join(app_dir(), TABLE_NAMES[edition])
    return balance.BALANCE_PATH


MOON_MULT = {"main": lambda v: 2 * v / 100, "rebalance": lambda v: math.sqrt(v / 50)}
MOON_DAYS = 28
# the guide's five words for a day's strength, and the ET0003 values each covers; the boundaries sit in the
# gaps between the table's values (tools/mkmoon.py)
MOON_LEVELS = [("弱", "弱い"), ("普通", "普通"), ("稍强", "やや強い"),
               ("强", "強い"), ("很强", "かなり強い")]
MOON_BANDS = [(10, 42.5), (42.5, 52.5), (52.5, 72.5), (72.5, 105), (105, 200)]
# the graph's scale: the 原版 multipliers of the table's smallest and largest value, in both editions, so the
# 再平衡版's flatter curve shows as flatter
MOON_MIN, MOON_MAX = 0.2, 4.0


def packed_edition():
    """The edition the running exe was built for."""
    edition = json.load(open(os.path.join(sys._MEIPASS, "edition.json"), encoding="utf-8"))["edition"]
    if edition not in EDITIONS:
        raise ValueError(f"edition.json: {edition}")
    return edition

# how a field is shown and typed in
INT, RESIST, SKILL, ITEM, LEARN, TALK, AFFINITY, RATE, MOON, RAW = (
    "int", "resist", "skill", "item", "learn", "talk", "affinity", "rate", "moon", "raw")

DEMON, SKILLS, GEAR = "demon", "skill", "gear"
SOURCES = [(DEMON, "恶魔", "悪魔"), (SKILLS, "魔法・特技", "魔法・特技"),
           (GEAR, "武器・防具・道具", "武器・防具・アイテム")]


def _demon_fields():
    out = [("基本", "基本", "等级", "レベル", 0x47, 1, INT),
           ("基本", "基本", "ＨＰ", "ＨＰ", 0x0C, 2, INT),
           ("基本", "基本", "ＭＰ", "ＭＰ", 0x0E, 2, INT),
           ("基本", "基本", "ＣＰ", "ＣＰ", 0x57, 1, INT),
           ("基本", "基本", "ＥＸＰ", "ＥＸＰ", 0x00, 4, INT),
           ("基本", "基本", "魔货", "魔貨", 0x04, 4, INT),
           ("基本", "基本", "ＭＡＧ", "ＭＡＧ", 0x08, 4, INT),
           ("基本", "基本", "月龄对应", "月齢対応", 0x58, 1, MOON),
           ("基本", "基本", "取得率", "取得率", 0x67, 1, RATE),
           ("基本", "基本", "会话类型", "会話タイプ", 0x73, 1, TALK),
           ("基本", "基本", "装备相性", "装備相性", p2fields.AFFINITY_AT, 1, AFFINITY),
           ("基本", "基本", "速度", "速度", p2fields.SPEED_AT, 1, INT),
           ("基本", "基本", "行动模式", "行動パターン", p2fields.AI_ROW_AT, 1, "named:行動パターン")]
    stats_ja = ["直感", "精神力", "魔力", "知力", "加護", "強さ", "体力",
                "敏捷性", "器用さ", "魅力", "命運"]
    stats = [f for f in p2fields.FIELDS if 0x4C <= f[0] <= 0x56]
    for i, (off, _w, zh) in enumerate(stats):
        out.append(("能力", "能力", zh, stats_ja[i], off, 1, INT))
    resist_ja = ["直接", "ガン", "火炎", "氷結", "衝撃", "電撃", "破魔", "魔力", "呪殺", "神経"]
    for i, zh in enumerate(p2fields.RESIST):
        out.append(("耐性", "耐性", zh, resist_ja[i], p2fields.RESIST_AT + i, 1, RESIST))
    for i in range(p2fields.SKILL_SLOTS):
        if i < p2fields.HELD_SKILLS:
            zh = ja = f"所持魔法 {i + 1}"
        else:
            zh, ja = f"敌专用 {i - p2fields.HELD_SKILLS + 1}", f"敵専用 {i - p2fields.HELD_SKILLS + 1}"
        out.append(("技能", "技能", zh, ja, p2fields.SKILLS_AT + 2 * i, 2, SKILL))
    for i in range(p2fields.LEARN_SLOTS):
        out.append(("技能", "技能", f"习得系统 {i + 1}", f"習得系統 {i + 1}",
                    p2fields.LEARN_AT + i, 1, LEARN))
    equip_ja = {"头": "頭", "体": "体", "腕": "腕", "脚": "脚",
                "饰": "飾", "剑": "剣", "枪": "銃", "弹": "弾"}
    for off, zh in p2fields.EQUIP_AT:
        out.append(("装备", "装備", zh, equip_ja[zh], off, 2, ITEM))
    out.append(("装备", "装備", "掉落道具", "アイテム", p2fields.DROP_AT, 2, ITEM))
    for off in p2fields.UNKNOWN:
        out.append(("未知", "不明", f"0x{off:02X}", f"0x{off:02X}", off, 1, RAW))
    return out


DEMON_FIELDS = _demon_fields()

# The ET fields whose byte stands for a word the guide spells out. They keep a plain number box, with
# the word beside it, because several of them give the same word to more than one value — a drop-down
# of words could not put such a value back.
ET_NAMED = {"系統": "系統", "使用状況": "使用状況", "範囲": "範囲",
            "リストアップ対象": "リストアップ対象", "体数": "体数",
            "相性": "相性", "追加効果": "追加効果"}


def et_kind(ja_label):
    if ja_label == "発動魔法／特技":
        return SKILL
    if ja_label == "修得系統":
        return LEARN
    if ja_label in ET_NAMED:
        return f"named:{ET_NAMED[ja_label]}"
    return INT


class Entry:
    __slots__ = ("target", "jp", "zh", "note", "source", "desc", "race", "deity")

    def __init__(self, target, jp, zh, note, source, desc=("", ""),
                 race=("", ""), deity=("", "")):
        self.target, self.jp, self.zh, self.note, self.source = target, jp, zh, note, source
        self.desc = desc                  # the game's own line about it, (japanese, chinese)
        self.race, self.deity = race, deity   # a demon's 種族 and 神族, shown but not editable


class Shipped:
    """One record as the editor carries it: what it is called, what the game says about it, its
    種族 and 神族 where it has them, and the numbers it shipped with."""
    __slots__ = ("jp", "zh", "desc", "base", "race", "deity")

    def __init__(self, r):
        self.jp, self.zh = r["jp"], r["zh"]
        self.desc = (r.get("jp_desc", ""), r.get("zh_desc", ""))
        self.base = base64.b64decode(r["base"])
        self.race = tuple(r.get("race", ("", "")))
        self.deity = tuple(r.get("deity", ("", "")))


def gamebase(path=GAMEBASE_PATH):
    """{target: Shipped}."""
    return {target: Shipped(r)
            for target, r in json.load(open(path, encoding="utf-8"))["records"].items()}


class Game:
    def __init__(self, image=None, table_path=None, edition="main"):
        """edition: which build of the editor this is (EDITIONS); it decides only the moon multipliers."""
        if edition not in EDITIONS:
            raise ValueError(f"edition: {edition}")
        self.edition = edition
        self.image = image if image is None or isinstance(image, gameimage.GameImage) \
            else gameimage.GameImage(image)
        self.base = gamebase()
        self.skills = self._named("ET0004")
        self.items = self._named("ET0001")
        self.enums = json.load(open(ENUMS_PATH, encoding="utf-8"))
        self.moon = json.load(open(MOON_PATH, encoding="utf-8"))["rows"]
        self.path = table_path or default_table(edition)
        self.table = balance.load(self.path)
        self.entries = self._entries()          # the level a demon is listed with is an edited value

    # ---- the records -------------------------------------------------------
    def _plain(self, stem):
        if self.image is None:
            raise gameimage.ImageError("还没有打开镜像")
        return self.image.plain(stem)

    def blob(self, stem):
        """A data file as the game shipped it, encrypted the way it is stored — what a .bat patch
        looks for in an image. Built from what this program carries, so no image is needed."""
        return records.encode(bytearray(self.base[stem].base))

    def _named(self, stem):
        """{index: (jp, zh)} of a table, for the drop-downs that pick a skill or an item."""
        out = {}
        for target, known in self.base.items():
            file, index = records.parse(target)
            if file == stem:
                out[index] = (known.jp, known.zh)
        return out

    @staticmethod
    def _order(target):
        """A file's records come in the order the game numbers them, not the order they spell."""
        stem, index = records.parse(target)
        return (stem, -1 if index is None else index)

    def _entries(self):
        """Every record this build knows, by target."""
        out = {}
        for target in sorted(self.base, key=self._order):
            k = self.base[target]
            stem, index = records.parse(target)
            if index is None:
                note, source = "", DEMON
            elif stem == "ET0004":
                note, source = "", SKILLS
            else:
                note, source = self._kind_name(k.base[4]), GEAR
            out[target] = Entry(target, k.jp, k.zh, note, source, k.desc, k.race, k.deity)
        return out

    def level(self, target):
        """A demon's level as it will be written, for the list to show and sort by."""
        return self.current(target, 0x47, 1)

    def label(self, target):
        """How a record is written down in an edit table: what it is called, and for a demon the
        level as well, which is what tells its several forms apart."""
        e = self.entries[target]
        note = f"Lv{self.level(target)}" if e.source == DEMON else e.note
        return f"{e.zh} {note}".strip()

    # which slot each item kind goes in, read off the demons' own equipment (run/item_kinds.py)
    KIND_NAMES = {1: "药品", 2: "香", 3: "石", 4: "投掷", 5: "符", 6: "书", 7: "软件",
                  8: "卡", 9: "宝石", 10: "剧情", 11: "武器", 12: "枪弓", 13: "弹",
                  14: "全身", 15: "头", 16: "体", 17: "腕", 18: "脚", 19: "饰"}

    def _kind_name(self, kind):
        return self.KIND_NAMES.get(kind, f"类{kind}")

    def of_source(self, source):
        return [e for e in self.entries.values() if e.source == source]

    # ---- the fields of one record -----------------------------------------
    def fields(self, target):
        """Which numbers a record holds, off the record the game shipped: for a table record how
        long its block of numbers is, and which map fits it, both follow from the record itself."""
        stem, index = records.parse(target)
        if index is None:
            return DEMON_FIELDS
        base = self.base[target].base
        known = etfields.fields(base, 0, stem)
        head = len(base)
        out, taken = [], set()
        for off, width, zh, ja in known:
            out.append(("Values", "数値", zh, ja, off, width, et_kind(ja)))
            taken.update(range(off, off + width))
        for off in range(head):
            if off not in taken:
                out.append(("Unknown", "不明", f"0x{off:02X}", f"0x{off:02X}", off, 1, RAW))
        return out

    # ---- reading and editing ----------------------------------------------
    def has(self, target, off, width):
        """A field the editor may touch: one the record the game shipped holds."""
        return self.original(target, off, width) is not None

    def stored(self, target, off, width):
        """The value the image holds right now; None with no image open, or where its record has no
        such field."""
        if self.image is None:
            return None
        stem, _index = records.parse(target)
        try:
            return records.read(self._plain(stem), target, off, width)
        except records.RecordError:
            return None

    def original(self, target, off, width):
        """The value the game shipped, out of what this build carries with it."""
        known = self.base.get(target)
        if known is None or off + width > len(known.base):
            return None
        return int.from_bytes(known.base[off:off + width], "little")

    def _pair(self, target, off, width):
        entry = self.table["edits"].get(target)
        return entry.get(balance.KEY_OF[width], {}).get(f"{off:02X}") if entry else None

    def current(self, target, off, width):
        """What will be in the image once the edit table is written: what the table asks for, or,
        where it asks for nothing, what the image already holds — and with no image open, the value
        the game shipped."""
        pair = self._pair(target, off, width)
        if pair:
            return pair[1]
        stored = self.stored(target, off, width)
        return self.original(target, off, width) if stored is None else stored

    def set(self, target, off, width, value):
        key = balance.KEY_OF[width]
        orig = self.original(target, off, width)
        if orig is None:
            raise KeyError(f"{target} 没有偏移 0x{off:02X}")
        entry = self.table["edits"].get(target)
        stored = self.stored(target, off, width)
        # nothing to write: the game's own value, and the image already holds it (or there is none)
        if value == orig and stored in (None, value):
            if entry and f"{off:02X}" in entry.get(key, {}):
                del entry[key][f"{off:02X}"]
                if not entry[key]:
                    del entry[key]
                if not any(k in entry for k in balance.WIDTHS):
                    del self.table["edits"][target]
            return
        if entry is None:
            entry = self.table["edits"][target] = {"name": self.label(target), "note": ""}
        entry.setdefault(key, {})[f"{off:02X}"] = [orig, value]

    def reset(self, target, off=None, width=None):
        if off is None:
            self.table["edits"].pop(target, None)
        else:
            self.set(target, off, width, self.original(target, off, width))

    def edit_count(self, target):
        entry = self.table["edits"].get(target)
        if not entry:
            return 0
        return sum(len(entry.get(k, {})) for k in balance.WIDTHS)

    # ---- the edit table as a file -----------------------------------------
    def open_table(self, path):
        self.table = balance.load(path)
        self.path = path

    def save_table(self, path=None):
        self.path = path or self.path
        balance.save(self.table, self.path)
        return self.path

    def new_table(self, title=""):
        self.table = balance.empty(title)
        self.path = default_table(self.edition)

    # ---- writing the image -------------------------------------------------
    def image_state(self):
        """'original', 'edited' or 'mixed' for every record the edit table touches, as the image
        holds it now."""
        return {target: balance.state(self._plain(records.file_of(target)), target, entry)
                for target, entry in self.table["edits"].items()}

    def write_image(self, revert=False):
        """Put into the image what the boxes show (or, reverting, what the game shipped) and keep
        what it replaces. Returns (records written, name the old image was kept under)."""
        wrote, stems = balance.apply_table(self.table, self._plain, revert=revert)
        return wrote, self.image.save(stems)

    # ---- how a value reads -------------------------------------------------
    def skill_text(self, v, lang):
        if v == 0:
            return "0  —"
        jp, zh = self.skills.get(v, ("?", "?"))
        return f"{v}  {jp if lang == 'ja' else zh}"

    def item_text(self, v, lang):
        if v == 0:
            return "0  —"
        jp, zh = self.items.get(v, ("?", "?"))
        return f"{v}  {jp if lang == 'ja' else zh}"

    def enum_text(self, group, v, lang):
        pair = self.enums[group].get(str(v))
        if pair is None:
            return f"{v}  ?"
        if isinstance(pair, str):
            return f"{v}（{'ガイド' if lang == 'ja' else '攻略'} {pair}）"
        return f"{v}  {pair[0] if lang == 'ja' else pair[1]}"

    def resist_text(self, v, lang):
        if v in p2fields.RESIST_SPECIAL:
            ja = {0x00: "無効", 0xFC: "吸収", 0xFF: "反射"}
            return ja[v] if lang == "ja" else p2fields.RESIST_SPECIAL[v]
        return p2fields.resist_text(v)

    def rate_bucket(self, v, lang):
        label = None
        for low, ja, zh in self.enums["取得率区间"]:
            if v >= low:
                label = ja if lang == "ja" else zh
        return f"（{label}）"

    def moon_curve(self, value):
        """The day's damage multiplier (MOON_MULT of this edition) for moon ages 0-27 of this 月齢対応 row, or
        None past the table (the game would read whatever follows it)."""
        if not 0 <= value < len(self.moon):
            return None
        return [MOON_MULT[self.edition](v) for v in self.moon[value]]

    def moon_bands(self):
        """MOON_BANDS as this edition's multipliers."""
        f = MOON_MULT[self.edition]
        return [(f(a), f(b)) for a, b in MOON_BANDS]

# English presentation; the legacy display slot keeps its serialized key.
EDITIONS = {"main": (" (Fixes)", " (Fixes)"), "rebalance": (" (Rebalance)", " (Rebalance)")}
TABLE_NAMES = {"main": "balance.json", "rebalance": "balance_redesign.json"}
MOON_LEVELS = [("Weak", "弱い"), ("Normal", "普通"), ("Stronger", "やや強い"), ("Strong", "強い"), ("Very strong", "かなり強い")]
_EN_GROUPS = {'基本': 'Basic', '能力': 'Attributes', '耐性': 'Resistances', '技能': 'Skills', '装备': 'Equipment', '未知': 'Unknown'}
_EN_LABELS = {'等级': 'Level', '魔货': 'Currency', '月龄对应': 'Moon table', '取得率': 'Acquisition rate', '会话类型': 'Negotiation type', '装备相性': 'Equipment affinity', '速度': 'Speed', '行动模式': 'AI row', '直感': 'Intuition', '精神力': 'Willpower', '魔力': 'Magic', '知力': 'Intelligence', '加护': 'Grace', '力量': 'Strength', '体力': 'Vitality', '敏捷性': 'Agility', '器用': 'Dexterity', '魅力': 'Charm', '命运': 'Luck', '直接': 'Physical', '枪击': 'Gun', '火炎': 'Fire', '冰结': 'Ice', '冲击': 'Force', '电击': 'Electricity', '破魔': 'Expel', '咒杀': 'Curse', '神经': 'Nerve', '掉落道具': 'Dropped item', '药品': 'Medicine', '香': 'Incense', '石': 'Stone', '投掷': 'Thrown item', '符': 'Talisman', '书': 'Book', '软件': 'Software', '卡': 'Card', '宝石': 'Gem', '剧情': 'Story item', '武器': 'Weapon', '枪弓': 'Gun / Bow', '弹': 'Ammunition', '全身': 'Full body', '头': 'Head', '体': 'Body', '腕': 'Arms', '脚': 'Legs', '饰': 'Accessory', '剑': 'Sword', '枪': 'Gun'}
DEMON_FIELDS = [(_EN_GROUPS.get(g, g), gj, _EN_LABELS.get(label, label), lj, off, width, kind)
                for g, gj, label, lj, off, width, kind in DEMON_FIELDS]
SOURCES = [(DEMON, "Demons", "悪魔"), (SKILLS, "Magic / Skills", "魔法・特技"), (GEAR, "Items / Equipment", "武器・防具・アイテム")]
Game.KIND_NAMES = {k: _EN_LABELS.get(v, v) for k, v in Game.KIND_NAMES.items()}

def _english_field(row):
    group, gj, label, lj, off, width, kind = row
    if kind == SKILL:
        index = (off - p2fields.SKILLS_AT) // 2
        label = f"Held skill {index + 1}" if index < p2fields.HELD_SKILLS else f"Enemy skill {index - p2fields.HELD_SKILLS + 1}"
    elif kind == LEARN:
        label = f"Learning family {off - p2fields.LEARN_AT + 1}"
    return group, gj, label, lj, off, width, kind
DEMON_FIELDS = [_english_field(row) for row in DEMON_FIELDS]
