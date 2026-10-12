#!/usr/bin/env python3
"""The DDS98 data-file cipher, as implemented in overlay 20 (fno_ctrl.c).

    ov20:0000  set_key(w)    state = (w & 0xFF) ^ (w >> 8)
    ov20:0018  getc_x(fp)    c = next byte; p = c ^ state; state = c
    ov20:0048  getw_x(fp)    lo = getc_x(); hi = getc_x(); return hi<<8 | lo

A file starts with a plain little-endian word; 1603:9458 passes it to set_key
and also uses it as the byte count of the rest of the file. Every following byte
is XORed with the previous *ciphertext* byte, so encrypting is the inverse chain:
c = p ^ state; state = c.
"""
import struct
import sys


def decrypt(data):
    """-> (header_word, plaintext of everything after the header)."""
    w = struct.unpack_from("<H", data, 0)[0]
    state = (w & 0xFF) ^ (w >> 8)
    out = bytearray(len(data) - 2)
    for i, c in enumerate(data[2:]):
        out[i] = c ^ state
        state = c
    return w, bytes(out)


def encrypt(plain, header_word=None):
    """Inverse of decrypt. The game treats the header as the remaining length."""
    w = len(plain) if header_word is None else header_word
    state = (w & 0xFF) ^ (w >> 8)
    out = bytearray(struct.pack("<H", w))
    for p in plain:
        c = p ^ state
        out.append(c)
        state = c
    return bytes(out)


if __name__ == "__main__":
    src = open(sys.argv[1], "rb").read()
    w, plain = decrypt(src)
    print(f"header word {w} (file {len(src)} B, payload {len(plain)} B)")
    if len(sys.argv) > 2:
        open(sys.argv[2], "wb").write(plain)
