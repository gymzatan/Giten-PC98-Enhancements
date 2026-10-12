#!/usr/bin/env python3
"""The converted Windows artwork as the game draws it, one PNG per frame.

    winresult.py [OUT]      default: Windows素材_转换后/

The material that goes in is Windows素材原图/ (winsource.py); this is what comes out. Every picture
here is read back from the FC files the patch actually writes - built by the same call the patch is
built with - and drawn in the palette that entry carries in those files, at the size the entry draws,
with index 16 left transparent. So a picture here is the game's own pixels, not a preview of them.

An entry may hold several palettes: the same pixels recoloured, one chosen by whatever loads the entry -
the map section for a wall set, the demon record for a demon (P2 byte 6Dh), the script command for a
room. Those are written as _v0.._v5; an entry with one palette has no suffix. Which of them normal play
ever shows is listed in 说明.txt: every MS and ID script was scanned for the picture commands (266,
2DB, 2EA) and the variant they pass, and every call of the entry loader 0871:ADC0 in the executable
and its overlays for where its variant comes from.

Colours worth knowing when reading these:

  walls, doors, stairs   drawn in four colours - black, the set's three, and the white of slot 4,
                         which the status frame FC0000 sets and the dungeon never touches. Doors and
                         stairs write no palette of their own: on screen they take colours 1-3 from
                         whatever wall set is loaded, and the palette they are drawn in here is the
                         one their entry carries, which is one of the sets they serve.
  rooms and creatures    up to sixteen, but only the slots that entry is allowed to set; the rest
                         are the status frame's and the ones its neighbours on screen already hold.
                         A room that a battle can start in keeps to slots 0-7 (tools/winrooms.py
                         says why).

清单.csv lists every file with its entry, its frame, and the colours it uses.
"""
import csv
import os
import re
import shutil
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fcimage  # noqa: E402
import gfx  # noqa: E402
import mkwinpatch  # noqa: E402
import wintex  # noqa: E402

OUT = os.path.join(WORK, "Windows素材_转换后")
SRC = os.path.join(WORK, "files", "DDS98")
KIND = {"FC0000": "边框", "FC0110": "边框", "FC1300": "楼梯", "FC1400": "门", "FC1": "墙面",
        "FC2": "恶魔", "FC3": "场景图（FC3）", "FC4": "事件画面", "FC50F0": "标题",
        "FC5": "房间与事件"}
