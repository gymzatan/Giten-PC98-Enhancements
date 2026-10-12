#!/usr/bin/env python3
"""The Windows release's artwork, pulled out whole and filed under what it becomes in the PC-98 game.

    winsource.py [OUT]      default: Windows素材原图/

Everything here is the Windows picture as it ships - full size, full colour, nothing reduced. What the
conversion does to it (fitting each picture to the few colours its PC-98 entry may set) happens
elsewhere; this is the material that goes in.

Two kinds of source, kept apart because they are found in different ways:

  fc/*.bin   one or more Windows BMPs per file, belonging to a PC-98 file, entry and frame. Which
             picture belongs where is run/win_to_pc98.py's catalogue, and only the frames the
             conversion turned into game pictures (gfx_win_fit/) are written, so this folder is
             exactly what went into the patch - not the catalogue's other matches (gfx_win/ also
             holds placements for frames that keep their PC-98 picture, some for frames the PC-98
             entry does not even have).
             A demon's sprites come once per palette variant (fc26320, fc26321, ...): the variant-0
             set is what the pixels are fitted to, the others what that variant's colours are, and
             all of them are written.
  w/*.bmp    the dungeon's own material, not tied to an entry: one 256x256 texture per wall set and
             variant, each holding four quarters - ceiling, wall, door, floor - and beside them the
             staircases, the treasure box, the NPC and the markers.

w/pc98/ is written too, under its own name: those are not the PC-98 game's own pictures but the
remake's drawings of how they might have looked, at 256x256 and sixteen colours where the game's wall
art has four, so they are material like the rest and not a reference.

清单.csv lists every file written with where it came from and what it is for.
"""
import csv
import functools
import os
import re
import shutil
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(WORK, "run"))
import fcimage  # noqa: E402
import wintex  # noqa: E402
import win_to_pc98 as W2P  # noqa: E402

OUT = os.path.join(WORK, "Windows素材原图")
SRC = os.path.join(WORK, "files", "DDS98")
KIND = {"FC2": "恶魔", "FC3": "场景图（FC3）", "FC4": "事件画面", "FC50F0": "标题",
        "FC5": "房间与事件"}
MODE = {"cg": "整幅画面", "sprite": "立绘（自带透明轮廓）"}
OTHER = {"txrtbox.bmp": "宝箱", "npc.bmp": "NPC", "target.bmp": "目标标记",
         "fight.bmp": "战斗标记", "darkwall.bmp": "暗墙", "white.bmp": "白底",
         "up.bmp": "上楼梯", "dn.bmp": "下楼梯"}
README = """Windows 版素材原图

偽典・女神転生 東京黙示録 Windows 重制版的美术素材，按它们在 PC-98 版里对应的位置整理。
全部是原始尺寸、原始颜色，没有做任何缩减——把它们压进 PC-98 每个条目能用的那几种颜色，
是转换工具的事，不在这里。

目录
  房间与事件/ 恶魔/ 场景图（FC3）/ 事件画面/ 标题/
      来自 ddswin/fc/*.bin。文件名是它对应的 PC-98 位置：FC5030_e07_f000 表示
      FC5030 文件的第 7 个条目、第 0 帧；它在原始 .bin 中的序号见清单.csv。
      帧号偶有跳号：有的帧和前面某一帧是同一张画（迷雾、跺脚鬼的第 1、2 帧就是
      第 0 帧），有的没有换成 Windows 的画、游戏里仍是 PC-98 原画——多是 PC-98 条目
      里只有几像素大的占位帧，Windows 版没有对应的画。
      恶魔的立绘按配色各有一套：同一个 PC-98 条目换一套配色就是另一种恶魔
      （FC2820 第 0 套是黑暗，第 1 套是迷雾，第 2 套游戏里没有恶魔用），Windows 版
      给每套都画了一份。文件名末尾的 _v0、_v1 就是第几套；像素按 _v0 拟合，_v1 等决定
      那一套的颜色。
      多数 640x400 的场景图带着重制版自己的边框——瓷砖背景加中间一块「屏幕」，
      画面在屏幕里面。转换时会先裁到那块屏幕再压色，所以进游戏的是中间一块，
      不是整张。清单.csv 的「游戏内尺寸」是裁压之后、PC-98 条目实际画出的大小。
  墙面/
      来自 ddswin/w/wall*.bmp，每张 256x256，分成四个象限：
          左上 天花板   右上 墙面
          左下 门       右下 地板
      文件名标出它服务的迷宫墙套与变体。
  楼梯/ 其他/
      上下楼梯、宝箱、NPC、标记等不属于任何条目的素材。
      迷宫里的楼梯不是按这里的 up、dn 转换的：它们只是同一段楼梯裁下的中间一截。
      转换用的是完整画面，也就是 场景图（FC3）/ 里的 FC3000_e00_f007（上楼）和 f008（下楼）。
  墙面_PC98风格/
      来自 ddswin/w/pc98/。这不是 PC-98 版自己的美术，而是重制组另画的「PC-98 风格」
      贴图——同样是 256x256 十六色，而游戏的墙面只有四色。作为素材收录，不能当原版参照。

清单.csv 列出每个文件的来源与用途。
"""


def label(fc):
    if fc in KIND:
        return KIND[fc]
    for pre in ("FC50F0", "FC2", "FC3", "FC4", "FC5"):
        if fc.startswith(pre):
            return KIND[pre]
    return "其他"


