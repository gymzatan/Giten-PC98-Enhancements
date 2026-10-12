#!/usr/bin/env python3
"""FAT12/FAT16 write support (allocate / replace / create) on top of fat12.Fat12."""
import struct
from fat12 import Fat12


class Fat12W(Fat12):
    def max_cluster(self):
        b = self.bpb
        data_sectors = b.total_sectors - (b.reserved_sectors + b.fat_count * b.sectors_per_fat
                                          + b.root_sectors)
        return 1 + data_sectors // b.sectors_per_cluster        # highest valid cluster number

    def free_clusters(self):
        return [c for c in range(2, self.max_cluster() + 1) if self.get_fat(c) == 0]

    def alloc(self, n):
        free = self.free_clusters()
        if len(free) < n:
            raise RuntimeError(f"need {n} clusters, only {len(free)} free")
        chain = free[:n]
        for i, c in enumerate(chain):
            self.set_fat(c, chain[i + 1] if i + 1 < n else self.eoc)
        return chain

    def free_chain(self, start):
        for c in self.chain(start):
            self.set_fat(c, 0)

    def _write_clusters(self, chain, payload):
        cs = self.bpb.cluster_size
        buf = payload + b"\x00" * ((len(chain) * cs) - len(payload))
        for i, c in enumerate(chain):
            o = self.cluster_off(c)
            self.data[o:o + cs] = buf[i * cs:(i + 1) * cs]

    def overwrite(self, path, payload):
        """Overwrite a file of unchanged length in place, leaving the rest of its clusters as it found
        them, so an image written back with the original content compares byte for byte."""
        e = self.find(path)
        if e is None:
            raise FileNotFoundError(path)
        if len(payload) != e["size"]:
            raise ValueError(f"{path}: {len(payload)} bytes for a {e['size']}-byte file")
        cs = self.bpb.cluster_size
        for i, c in enumerate(self.chain(e["cluster"])):
            part = payload[i * cs:(i + 1) * cs]
            if not part:
                break
            o = self.cluster_off(c)
            self.data[o:o + len(part)] = part

    def replace(self, path, payload):
        """Overwrite an existing file, reallocating clusters if the size changed."""
        e = self.find(path)
        if e is None:
            raise FileNotFoundError(path)
        cs = self.bpb.cluster_size
        need = max(1, (len(payload) + cs - 1) // cs)
        chain = self.chain(e["cluster"]) if e["cluster"] else []
        if len(chain) != need:
            if chain:
                self.free_chain(e["cluster"])
            chain = self.alloc(need)
            struct.pack_into("<H", self.data, e["entry_off"] + 26, chain[0])
        self._write_clusters(chain, payload)
        struct.pack_into("<I", self.data, e["entry_off"] + 28, len(payload))
        return len(chain)

    def remove(self, path):
        """Delete a file: free its clusters and mark its directory entry free, the way DOS does."""
        e = self.find(path)
        if e is None:
            raise FileNotFoundError(path)
        if e["is_dir"]:
            raise IsADirectoryError(path)
        if e["cluster"]:
            self.free_chain(e["cluster"])
        self.data[e["entry_off"]] = 0xE5

    def _dir_entry_slots(self, dir_path):
        """Yield absolute offsets of directory entries for dir_path (None = root)."""
        if dir_path is None:
            base = self.base + self.bpb.root_off
            n = self.bpb.root_entry_count
            for i in range(n):
                yield base + i * 32
        else:
            e = self.find(dir_path)
            if e is None or not e["is_dir"]:
                raise FileNotFoundError(dir_path)
            per = self.bpb.cluster_size // 32
            for c in self.chain(e["cluster"]):
                o = self.cluster_off(c)
                for i in range(per):
                    yield o + i * 32

    def create(self, dir_path, name, payload, attr=0x20):
        """Create (or replace) `name` inside `dir_path` (None = root)."""
        nm, _, ext = name.partition(".")
        raw = nm.upper().ljust(8)[:8].encode("ascii") + ext.upper().ljust(3)[:3].encode("ascii")
        slot = None
        for off in self._dir_entry_slots(dir_path):
            first = self.data[off]
            if first in (0x00, 0xE5):
                if slot is None:
                    slot = off
                if first == 0x00:
                    break
            elif bytes(self.data[off:off + 11]) == raw:
                full = f"{dir_path}/{name}" if dir_path else name
                self.replace(full, payload)
                return
        if slot is None:
            raise RuntimeError(f"no free directory slot in {dir_path}")
        cs = self.bpb.cluster_size
        need = max(1, (len(payload) + cs - 1) // cs)
        chain = self.alloc(need)
        self._write_clusters(chain, payload)
        ent = bytearray(32)
        ent[0:11] = raw
        ent[11] = attr
        struct.pack_into("<H", ent, 22, 0x6000)          # time 12:00:00
        struct.pack_into("<H", ent, 24, 0x38BC)          # date 1998-05-28 (matches siblings)
        struct.pack_into("<H", ent, 26, chain[0])
        struct.pack_into("<I", ent, 28, len(payload))
        self.data[slot:slot + 32] = ent