PART = {0: "墙与门的透视片", 4: "天花板", 5: "地板"}
README = """Windows 素材，转换后

偽典・女神転生 東京黙示録 的 Windows 重制版美术，压进 PC-98 版之后的样子。每一张都是从补丁
真正写进游戏的 FC 文件里读回来的，用的是那个条目在文件里带的调色板、那个条目实际画出的
尺寸，所以这就是游戏里的像素本身，不是预览图。

素材原图在 Windows素材原图/，文件名一一对应，可以并排比较。

文件名
  FC5030_e07_f000.png    FC5030 文件的第 7 个条目、第 0 帧。
  ..._v0 .. _v5          一个条目可以带好几套调色板，同一组像素换一套颜色。
                         带后缀的就是各套色；只有一套色的没有后缀。

多套配色
  游戏按场合挑一套。正常流程里用到第 1 套以后的只有：
      墙面      按地图分区选用
      恶魔      每种恶魔的数据里写着用第几套：FC2820 第 1 套是フォッグ
      房间图    FC5010 条目 10 第 1 套、FC5030 条目 7 第 2 套（脚本 MS003A），
                FC5030 条目 1 第 3 套（脚本 MS0052）
  其余第 1 套以后的配色在正常流程中不会出现。
  恶魔各套的颜色取自 Windows 版为那一套单独画的立绘。房间图 Windows 版只有一张，
  所以各套在转换可选的槽位上与第 0 套相同，只在与其它画面共用的槽位上保留游戏原来的换色；
  FC5010 条目 10 和 FC5030 条目 7 例外，它们的每套配色在 Windows 版里各有一张画。

目录
  墙面/ 门/ 楼梯/
      迷宫。墙面每套是 FC10s0：条目 0 是墙和门的透视片，条目 4 天花板，条目 5 地板。
      四色画面：黑、这一套自己的三色、以及 4 号槽的白——白是状态框 FC0000 设的，
      迷宫自己碰不到。门（FC1400）按墙套各有一条目（条目号等于墙套号），进游戏时
      用屏幕上当时那套墙的 1-3 号色；地图分区的门号已经改成与墙套相同。墙套 10
      的贴图没有门，仍是黑洞。这里画的是各条目自己带的那套墙色。
      楼梯另外还用状态框的白、红、绿、黄（4-7 号），它们在迷宫画面里一直都在。楼梯是按
      FC3000 第 7、8 帧的 Windows 原图转换的完整画面，按亮度选色，同一组像素在它服务的
      每套墙色下都成立；灯和指示牌用状态框里最接近的颜色画，别处不用红、绿、黄。
      墙面的单张是视角切片，单看认不出什么；墙面/_迷宫视图/ 里是按引擎的画法拼起来的
      整幅画面，每套墙每种配色各两张：走廊（两侧墙一直到尽头）和房间（正面一排墙）。
  房间与事件/ 事件画面/ 恶魔/ 场景图（FC3）/ 标题/
      最多十六色，但只有这个条目有权设的那几个槽是它自己的，其余是状态框的，
      以及同屏其它画面已经占着的。恶魔立绘的轮廓用透明（16 号）留出。
      会在里面开战的房间图只用 0-7 号槽：开战时房间图留作战斗背景，而 8-15 号槽
      在开战时清空、交给敌人，画在那里的像素会跟着敌人变色。
      恶魔立绘是 Windows 那张 256×256 画布整张按比例放进来的：条目 2 是 1:1，
      条目 4、6 缩到 158、115 像素（PC-98 自己的小图就是这个比例）。同一只恶魔
      的各帧对准同一个锚点，所以每张图的大小就是画本身占的格子，不是 PC-98
      原来的帧框。式神和用同一张图换色的护法童子、天逆神（FC2630）保留 PC-98
      原画，没有转换：Windows 版的式神只是在 PC-98 原画的轮廓里重新上了色，第 1、2
      帧还直接用了第 0 帧的画，压回 PC-98 的颜色只会更粗。
  边框/
      围着整个 640×400 屏幕的状态框（FC0000 条目 0 的十帧）和下面那块罗盘底板
      （FC0000 条目 2 帧 111、FC0110 条目 9 的四帧），原本是红绿黄凑出来的金色，
      这里换成灰色金属。画还是原来那张：先把原图用来画暗面的交错黑点并回它所在的
      色块（所以罗盘下面那条凹槽是平的），再把每种颜色画成固定网点——面是 2×2 一个
      白点，凹槽和压边是棋盘，面板全黑，细线全白，网格按帧在屏幕上的位置对齐。
      只用黑（0 号）和白（4 号）是因为全游戏的画面都把这两个槽填成黑和白，边框走到
      哪儿都不会串色；红、绿、黄是血条和状态在用的，没有动。罗盘表盘里的白面和红
      字母原样留着，外圈黑环也是原图那一圈。
      命令按钮、方向盘和菜单文字仍是原版的绿色，补丁不动。

清单.csv 列出每个文件的条目、帧号和它用到的颜色。
"""


def label(fc):
    for pre in ("FC0000", "FC0110", "FC1300", "FC1400", "FC50F0", "FC1", "FC2", "FC3", "FC4",
                "FC5"):
        if fc.startswith(pre):
            return KIND[pre]
    raise SystemExit(f"{fc}: 不知道这是哪一类")


def rgb(word):
    return ((word >> 4) & 15) * 17, ((word >> 8) & 15) * 17, (word & 15) * 17


