#!/usr/bin/env python3
import sys, os
from pathlib import Path
from fat12 import open_hdi, Fat12

img, outdir = sys.argv[1], Path(sys.argv[2])
raw, hdr, disk, poff = open_hdi(img)
fs = Fat12(disk, poff)
n = 0
for name, e in fs.walk():
    dest = outdir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(fs.read_chain(e["cluster"], e["size"]) if e["size"] else b"")
    n += 1
print(f"extracted {n} files to {outdir}")
