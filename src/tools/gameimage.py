"""The game's data files as they sit in a disk image, and the way one is written back.

The image says what the game's numbers are right now; what they were when the game shipped, and what
every record is called, the editor carries with it (tools/gamebase.json).

Writing an image keeps the one it replaces: the old bytes are saved beside it under the same name
with the time of the write in it, and the new image takes the original name, so whatever launches
the game keeps launching it.
"""
import os
import time
import records
from fat12 import open_hdi
from fat12w import Fat12W
DIR = 'DDS98'
BACKUP_TIME = '%Y%m%d-%H%M%S'

class ImageError(ValueError):
    pass

class GameImage:
    """One disk image, open for reading and (through save()) for writing."""

    def __init__(self, path):
        self.path = path
        try:
            self.raw, self.header, self.disk, part = open_hdi(path)
            self.fs = Fat12W(self.disk, part)
            self.files = {}
            for name, entry in self.fs.walk():
                parts = name.upper().split('/')
                if len(parts) == 2 and parts[0] == DIR and parts[1].endswith('.BIN'):
                    self.files[parts[1][:-4]] = entry
        except Exception as e:
            raise ImageError(f'{os.path.basename(path)}: cannot read this image — {e}') from None
        if 'ET0001' not in self.files or 'ET0004' not in self.files:
            raise ImageError(f'{os.path.basename(path)}: missing {DIR}\\ET0001.BIN，这不是偽典・女神転生的镜像')
        self.plains = {}

    def stems(self, prefix=''):
        return sorted((s for s in self.files if s.startswith(prefix)))

    def blob(self, stem):
        """The file as it is stored, still encrypted."""
        e = self.files.get(stem)
        if e is None:
            raise ImageError(f'{os.path.basename(self.path)}: missing {DIR}\\{stem}.BIN')
        return self.fs.read_chain(e['cluster'], e['size'])

    def plain(self, stem):
        """The file decrypted, kept so that edits to it accumulate."""
        if stem not in self.plains:
            self.plains[stem] = records.plain_of(self.blob(stem))
        return self.plains[stem]

    def save(self, stems, path=None, backup=True):
        """Write the given files back and put the image in place of the one on disk.

        Returns the name the old image was kept under, or None when it was not kept (a build that
        has just written the image itself asks for no backup of what it wrote a moment ago)."""
        if not stems:
            return None
        path = path or self.path
        for stem in stems:
            self.fs.overwrite(f'{DIR}/{stem}.BIN', records.encode(self.plains[stem]))
        out = bytearray(self.raw)
        out[self.header:] = self.disk
        kept = None
        if backup and os.path.exists(path):
            kept = backup_name(path)
            os.replace(path, kept)
        tmp = path + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(bytes(out))
        os.replace(tmp, path)
        return kept

def backup_name(path, when=None):
    """<image>.<date-time>.bak, beside the image it is a copy of, and never the name of one that is
    already there: two writes within the same second must not cost the older image."""
    stamp = time.strftime(BACKUP_TIME, time.localtime(when))
    first = f'{path}.{stamp}.bak'
    name, n = (first, 1)
    while os.path.exists(name):
        n += 1
        name = f'{first}.{n}'
    return name
