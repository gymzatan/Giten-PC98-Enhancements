#!/usr/bin/env python3
"""Map door bytes follow the wall set. Run from work/."""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import mapdoors  # noqa: E402
from ddscrypt import decrypt  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "DDS98")
FAILS = []


def expect(ok, what):
    if not ok:
        FAILS.append(what)
        print("FAIL", what)


def main():
    files = sorted(glob.glob(os.path.join(SRC, "M0*.BIN")))
    expect(len(files) > 50, f"map files present ({len(files)})")
    total = 0
    for path in files:
        data = open(path, "rb").read()
        new, n = mapdoors.remap_blob(data)
        total += n
        w, plain = decrypt(new)
        leftover = [(o, wall, plain[o + mapdoors.DOOR_AT])
                    for o, wall in mapdoors.sections(plain)
                    if plain[o + mapdoors.DOOR_AT] != wall]
        expect(not leftover, f"{os.path.basename(path)}: door still != wall after remap")
        again, n2 = mapdoors.remap_blob(new)
        expect(n2 == 0 and again == new, f"{os.path.basename(path)}: remap not idempotent")
        expect(decrypt(new)[0] == w, f"{os.path.basename(path)}: header word kept")
    expect(total > 0, f"original maps actually used shared door ids ({total} sections)")
    print(f"{len(files)} maps, {total} sections remapped")
    print("OK" if not FAILS else f"{len(FAILS)} failures")
    return 1 if FAILS else 0


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
