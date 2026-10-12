#!/usr/bin/env python3
"""Map-section door bytes, so each wall set loads its own FC1400 entry.

The engine loads graphic 1400h + the door byte (low nibble = entry of FC1400.BIN).
Windows keeps the door in the wall texture, so the conversion gives FC1400 one entry
per wall set and this writes that set number into every section's door field.

    remap_plain(plain) -> (plain, n)
    remap_blob(data)   -> (encrypted, n)     n sections whose door byte changed
    remap_image(fs, folder) -> (files, n)    every M0*.BIN in an image's folder, written back
    per_wall(fc1400)   -> bool               FC1400 holds one door per wall set
"""
import struct

import fcimage
from ddscrypt import decrypt, encrypt

WALL_AT, DOOR_AT = 0x22, 0x24
NEED = 0x26                                 # section must hold wall, variant, door, stairs
SHARED_DOORS = 5                            # the game's own FC1400: five doors the wall sets share


def sections(plain):
    """(offset, wall) of every map section that names a wall set."""
    if len(plain) < 6:
        return
    _zero, _name, cnt = struct.unpack_from("<3H", plain, 0)
    if cnt == 0 or 6 + 2 * cnt > len(plain):
        return
    for o in struct.unpack_from(f"<{cnt}H", plain, 6):
        if o + NEED > len(plain) or plain[o + WALL_AT] == 0xFF:
            continue
        yield o, plain[o + WALL_AT]


def remap_plain(plain):
    """Copy the wall set into the door byte. Returns (new_plain, how many bytes changed)."""
    out = bytearray(plain)
    n = 0
    for o, wall in sections(plain):
        if out[o + DOOR_AT] != wall:
            out[o + DOOR_AT] = wall
            n += 1
    return bytes(out), n


def remap_blob(data):
    """An encrypted map file with its door bytes remapped. n==0 leaves the bytes as they are."""
    w, plain = decrypt(data)
    new, n = remap_plain(plain)
    if not n:
        return data, 0
    return encrypt(new, w), n


def remap_image(fs, folder):
    """Remap the door bytes of every map file in a FAT image's game folder, writing back the files
    that change. Returns (files written, sections changed)."""
    n_files = n_sec = 0
    d = fs.find(folder)
    if d is None:
        return 0, 0
    for e in fs.read_dir(d["cluster"]):
        name = e["name"].upper()
        if e["is_dir"] or not name.startswith("M0") or not name.endswith(".BIN"):
            continue
        new, n = remap_blob(bytes(fs.read_chain(e["cluster"], e["size"])))
        if not n:
            continue
        fs.replace(f"{folder}/{e['name']}", new)
        n_files += 1
        n_sec += n
    return n_files, n_sec


def per_wall(fc1400):
    """Whether an FC1400.BIN holds a door per wall set, as the Windows-art patch's does, rather than
    the game's five shared ones."""
    return len(fcimage.entries(fc1400)) > SHARED_DOORS
