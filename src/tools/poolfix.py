#!/usr/bin/env python3
"""The protagonist's learning pools of the 再平衡版 (tools/rebalance.py): skills added to ET0030. Content, not a fix,
so the plain Chinese builds leave the game's pools alone (the user, 2026-10-01: 「只放再平衡版」).

    poolfix.py      the pools before and after, with the skill names and the file sizes

ET0030 is stored raw (not enciphered): [length u16], then the body - [count u16], count entries of
[offset u16][pool id s16] (offsets from the body's start), then each pool's skill ids (u16) closed by
FFFF. The protagonist's pool for an awakened slot is -1 - the slot's skill (剑 -1, 枪 -2, 魔法 -3,
COMP -4): ov02:0D9E works it out from the slot byte with no case for any skill and looks the id up
in the entry table by the table's own count. A companion's pool is its index in the runtime human
table. The game ships no pool for 枪, so that route learns nothing of its own.

ADD appends to the pools (a pool the game lacks is made):
  魔法 -3  メギ, メギド, メギドラオン - the route's attack spells are fire and nothing else, and fire
           is resisted by about half the demons of the late game
  枪 -2    the gun skills - ボンブ, ハンドガン, ショットガン, マシンガン, レーザーガン, which tools/skillfix.py (in
           every build) makes work - and the ダム line, the 枪击 magic learnt by no protagonist so far,
           in learn-level order: ボンブ 1, ハンドガン 5, ダーム 5, ダムド 10, ショットガン 15, ダムドーラ 20,
           マシンガン 25, ダムドラオン 35, レーザーガン 35. None of them is in any pool of the game's own
Learning itself is the game's: each level-up tries the candidates in list order by (character level
- the skill's learn level) x 10 + 知力 against the mean of three U(10..60) (ov13:06D6), so the four
gun templates learn at the levels tools/skillfix.py gives them. The three slots' pools together fill a
list of at most 63 (DS:952C-95AA); with these the largest pair of slots (剑 with 魔法 and COMP) reaches
46. Nothing in ET0030 is text, so one pair of contents - as shipped and as changed - fits the Japanese
original and every Chinese build; the 再平衡 .bat patches carry them whole (tools/mkpatchbat.py)."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tables  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98")
NAME = "ET0030.BIN"
LABEL = "主角的技能学习池"
ADD = ((-3, ("メギ", "メギド", "メギドラオン")),
       (-2, ("ボンブ", "ハンドガン", "ダーム", "ダムド", "ショットガン", "ダムドーラ", "マシンガン", "ダムドラオン",
             "レーザーガン")))
POOL_NAMES = {-1: "剑", -2: "枪", -3: "魔法", -4: "COMP"}
LIST_MAX = 63


class PoolError(ValueError):
    pass


def skill_names(src_dir=SRC):
    """{skill id: Japanese name} from ET0004's string table (a 20-byte header before the name)."""
    (chunk,) = tables.chunks_of(open(os.path.join(src_dir, "ET0004.BIN"), "rb").read())[:1]
    return {i: bytes(e[20:]).split(b"\0")[0].decode("cp932") for i, e in enumerate(tables.string_table(chunk))
            if len(e) > 20}


def parse(raw):
    """[(pool id, [skill ids])] in entry-table order, and the lists' order in the file (pool ids)."""
    length = struct.unpack_from("<H", raw, 0)[0]
    if length + 2 != len(raw):
        raise PoolError(f"{NAME}: length word {length}, file {len(raw)} bytes")
    body = raw[2:]
    count = struct.unpack_from("<H", body, 0)[0]
    pools, offsets = [], {}
    for i in range(count):
        off, pid = struct.unpack_from("<Hh", body, 2 + 4 * i)
        ids = []
        while True:
            (v,) = struct.unpack_from("<H", body, off + 2 * len(ids))
            if v == 0xFFFF:
                break
            ids.append(v)
        pools.append((pid, ids))
        offsets[pid] = off
    return pools, sorted(offsets, key=offsets.get)


def serialize(pools, order):
    """The file for pools [(pool id, [ids])] (entry-table order) with their lists laid out in `order`."""
    head = 2 + 4 * len(pools)
    lists, offsets = bytearray(), {}
    for pid in order:
        offsets[pid] = head + len(lists)
        ids = dict(pools)[pid]
        lists += struct.pack(f"<{len(ids)}H", *ids) + b"\xff\xff"
    body = bytearray(struct.pack("<H", len(pools)))
    for pid, _ids in pools:
        body += struct.pack("<Hh", offsets[pid], pid)
    body += lists
    return struct.pack("<H", len(body)) + bytes(body)


def changed(raw, src_dir=SRC):
    """ET0030 with ADD applied: added skills go at the end of their pool's list, a new pool's entry at
    the end of the entry table and its list after the others; the rest stays in place and in order."""
    pools, order = parse(raw)
    if serialize(pools, order) != raw:
        raise PoolError(f"{NAME}: laid out other than this tool writes it")
    by_name = {}
    for sid, name in skill_names().items():
        by_name.setdefault(name, []).append(sid)
    pools = [(pid, list(ids)) for pid, ids in pools]
    for pid, names in ADD:
        ids = []
        for n in names:
            if len(by_name.get(n, ())) != 1:
                raise PoolError(f"ET0004: {n} names {len(by_name.get(n, ()))} skills")
            ids.append(by_name[n][0])
        have = dict(pools)
        if pid not in have:
            pools.append((pid, []))
            order.append(pid)
            have = dict(pools)
        if set(ids) & set(have[pid]):
            raise PoolError(f"pool {pid} already holds some of {names}")
        have[pid] += ids
    new = serialize(pools, order)
    # slot 1 is 剑 for every protagonist; the aptitude check, 黄泉 and バエル fill the other two with two of
    # 枪 / 魔法 / COMP, which two the game decides - so every such pair has to fit the list
    size = {pid: len(ids) for pid, ids in pools}
    for pair in ((-2, -3), (-2, -4), (-3, -4)):
        n = size[-1] + sum(size.get(p, 0) for p in pair)
        if n > LIST_MAX:
            raise PoolError(f"剑 + {'/'.join(POOL_NAMES[p] for p in pair)}: {n} candidates, the list holds {LIST_MAX}")
    return new


def edit(src_dir=SRC):
    """(file name, label, as shipped, as changed) for the .bat patches (tools/mkpatchbat.py)."""
    raw = open(os.path.join(src_dir, NAME), "rb").read()
    return NAME, LABEL, raw, changed(raw, src_dir)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    names = skill_names()
    _name, _label, before, after = edit()
    for tag, raw in (("游戏原版", before), ("加入后", after)):
        pools, _order = parse(raw)
        print(f"== {tag}（{len(raw)} 字节）")
        for pid, ids in pools:
            if pid < 0:
                print(f"  {POOL_NAMES[pid]}（{pid}）：" + "、".join(names[s] for s in ids))


if __name__ == "__main__":
    main()
