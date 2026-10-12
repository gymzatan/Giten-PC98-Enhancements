#!/usr/bin/env python3
"""sheet.py out.png cols scale in1.png in2.png ... - contact sheet of captures, labelled."""
import sys

from PIL import Image, ImageDraw

out, cols, scale = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
ims = [Image.open(p).convert("RGB") for p in sys.argv[4:]]
w, h = int(ims[0].width * scale), int(ims[0].height * scale)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * (h + 14)), (40, 40, 40))
d = ImageDraw.Draw(sheet)
for i, (im, path) in enumerate(zip(ims, sys.argv[4:])):
    x, y = i % cols * w, i // cols * (h + 14)
    sheet.paste(im.resize((w, h), Image.NEAREST), (x, y + 14))
    d.text((x + 2, y + 1), path.replace("\\", "/").split("/")[-1], fill=(255, 255, 0))
sheet.save(out)
print(out, sheet.size)
