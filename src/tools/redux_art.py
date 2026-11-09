"""The Windows artwork (tools/webpayload.art_part) for a translation that redraws pictures of its own.

delacannon's translation (tools/redux_translations.py) letters the status labels (FC0000 entry 2) and the demon
lists' table headers (FC0110 entry 11) in English or Spanish; the artwork redraws the screen frame (FC0000 entry 0),
the compass plate (FC0000 entry 2 frame 111) and the compass needle (FC0110 entry 9). An FC file is a list of
entries (tools/fcimage.py), so the two go together entry by entry: an entry only one side changes is that side's,
and FC0000 entry 2, which both change in different frames with the same palette, is the artwork's with the
translation's frames encoded into it (tools/fcencode.encode_entry) - every frame checked pixel by pixel.

merged(jp, translated, art) -> the file; alternatives(art_files, translations) -> {file: [(the translation's
file, the merged file)]} for every artwork file a translation changes.
"""
import struct

import fcencode
import fcimage


class MergeError(ValueError):
    pass


def _container(entries):
    return b"".join(struct.pack("<I", len(e)) + e for e in entries)


def _palette(entry):
    (n_layout,) = struct.unpack_from("<H", entry, 0)
    (npal,) = struct.unpack_from("<H", entry, 2 + n_layout + 2)
    return entry[2 + n_layout:2 + n_layout + 6 + 32 * npal]


def _frames(entry):
    img = fcimage.Image(entry)
    return img, {f: img.indices(f) for f in range(len(img.frames))}


def merged(jp, translated, art):
    a, t, w = fcimage.entries(jp), fcimage.entries(translated), fcimage.entries(art)
    if not len(a) == len(t) == len(w):
        raise MergeError("the files have different numbers of entries")
    out = []
    for k, (ja, tr, wa) in enumerate(zip(a, t, w)):
        if tr == ja or wa == ja:
            out.append(wa if tr == ja else tr)
            continue
        jimg, jf = _frames(ja)
        timg, tf = _frames(tr)
        wimg, wf = _frames(wa)
        if not len(jf) == len(tf) == len(wf):
            raise MergeError(f"entry {k}: the sides have different frames")
        if not _palette(ja) == _palette(tr) == _palette(wa):
            raise MergeError(f"entry {k}: a side changes the palette")
        art_frames = {f for f in wf if wf[f] != jf[f]}
        tr_frames = {f for f in tf if tf[f] != jf[f]}
        if art_frames & tr_frames:
            raise MergeError(f"entry {k}: the translation and the artwork both redraw frames {sorted(art_frames & tr_frames)}")
        # the translation's frames go into the artwork's entry: the artwork's comes from this project's encoder,
        # while a translation's may hold cells no frame uses (delacannon's FC0000 entry 2 does), which the
        # encoder cannot keep
        offs = fcencode.frame_offsets(wimg.layout)
        edits = {}
        for f in tr_frames:
            _w, _h, pix = tf[f]
            edits[offs[f]] = [None if v is None else int(v) for v in pix]
        entry = fcencode.encode_entry(wa, edits)
        _m, mf = _frames(entry)
        want = {f: (tf[f] if f in tr_frames else wf[f]) for f in tf}
        if mf != want:
            raise MergeError(f"entry {k}: the merged entry does not show both sides' frames")
        out.append(entry)
    return _container(out)


def alternatives(jp_files, art_files, translations):
    """{file: [(the translation's file, merged)]} for the artwork files `translations` ({key: {name: bytes}}) change."""
    out = {}
    for key, files in translations.items():
        for name, art in art_files.items():
            tr, jp = files.get(name), jp_files.get(name)
            if tr is None or jp is None or tr == jp:
                continue
            pair = (tr, merged(jp, tr, art))
            if pair not in out.setdefault(name, []):
                out[name].append(pair)
    return out
