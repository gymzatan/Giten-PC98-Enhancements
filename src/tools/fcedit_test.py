#!/usr/bin/env python3
"""Self-test of the picture editor, without opening a window.

    fcedit_test.py [IMAGE.hdi]      default: dist/Redux/Game.hdi

A copy of the image goes through the whole path: a file exported, an exported PNG edited by hand and
put back as it is, an ordinary picture converted into another entry's frame, the image written. Then
the written image is opened again and what it draws is compared with what was staged, pixel for pixel
and palette for palette - the encoder's own check only says the entry decodes to what was handed to
it, not that the right bytes reached the disk. The backup and a file nobody touched are checked too.
"""
import os
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fcedit  # noqa: E402
import fcfit  # noqa: E402

IMAGE = os.path.join(WORK, "dist", "Redux", "Game.hdi")
HAND = ("FC5000", 2, 0)                 # one frame, edited as an indexed PNG
SHOT = ("FC5030", 3, 0)                 # another entry, given a picture to convert


def run(image=IMAGE):
    if not os.path.exists(image):
        raise SystemExit(f"缺少 {image}")
    room = tempfile.mkdtemp(prefix="fcedit_test_")
    try:
        copy = os.path.join(room, os.path.basename(image))
        shutil.copyfile(image, copy)
        bundle = fcedit.Bundle(copy)
        print(f"{os.path.basename(image)}：{len(bundle.names)} 个图形文件")

        stem, k, f = HAND
        out = os.path.join(room, "export")
        made = fcedit.export_file(bundle, out, stem, [k])
        if made != 1:
            raise SystemExit(f"导出 {stem} 条目 {k} 应当写出 1 张 PNG，实际 {made} 张")
        png = os.path.join(out, stem, f"{k:02d}_{f:03d}.png")
        im = Image.open(png)
        before = np.asarray(im).copy()
        ImageDraw.Draw(im).rectangle((8, 8, 100, 48), fill=1)
        hand = os.path.join(room, "hand.png")
        im.save(hand, transparency=fcfit.TRANSPARENT)
        index = fcedit.exact_indices(bundle, stem, k, f, hand)
        if index is None or np.array_equal(index, before):
            raise SystemExit("改过的索引 PNG 没有被原样接受")
        fcedit.stage_indices(bundle, stem, k, f, index)
        print(f"原样导入：{stem} 条目 {k} 帧 {f}，cell {bundle.staged[(stem, k)].cells}")

        plain = os.path.join(room, "plain.png")
        Image.new("RGB", (200, 120), (30, 90, 200)).save(plain)
        if fcedit.exact_indices(bundle, stem, k, f, plain) is not None:
            raise SystemExit("普通图片被当成了索引 PNG")

        stem2, k2, f2 = SHOT
        w, h = fcfit.frame_size(bundle.image(stem2, k2), f2)
        y, x = np.mgrid[0:h, 0:w]
        shot = Image.fromarray(np.clip(np.stack([200 * x / w, 255 * y / h,
                                                 180 + 60 * np.sin(x / 13)], -1),
                                       0, 255).astype(np.uint8))
        fit = fcfit.fit(bundle.entries(stem2)[k2], {f2: shot}, placement="cover", outline="opaque")
        bundle.stage(stem2, k2, fit)
        print(f"转换：{stem2} 条目 {k2} 帧 {f2}，{fit.how}，cell {fit.cells}，解码 {fit.bytes} 字节")

        entry2 = bundle.entries(stem2)[k2]
        own = fcfit.owned(bundle.image(stem2, k2))
        kept = fcfit.fit(entry2, {f2: shot}, palette="own", slots=own[:2], placement="cover",
                         outline="opaque")
        drew = {int(v) for v in np.unique(kept.index[f2])} - {fcfit.TRANSPARENT}
        if not drew <= set(own[:2]):
            raise SystemExit(f"限定色槽 {own[:2]} 之外还画了 {sorted(drew - set(own[:2]))}")
        if [list(p) for p in kept.palettes] != [list(p) for p in bundle.image(stem2, k2).palettes]:
            raise SystemExit("「只用条目可设的色槽」改动了调色板")
        print(f"限定色槽 {own[:2]}：只画了 {sorted(drew)}，调色板没动")
        for bad_slots in ([i for i in range(16) if i not in own][:1], []):
            try:
                fcfit.fit(entry2, {f2: shot}, palette="own", slots=bad_slots, placement="cover")
            except fcfit.FitError:
                continue
            raise SystemExit(f"色槽 {bad_slots} 本该被拒绝")

        files = bundle.files_to_write()
        need, free = bundle.room_for(files)
        print(f"要写 {sorted(files)}：还需 {need} 个簇，空闲 {free} 个")
        staged = {key: dict(v.index) for key, v in bundle.staged.items()}
        palettes = {key: [list(p) for p in v.palettes] for key, v in bundle.staged.items()}
        untouched = bundle.entries("FC2630")[0]
        kept = bundle.write(files)

        after = fcedit.Bundle(copy)
        bad = 0
        for (s, e), frames in staged.items():
            img = after.image(s, e)
            for frame, want in frames.items():
                fw, fh, pix = img.indices(frame)
                got = np.array([fcfit.TRANSPARENT if c is None else c for c in pix],
                               np.uint8).reshape(fh, fw)
                if not np.array_equal(got, want):
                    bad += 1
                    print(f"  {s} 条目 {e} 帧 {frame}：写回的像素和暂存的不一致")
            if [list(p) for p in img.palettes] != palettes[(s, e)]:
                bad += 1
                print(f"  {s} 条目 {e}：调色板和暂存的不一致")
        if after.entries("FC2630")[0] != untouched:
            bad += 1
            print("  没动过的 FC2630 变了")
        if not os.path.exists(kept) or os.path.getsize(kept) != os.path.getsize(image):
            bad += 1
            print("  备份镜像不是原来的那一份")
        if bad:
            raise SystemExit(f"{bad} 处不符")
    finally:
        shutil.rmtree(room, ignore_errors=True)
    print("通过：导出、原样导入、转换、写回，再打开镜像读回来都对得上")
    return 0


if __name__ == "__main__":
    sys.exit(run(*sys.argv[1:2]))
