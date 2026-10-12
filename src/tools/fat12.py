#!/usr/bin/env python3
"""FAT12/FAT16 reader for PC-98 HDI images (1024-byte sectors, partitioned).

The FAT width is not stored anywhere reliable, so it is derived the standard way
from the cluster count: fewer than 4085 clusters is FAT12, otherwise FAT16.
Planets of Dragon is FAT12; Giten Megami Tensei is FAT16.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class Bpb:
    bytes_per_sector: int
    sectors_per_cluster: int
    reserved_sectors: int
    fat_count: int
    root_entry_count: int
    total_sectors: int
    sectors_per_fat: int

    @property
    def root_sectors(self) -> int:
        return (self.root_entry_count * 32 + self.bytes_per_sector - 1) // self.bytes_per_sector

    @property
    def fat_off(self) -> int:
        return self.reserved_sectors * self.bytes_per_sector

    @property
    def root_off(self) -> int:
        return (self.reserved_sectors + self.fat_count * self.sectors_per_fat) * self.bytes_per_sector

    @property
    def data_off(self) -> int:
        return self.root_off + self.root_sectors * self.bytes_per_sector

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster


class Fat12:
    def __init__(self, data: bytearray, part_off: int):
        self.data = data
        self.base = part_off
        b = bytes(data[part_off:part_off + 64])
        self.bpb = Bpb(
            bytes_per_sector=struct.unpack_from("<H", b, 11)[0],
            sectors_per_cluster=b[13],
            reserved_sectors=struct.unpack_from("<H", b, 14)[0],
            fat_count=b[16],
            root_entry_count=struct.unpack_from("<H", b, 17)[0],
            total_sectors=(struct.unpack_from("<H", b, 19)[0]
                           or struct.unpack_from("<I", b, 32)[0]),
            sectors_per_fat=struct.unpack_from("<H", b, 22)[0],
        )
        bp = self.bpb
        data_sectors = bp.total_sectors - (bp.reserved_sectors + bp.fat_count * bp.sectors_per_fat
                                           + bp.root_sectors)
        self.fat_bits = 12 if data_sectors // bp.sectors_per_cluster < 4085 else 16
        self.eoc = 0xFFF if self.fat_bits == 12 else 0xFFFF       # end-of-chain marker
        self.first_reserved = self.eoc - 0xF                         # 0xFF0 / 0xFFF0

    def _fat_bytes(self, idx: int = 0) -> memoryview:
        o = self.base + self.bpb.fat_off + idx * self.bpb.sectors_per_fat * self.bpb.bytes_per_sector
        return memoryview(self.data)[o:o + self.bpb.sectors_per_fat * self.bpb.bytes_per_sector]

    def get_fat(self, cluster: int) -> int:
        fat = self._fat_bytes()
        if self.fat_bits == 16:
            return fat[cluster * 2] | (fat[cluster * 2 + 1] << 8)
        off = cluster + (cluster >> 1)
        val = fat[off] | (fat[off + 1] << 8)
        return (val >> 4) if (cluster & 1) else (val & 0x0FFF)

    def set_fat(self, cluster: int, value: int) -> None:
        for i in range(self.bpb.fat_count):
            fat = self._fat_bytes(i)
            if self.fat_bits == 16:
                fat[cluster * 2] = value & 0xFF
                fat[cluster * 2 + 1] = (value >> 8) & 0xFF
                continue
            off = cluster + (cluster >> 1)
            cur = fat[off] | (fat[off + 1] << 8)
            if cluster & 1:
                cur = (cur & 0x000F) | ((value & 0x0FFF) << 4)
            else:
                cur = (cur & 0xF000) | (value & 0x0FFF)
            fat[off] = cur & 0xFF
            fat[off + 1] = (cur >> 8) & 0xFF

    def cluster_off(self, cluster: int) -> int:
        return self.base + self.bpb.data_off + (cluster - 2) * self.bpb.cluster_size

    def chain(self, start: int) -> list[int]:
        out, c, seen = [], start, set()
        while 2 <= c < self.first_reserved and c not in seen:
            seen.add(c)
            out.append(c)
            c = self.get_fat(c)
        return out

    def read_chain(self, start: int, size: int | None = None) -> bytes:
        buf = bytearray()
        for c in self.chain(start):
            o = self.cluster_off(c)
            buf += self.data[o:o + self.bpb.cluster_size]
        return bytes(buf[:size]) if size is not None else bytes(buf)

    def read_dir(self, start_cluster: int | None) -> list[dict]:
        """start_cluster None = root directory."""
        if start_cluster is None:
            o = self.base + self.bpb.root_off
            raw = bytes(self.data[o:o + self.bpb.root_sectors * self.bpb.bytes_per_sector])
            locs = [(o + i * 32) for i in range(len(raw) // 32)]
        else:
            raw = self.read_chain(start_cluster)
            locs = []
            per = self.bpb.cluster_size // 32
            for ci, c in enumerate(self.chain(start_cluster)):
                for i in range(per):
                    locs.append(self.cluster_off(c) + i * 32)
        out = []
        for i in range(len(raw) // 32):
            e = raw[i * 32:(i + 1) * 32]
            if e[0] == 0x00:
                break
            if e[0] == 0xE5 or (e[11] & 0x0F) == 0x0F:
                continue
            name = e[0:8].decode("shift_jis", "replace").rstrip()
            ext = e[8:11].decode("shift_jis", "replace").rstrip()
            out.append({
                "name": f"{name}.{ext}" if ext else name,
                "attr": e[11],
                "cluster": struct.unpack_from("<H", e, 26)[0],
                "size": struct.unpack_from("<I", e, 28)[0],
                "is_dir": bool(e[11] & 0x10),
                "entry_off": locs[i],
            })
        return out

    def walk(self, cluster=None, path=""):
        for e in self.read_dir(cluster):
            if e["name"] in (".", ".."):
                continue
            full = f"{path}/{e['name']}" if path else e["name"]
            if e["is_dir"]:
                yield from self.walk(e["cluster"], full)
            else:
                yield full, e

    def find(self, path: str):
        parts = path.strip("/").split("/")
        cur = None
        for i, p in enumerate(parts):
            ents = {e["name"].upper(): e for e in self.read_dir(cur)}
            e = ents.get(p.upper())
            if e is None:
                return None
            if i == len(parts) - 1:
                return e
            cur = e["cluster"]
        return None

    def write_file_inplace(self, entry: dict, payload: bytes) -> None:
        """Overwrite file content, reusing its cluster chain (payload must fit)."""
        chain = self.chain(entry["cluster"])
        cap = len(chain) * self.bpb.cluster_size
        if len(payload) > cap:
            raise ValueError(f"payload {len(payload)} > chain capacity {cap}")
        buf = payload + b"\x00" * (cap - len(payload))
        for i, c in enumerate(chain):
            o = self.cluster_off(c)
            self.data[o:o + self.bpb.cluster_size] = buf[i * self.bpb.cluster_size:(i + 1) * self.bpb.cluster_size]
        struct.pack_into("<I", self.data, entry["entry_off"] + 28, len(payload))


def open_hdi(path):
    raw = bytearray(open(path, "rb").read())
    hdr = struct.unpack_from("<I", raw, 8)[0]
    disk = raw[hdr:]
    sect_sz = struct.unpack_from("<I", raw, 16)[0]
    spt = struct.unpack_from("<I", raw, 20)[0]
    heads = struct.unpack_from("<I", raw, 24)[0]
    # PC-98 partition table in sector 1, which is not always 512 bytes in: dumps of this game are
    # about as often written with 256-byte sectors as with 512-byte ones
    pt = disk[sect_sz:sect_sz + 32]
    st_sect, st_head = pt[8], pt[9]
    st_cyl = struct.unpack_from("<H", pt, 10)[0]
    lba = (st_cyl * heads + st_head) * spt + st_sect
    return raw, hdr, disk, lba * sect_sz


if __name__ == "__main__":
    import sys
    raw, hdr, disk, poff = open_hdi(sys.argv[1])
    fs = Fat12(disk, poff)
    print(f"# part_off=0x{poff:X} bps={fs.bpb.bytes_per_sector} spc={fs.bpb.sectors_per_cluster} "
          f"clsz={fs.bpb.cluster_size} root_ents={fs.bpb.root_entry_count} data_off=0x{fs.bpb.data_off:X}")
    total = 0
    for name, e in fs.walk():
        print(f"{e['size']:>9}  clus={e['cluster']:<5} {name}")
        total += e["size"]
    print(f"# total {total} bytes")
