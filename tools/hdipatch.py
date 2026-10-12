#!/usr/bin/env python3
"""Apply or take back an edit table's changes in a game disk image.

    hdipatch.py status IMAGE.hdi [TABLE.json]     what state each edited record is in
    hdipatch.py apply  IMAGE.hdi [TABLE.json]     write the edited values
    hdipatch.py revert IMAGE.hdi [TABLE.json]     put the original values back

The edits only touch numbers, never any text, so the same table fits the Japanese original and the
Chinese build; a record is recognised by the values it holds, and records inside the ET tables are
found through each image's own pointer list, which the two builds do not share. Every record is
checked before anything is written, and the image is left untouched when any of them does not match.
Running the same command twice changes nothing the second time.

A write keeps the image it replaces, beside it under the same name with the time of the write in it
(tools/gameimage.py), so the file the game is launched from is always the edited one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balance  # noqa: E402
import gameimage  # noqa: E402


def run(action, image, table, backup=True):
    if not table["edits"]:
        raise SystemExit("这张修改表里没有任何改动")
    img = gameimage.GameImage(image)
    plans = balance.plan(table, img.plain)

    if action == "status":
        for _stem, plain, target, entry in plans:
            print(f"  {target} 「{entry.get('name', target)}」: "
                  f"{balance.state(plain, target, entry)}")
        return 0

    revert = action == "revert"
    wrote, stems = balance.apply_table(table, img.plain, revert=revert)
    if not wrote:
        print(f"{image}：已经是{'出厂' if revert else '补丁后'}数值，无需改动")
        return 0
    kept = img.save(stems, backup=backup)
    if kept:
        print(f"  已把原镜像另存为 {os.path.basename(kept)}")
    print(f"{image}：{'还原' if revert else '打补丁'}完成 — " + "、".join(wrote))
    return 0


USAGE = """把 Giten.hdi（原始日文版）或 Giten_CN.hdi（汉化版）拖到本文件上即可。
两个补丁都会先核对镜像里的数值，对不上就什么都不改；打过的补丁再打一次也不会重复。
每次改动前会把原镜像另存为 <文件名>.hdi.<日期-时间>.bak。

改动的是："""


def usage():
    print(USAGE)
    for target, entry in balance.load()["edits"].items():
        print(f"  {entry.get('name', target)}　{entry.get('note', '')}")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("status", "apply", "revert"):
        if len(sys.argv) == 1:
            usage()
        else:
            print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2], balance.load(*sys.argv[3:4])))
