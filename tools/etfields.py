"""Where the numbers live in the ET table records.

Every ET table is laid out the same way: a count word, that many 2-byte offsets, then the records.
A record starts with a block of numbers and ends with its name and description as text. How long that
block is depends on the record: 20 bytes for a skill, and for an item the kind byte at offset 4 says
which of tables.ITEM_HEADER's lengths applies.

The offsets below were settled by pairing the records with the unofficial guide's own tables and
keeping only the offsets whose value decides a printed column across the whole set (run/et_match.py,
run/skill_match.py). Kinds with no column to match them against carry no map yet and are shown as
plain numbered bytes.
"""
import struct
import tables
SKILL = [(0, 1, 'Class', '系統'), (1, 1, 'Learning pool', '修得系統'), (2, 1, 'Level', 'レベル'), (3, 1, 'Cost', '消費'), (4, 1, 'Use context', '使用状況'), (5, 1, 'Range', '範囲'), (6, 1, 'Targets', 'リストアップ対象'), (7, 1, 'Target count', '体数'), (8, 1, 'Distance', '距離'), (12, 1, 'Element', '相性'), (13, 1, 'Added status', '追加効果')]
WEAPON = [(5, 1, 'Equipment affinity', '装備相性'), (9, 1, 'Sword power', '剣攻撃力'), (11, 1, 'Sword accuracy', '剣命中率'), (13, 1, 'Element', '相性'), (14, 1, 'Distance', '距離'), (15, 1, 'Minimum hits', '攻撃回数 下限'), (16, 1, 'Maximum hits', '攻撃回数 上限'), (17, 1, 'Vitality requirement', '必要体力'), (18, 1, 'Dexterity requirement', '必要器用さ'), (21, 1, 'Added status', '追加効果'), (26, 2, 'Activated skill', '発動魔法／特技'), (29, 1, 'Magic power', '魔法攻撃力')]
ARMOUR = [(5, 1, 'Equipment affinity', '装備相性'), (9, 1, 'Defense', 'Defense'), (10, 1, 'Evasion', '回避率（剣攻撃）'), (13, 1, 'Element', '相性')]
BY_KIND = {11: WEAPON}
BY_KIND.update({k: ARMOUR for k in (14, 15, 16, 17, 18, 19)})

def pointers(plain):
    """The offset of every record in an ET table chunk."""
    count = struct.unpack_from('<H', plain, 0)[0]
    return [struct.unpack_from('<H', plain, 2 + 2 * i)[0] for i in range(count)]

def head_len(plain, start, stem):
    """How many bytes of numbers this record carries before its text."""
    if stem == 'ET0004':
        return tables.SKILL_HEADER
    return tables.ITEM_HEADER.get(plain[start + 4], 0)

def fields(plain, start, stem):
    """The map for one record, or [] when that kind has not been worked out yet."""
    if stem == 'ET0004':
        return SKILL
    return BY_KIND.get(plain[start + 4], [])
