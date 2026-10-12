#!/usr/bin/env python3
"""Dump DOS MZ header info + relocation table."""
import struct, sys

for path in sys.argv[1:]:
    d = open(path, "rb").read()
    (sig, lastpage, pages, nreloc, hdrpara, minalloc, maxalloc,
     ss, sp, csum, ip, cs, reloff, ovl) = struct.unpack_from("<2sHHHHHHHHHHHHH", d, 0)
    hdr = hdrpara * 16
    imgsz = (pages - 1) * 512 + (lastpage or 512) - hdr
    print(f"== {path}")
    print(f"   file={len(d)}  header={hdr} (0x{hdr:X})  image={imgsz} (0x{imgsz:X})  overlay_bytes={len(d)-hdr-imgsz}")
    print(f"   CS:IP={cs:04X}:{ip:04X} (file 0x{hdr+cs*16+ip:X})   SS:SP={ss:04X}:{sp:04X}")
    print(f"   minalloc={minalloc} para ({minalloc*16} B)  maxalloc={maxalloc}  relocs={nreloc} @0x{reloff:X}")
    print(f"   total load = {imgsz + minalloc*16} B  ({(imgsz + minalloc*16)/1024:.1f} KB)")
    rel = []
    for i in range(nreloc):
        o, s = struct.unpack_from("<HH", d, reloff + i * 4)
        rel.append((s, o))
    segs = sorted({s for s, o in rel})
    print(f"   reloc segments: {len(segs)} -> {[hex(s) for s in segs[:16]]}{' ...' if len(segs)>16 else ''}")
    # which file offsets do relocations point at (useful to avoid patching over them)
    if rel:
        offs = sorted(hdr + s * 16 + o for s, o in rel)
        print(f"   reloc file-offset range: 0x{offs[0]:X} .. 0x{offs[-1]:X}")
    print()