@functools.lru_cache(maxsize=None)
def palettes_of(fc, k):
    return len(fcimage.Image(fcimage.entries(open(os.path.join(SRC, fc + ".BIN"), "rb").read())[k])
               .palettes)


def variant_bins(cat, j, fc, k):
    """{variant: path} of a demon's other sprite sets, as winfit.variant_sources finds them."""
    stem = os.path.splitext(os.path.basename(j["path"]))[0]
    kind = W2P.resolve(stem, cat)
    if not kind or kind[0] != "demon":
        return {}
    return {v: cat.win[stem[:-1] + f"{v:x}"] for v in range(1, palettes_of(fc, k))
            if stem[:-1] + f"{v:x}" in cat.win}


def jobs(cat):
    """The catalogue's chosen picture for every PC-98 frame the conversion converts."""
    best = {}
    for stem, path in sorted(cat.win.items()):
        kind = W2P.resolve(stem, cat)
        if not kind:
            continue
        for j in W2P.jobs_for_file(path, kind, cat):
            key = (j["fc"], j["png"])
            if key not in best or j["score"] > best[key]["score"]:
                best[key] = j
    return best


def build(out=OUT):
    # rebuilt whole, like winresult.py: a picture the conversion stopped reading must not linger here
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    rows = []
    cat = W2P.Catalog()

    for (fc, png), j in sorted(jobs(cat).items()):
        # only what the conversion turned into a picture of the game
        fitted = os.path.join(WORK, "gfx_win_fit", fc, png)
        if not os.path.exists(fitted):
            continue
        m = re.fullmatch(r"(\d{2})_(\d{3})\.png", png)
        if not m:
            continue
        k, f = int(m.group(1)), int(m.group(2))
        others = variant_bins(cat, j, fc, k)
        folder = os.path.join(out, label(fc))
        os.makedirs(folder, exist_ok=True)
        # the frame the conversion produced is at the size the PC-98 entry draws
        gw, gh = Image.open(fitted).size
        for v, path in sorted({0: j["path"], **others}.items()):
            bmps = W2P.parse_bmps(open(path, "rb").read())
            if j["bmp_index"] >= len(bmps):
                continue
            im = bmps[j["bmp_index"]]
            tail = f"_v{v}" if others else ""
            name = f"{fc}_e{k:02d}_f{f:03d}{tail}.png"
            im.convert("RGB").save(os.path.join(folder, name))
            use = MODE.get(j.get("mode", ""), j.get("mode", ""))
            rows.append([label(fc), name, f"{im.size[0]}x{im.size[1]}", f"{gw}x{gh}",
                         os.path.basename(path), j["bmp_index"],
                         f"{use}，第 {v} 套配色" if others else use])

    table = wintex.texture_table()
    serves = {}
    for (s, v), bmp in sorted(table.items()):
        serves.setdefault(os.path.basename(str(bmp)), []).append(f"墙套{s}变体{v}")
    walls = os.path.join(out, "墙面")
    os.makedirs(walls, exist_ok=True)
    src_w = os.path.join(wintex.WIN, "w")
    for name in sorted(os.listdir(src_w)):
        path = os.path.join(src_w, name)
        if not os.path.isfile(path) or not name.lower().endswith(".bmp"):
            continue
        im = Image.open(path)
        if name.lower().startswith("wall"):
            who = "、".join(serves.get(name, [])) or "未被任何地图使用"
            dest = os.path.join(walls, f"{os.path.splitext(name)[0]}.png")
            im.convert("RGB").save(dest)
            rows.append(["墙面", os.path.basename(dest), f"{im.size[0]}x{im.size[1]}",
                         "按视角缩放", name, "", who])
        else:
            what = OTHER.get(name.lower(), "")
            folder = os.path.join(out, "楼梯" if name.lower() in ("up.bmp", "dn.bmp") else "其他")
            os.makedirs(folder, exist_ok=True)
            dest = os.path.join(folder, f"{os.path.splitext(name)[0]}.png")
            im.convert("RGB").save(dest)
            rows.append([os.path.basename(folder), os.path.basename(dest),
                         f"{im.size[0]}x{im.size[1]}", "按视角缩放", name, "", what])

    pc98 = os.path.join(src_w, "pc98")
    if os.path.isdir(pc98):
        folder = os.path.join(out, "墙面_PC98风格")
        os.makedirs(folder, exist_ok=True)
        for name in sorted(os.listdir(pc98)):
            if not name.lower().endswith(".bmp"):
                continue
            im = Image.open(os.path.join(pc98, name))
            dest = os.path.join(folder, f"{os.path.splitext(name)[0]}.png")
            im.convert("RGB").save(dest)
            rows.append(["墙面_PC98风格", os.path.basename(dest),
                         f"{im.size[0]}x{im.size[1]}", "按视角缩放", f"pc98/{name}", "",
                         "重制组另画，非原版"])

    with open(os.path.join(out, "说明.txt"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(README)
    with open(os.path.join(out, "清单.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["分类", "文件", "原图尺寸", "游戏内尺寸", "来源", "bin 内序号",
                    "用途 / 服务的墙套"])
        w.writerows(rows)
    print(f"{len(rows)} 个文件写入 {out}")
    for d in sorted(os.listdir(out)):
        p = os.path.join(out, d)
        if os.path.isdir(p):
            print(f"  {d}/  {len(os.listdir(p))} 个")
    return out


if __name__ == "__main__":
    build(*sys.argv[1:])