def render(img, f, palette):
    """One frame as RGBA, the entry's palette applied and index 16 left transparent."""
    w, h, pix = img.indices(f)
    out = Image.new("RGBA", (w, h))
    out.putdata([(0, 0, 0, 0) if c is None else rgb(palette[c]) + (255,) for c in pix])
    return out


def wall_view(entries, palette, layout):
    """A wall set as the engine puts it on screen: ceiling, floor and the pieces of one view."""
    imgs = {k: fcimage.Image(entries[k]) for k in (0, 4, 5)}
    pieces = {k: [wintex.Piece(img, k, f) for f in wintex.owners(img)] for k, img in imgs.items()}
    return Image.fromarray(wintex.compose(pieces, None, palette, True, layout))


def built():
    """{FC name: entries}, read back from the files the patch writes."""
    files, _changes = gfx.edited_files(mkwinpatch.merged(mkwinpatch.ROOT))
    return {os.path.splitext(name)[0]: fcimage.entries(blob) for name, blob in files.items()}


def build(out=OUT):
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    rows = []
    root = os.path.join(mkwinpatch.ROOT, "gfx")
    entries_of = built()

    for folder in sorted(os.listdir(root)):
        fc = folder
        entries = entries_of[fc]
        cat = label(fc)
        dest = os.path.join(out, cat)
        os.makedirs(dest, exist_ok=True)
        for png in sorted(os.listdir(os.path.join(root, folder))):
            m = re.fullmatch(r"(\d{2})_(\d{3})\.png", png)
            if not m:
                continue
            k, f = int(m.group(1)), int(m.group(2))
            img = fcimage.Image(entries[k])
            if not img.palettes:
                raise SystemExit(f"{fc} 条目 {k} 没有调色板，画不出来")
            for vi, pal in enumerate(img.palettes):
                im = render(img, f, pal)
                tail = f"_v{vi}" if len(img.palettes) > 1 else ""
                name = f"{fc}_e{k:02d}_f{f:03d}{tail}.png"
                im.save(os.path.join(dest, name))
                used = sorted({c for c in img.indices(f)[2] if c is not None})
                rows.append([cat, name, f"{im.size[0]}x{im.size[1]}", f"{fc} 条目{k} 帧{f}",
                             f"{vi + 1}/{len(img.palettes)}",
                             " ".join(f"{pal[c]:03X}" for c in used),
                             PART.get(k, "") if cat == "墙面" else ""])

    # the wall pieces are slivers of a view; assembled they are the dungeon the player walks through
    views = os.path.join(out, "墙面", "_迷宫视图")
    os.makedirs(views, exist_ok=True)
    for fc in sorted(entries_of):
        if not re.fullmatch(r"FC10[0-9A]0", fc):
            continue
        pals = fcimage.Image(entries_of[fc][0]).palettes
        for vi, pal in enumerate(pals):
            for layout, zh in (("corridor", "走廊"), ("room", "房间")):
                im = wall_view(entries_of[fc], pal, layout)
                name = f"{fc}_v{vi}_{zh}.png"
                im.save(os.path.join(views, name))
                rows.append(["墙面/_迷宫视图", name, f"{im.size[0]}x{im.size[1]}",
                             f"{fc} 条目 0+4+5 合成", f"{vi + 1}/{len(pals)}",
                             " ".join(f"{c:03X}" for c in pal[:4]), "整幅视图"])

    with open(os.path.join(out, "说明.txt"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(README)
    with open(os.path.join(out, "清单.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["分类", "文件", "尺寸", "来自", "第几套色", "用到的颜色 (0GRB)", "部位"])
        w.writerows(rows)
    print(f"{len(rows)} 个文件写入 {out}")
    for d in sorted(os.listdir(out)):
        p = os.path.join(out, d)
        if os.path.isdir(p):
            n = sum(len([x for x in fs if x.endswith(".png")]) for _r, _d, fs in os.walk(p))
            print(f"  {d}/  {n} 个")
    return out


if __name__ == "__main__":
    build(*sys.argv[1:])
