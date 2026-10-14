#!/usr/bin/env python3
"""hdigrow.py - an HDI hard disk image grown by whole cylinders at its end, with its one DOS volume, so the volume
gains free clusters. The user (2026-10-13), for the English add-on page: 「空间不够时加大镜像」 - the English reference
disk with the translation, Fixes and Windows Artwork has no free cluster left, and each add-on's file needs one.
The page's enhancement_runtime.js (addonGrow) does the same; tools/enaddons_test.py compares the two.

Only a disk whose volume already fills it is grown, and nothing is guessed:
  - the HDI header's data size is the file's size past the header and its cylinders × heads × sectors × sector size;
  - the partition table (sector 1) holds one entry, the rest of the sector zero, and the entry's end cylinder is the
    disk's last cylinder;
  - the volume is FAT12 with a 16-bit sector count, and it ends within one of its sectors of the disk's end.
The new cylinders are zeros; the header's size and cylinder count, the entry's end cylinder and the BPB's sector
count follow them. The FAT entries of the clusters gained must be zero already, the FAT must have room for them, and
the volume must stay FAT12 (fewer than 4085 clusters). Nothing else of the image changes.

    grow(raw, more) -> (a new raw, cylinders added): at least `more` clusters more, all free
    hdigrow.py IMAGE MORE [OUT]
"""
import struct
import sys


class GrowError(ValueError):
    pass


def u16(b, at):
    return struct.unpack_from("<H", b, at)[0]


def u32(b, at):
    return struct.unpack_from("<I", b, at)[0]


def volume(raw):
    """{hdr, sect, spt, heads, cyls, part, entry}: the HDI header's fields, the volume's offset in the disk and the
    partition entry's offset."""
    hdr, sect, spt, heads, cyls = u32(raw, 8), u32(raw, 16), u32(raw, 20), u32(raw, 24), u32(raw, 28)
    entry = hdr + sect
    lba = (u16(raw, entry + 10) * heads + raw[entry + 9]) * spt + raw[entry + 8]
    return {"hdr": hdr, "sect": sect, "spt": spt, "heads": heads, "cyls": cyls, "part": lba * sect, "entry": entry}


def fat(raw, v):
    """The volume's BPB fields and cluster bounds."""
    b = v["hdr"] + v["part"]
    bps, spc, reserved, fats, root = u16(raw, b + 11), raw[b + 13], u16(raw, b + 14), raw[b + 16], u16(raw, b + 17)
    total16, spf = u16(raw, b + 19), u16(raw, b + 22)
    overhead = reserved + fats * spf + (root * 32 + bps - 1) // bps
    return {"base": b, "bps": bps, "spc": spc, "reserved": reserved, "spf": spf, "total": total16,
            "overhead": overhead, "max": 1 + (total16 - overhead) // spc}


def fat_entry(raw, f, c):
    o = f["base"] + f["reserved"] * f["bps"] + c + (c >> 1)
    val = raw[o] | (raw[o + 1] << 8)
    return (val >> 4) if (c & 1) else (val & 0xFFF)


def free_clusters(raw, f):
    return sum(1 for c in range(2, f["max"] + 1) if fat_entry(raw, f, c) == 0)


def check(raw):
    """GrowError unless the image is one this module grows."""
    v = volume(raw)
    size = len(raw) - v["hdr"]
    if u32(raw, 12) != size or size != v["cyls"] * v["heads"] * v["spt"] * v["sect"]:
        raise GrowError("the HDI header's size does not match the image")
    if any(raw[v["entry"] + 32:v["hdr"] + 2 * v["sect"]]):
        raise GrowError("the disk has more than one partition")
    if u16(raw, v["entry"] + 14) != v["cyls"] - 1:
        raise GrowError("the partition does not reach the disk's last cylinder")
    f = fat(raw, v)
    if f["total"] == 0 or (f["total"] - f["overhead"]) // f["spc"] >= 4085:
        raise GrowError("the volume is not FAT12 with a 16-bit sector count")
    if not 0 <= size - (v["part"] + f["total"] * f["bps"]) < f["bps"]:
        raise GrowError("the volume does not end at the disk's end")
    return v, f


def grow(raw, more):
    """raw grown by the fewest cylinders that give its volume at least `more` (> 0) new clusters, all free."""
    v, f = check(raw)
    cyl = v["heads"] * v["spt"] * v["sect"]
    size = len(raw) - v["hdr"]
    for k in range(1, 1 << 16):
        total = (size + k * cyl - v["part"]) // f["bps"]
        if total > 0xFFFF or (total - f["overhead"]) // f["spc"] >= 4085:
            raise GrowError(f"the volume cannot gain {more} more clusters and stay FAT12")
        top = 1 + (total - f["overhead"]) // f["spc"]
        if top + (top >> 1) + 1 >= f["spf"] * f["bps"]:
            raise GrowError("the FAT has no room for more clusters")
        if top - f["max"] >= more:
            break
    if any(fat_entry(raw, f, c) for c in range(f["max"] + 1, top + 1)):
        raise GrowError("the FAT's entries past the volume are not empty")
    out = bytearray(raw) + bytes(k * cyl)
    struct.pack_into("<I", out, 12, size + k * cyl)
    struct.pack_into("<I", out, 28, v["cyls"] + k)
    struct.pack_into("<H", out, v["entry"] + 14, v["cyls"] + k - 1)
    struct.pack_into("<H", out, f["base"] + 19, total)
    return out, k


def main(argv):
    raw = bytearray(open(argv[0], "rb").read())
    out, k = grow(raw, int(argv[1]))
    v, f = check(out)
    print(f"{argv[0]}: +{k} cylinders, {free_clusters(out, f)} free clusters of {f['bps'] * f['spc']} bytes "
          f"(was {free_clusters(raw, fat(raw, volume(raw)))})")
    if len(argv) > 2:
        with open(argv[2], "wb") as fh:
            fh.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
