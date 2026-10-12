#!/usr/bin/env python3
"""The Windows release's pictures as BMP files, every frame, original bytes.

    winbmps.py [OUT]      default: Windows完整素材/

ddswin/fc/*.bin is a concatenation of BMPs; ddswin/w/*.bmp is already one file per
texture. This writes each picture out as .bmp without re-encoding, including frames the
PC-98 conversion never uses. Windows素材原图/ is the other dump: PNG, and only the
pictures the conversion reads, named after the PC-98 entry they become.
"""
import csv
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
WIN = os.path.join(WORK, "inputs", "ddswin")
OUT = os.path.join(WORK, "windows-bmp")

KIND = {
    "fc2": "恶魔",
    "fc3": "场景图",
    "fc4": "事件画面",
    "fc5": "房间与事件",
    "fc6": "fc6",
    "fc7": "状态框与界面",
    "fch": "状态框（高分辨率）",
}
README = """Windows 完整素材（BMP）

偽典・女神転生 東京黙示録 Windows 重制版安装目录里的全部画面，按原样拆成一张张
.bmp。像素、调色板、文件头都是游戏里的那一份，没有转成 PNG，也没有按 PC-98 能用
的颜色重映射。

这和 Windows素材原图/ 不是同一套：那边是转换实际读到的图，PNG，文件名是 PC-98
的条目；这边是 Windows 自己的完整库存，包括转换没用上的帧（占位的 8x8、DUMMY
板、Windows 多出来的界面图等）。

来源
  WIN/Giten Megami Tensei/ddswin/fc/*.bin
      每个 .bin 是若干 BMP 首尾相接。拆成 fc/<bin 名>/000.bmp、001.bmp……
      文件名就是 Windows 的：fc20020 是恶魔立绘，末位是配色套号；fc3000 一类是
      场景；fc4、fc5 是事件和房间；fc7e / fch7e 是状态框一带的界面。
  WIN/Giten Megami Tensei/ddswin/w/*.bmp
      迷宫贴图，本来就是 BMP，原样复制到 w/。wall*_*.bmp 每张 256x256，四象限是
      天花板 / 墙 / 门 / 地板。up.bmp、dn.bmp 是楼梯中间一截。w/pc98/ 是重制组
      另画的十六色「PC-98 风格」贴图，不是 PC-98 原版；其中 *_opaque.bmp 是后来
      为转换加的不透明副本。

清单.csv 列出每张图的尺寸、色深和它从哪个文件第几张拆出来。
"""


def kind_of(stem):
    s = stem.lower()
    for pre in ("fch", "fc2", "fc3", "fc4", "fc5", "fc6", "fc7"):
        if s.startswith(pre):
            return KIND[pre]
    return "其他"


def bmp_slices(data):
    """(offset, size, width, height, bpp) for each BMP packed in a Windows fc bin."""
    pos = 0
    n = 0
    while pos + 30 <= len(data) and n < 128:
        if data[pos:pos + 2] != b"BM":
            nxt = data.find(b"BM", pos + 1)
            if nxt < 0:
                break
            pos = nxt
            if pos + 30 > len(data):
                break
        bf_size = struct.unpack_from("<I", data, pos + 2)[0]
        offbits = struct.unpack_from("<I", data, pos + 10)[0]
        w = abs(struct.unpack_from("<i", data, pos + 18)[0])
        h = abs(struct.unpack_from("<i", data, pos + 22)[0])
        bpp = struct.unpack_from("<H", data, pos + 28)[0]
        if bf_size < 54 or pos + bf_size > len(data):
            row = ((w * bpp + 31) // 32) * 4
            guess = offbits + row * h
            if guess >= 54 and pos + guess <= len(data):
                bf_size = guess
            else:
                break
        yield pos, bf_size, w, h, bpp
        pos += bf_size
        n += 1


def write_bmps(src, dest, rel_dir, rows, cat, origin):
    data = open(src, "rb").read()
    os.makedirs(dest, exist_ok=True)
    n = 0
    end = 0
    for off, size, w, h, bpp in bmp_slices(data):
        name = f"{n:03d}.bmp"
        open(os.path.join(dest, name), "wb").write(data[off:off + size])
        rows.append([cat, f"{rel_dir}/{name}", f"{w}x{h}", bpp, size, origin, n])
        n += 1
        end = off + size
    if n == 0:
        raise SystemExit(f"{origin}: 里面没有 BMP")
    if end != len(data):
        raise SystemExit(f"{origin}: 拆完还剩 {len(data) - end} 字节")
    return n


def copy_w(src_w, dest_w, rows):
    n = 0
    for dirpath, dirnames, names in os.walk(src_w):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, src_w)
        for name in sorted(names):
            if not name.lower().endswith(".bmp"):
                continue
            src = os.path.join(dirpath, name)
            if rel_dir == ".":
                dest_dir, origin, rel = dest_w, f"w/{name}", f"w/{name}"
            else:
                dest_dir = os.path.join(dest_w, rel_dir)
                origin = f"w/{rel_dir.replace(os.sep, '/')}/{name}"
                rel = origin
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(src, os.path.join(dest_dir, name))
            header = open(src, "rb").read(30)
            w = abs(struct.unpack_from("<i", header, 18)[0])
            h = abs(struct.unpack_from("<i", header, 22)[0])
            bpp = struct.unpack_from("<H", header, 28)[0]
            rows.append(["迷宫贴图" if rel_dir == "." else "迷宫贴图_PC98风格",
                         rel.replace("\\", "/"), f"{w}x{h}", bpp, os.path.getsize(src), origin, ""])
            n += 1
    return n


def build(out=OUT):
    fc = os.path.join(WIN, "fc")
    src_w = os.path.join(WIN, "w")
    if not os.path.isdir(fc) or not os.path.isdir(src_w):
        raise SystemExit(f"找不到 Windows 素材目录：{WIN}")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    rows = []
    dest_fc = os.path.join(out, "fc")
    for name in sorted(os.listdir(fc)):
        if not name.lower().endswith(".bin"):
            continue
        stem = os.path.splitext(name)[0]
        write_bmps(os.path.join(fc, name), os.path.join(dest_fc, stem),
                   f"fc/{stem}", rows, kind_of(stem), f"fc/{name}")
    copy_w(src_w, os.path.join(out, "w"), rows)
    with open(os.path.join(out, "说明.txt"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(README)
    with open(os.path.join(out, "清单.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["分类", "文件", "尺寸", "色深", "字节", "来源", "bin 内序号"])
        w.writerows(rows)
    print(f"{len(rows)} 个文件写入 {out}")
    for d in ("fc", "w"):
        p = os.path.join(out, d)
        n = sum(1 for _r, _ds, fs in os.walk(p) for x in fs if x.lower().endswith(".bmp"))
        print(f"  {d}/  {n} 个")
    return out


if __name__ == "__main__":
    build(*sys.argv[1:])
