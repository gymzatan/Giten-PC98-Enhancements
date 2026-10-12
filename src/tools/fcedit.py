"""素材编辑器: the game's pictures taken out of a disk image, replaced, and written back.

    fcedit.py [IMAGE.hdi]

Everything it needs it reads from the image it opens: the FC files hold the pictures, each entry its
own cell dictionaries, layout and palettes (tools/fcimage.py). A frame is exported as an indexed PNG
in the entry's colours, and a picture put back into a frame goes through tools/fcfit.py - placed in
the frame, the entry's own palette slots fitted to it, ordered dithering on the cell grid, and the
cells chosen together when the entry's dictionary cannot hold them. Writing back re-encodes the
entries (tools/fcencode.py), rebuilds the FC files and puts the image in place of the one on disk,
keeping the old one beside it.

Nothing of work/ travels with it, so the exe built by tools/mkfcedit.py opens any dump of the game,
Japanese or Chinese.
"""
import ctypes
import json
import os
import queue
import re
import struct
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
from PIL import Image, ImageTk
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcencode
import fcfit
import fcimage
import gfx
from fat12 import open_hdi
from fat12w import Fat12W
TITLE = 'Giten Redux — Artwork Editor'
DIR = 'DDS98'
IMAGE_TYPES = [('PC-98 HDI image', '*.hdi'), ('All files', '*.*')]
PICTURE_TYPES = [('Picture', '*.png *.bmp *.jpg *.jpeg *.gif *.webp'), ('All files', '*.*')]
BACKUP_TIME = '%Y%m%d-%H%M%S'
PLACE_TEXT = [('contain', 'Contain (black margins)'), ('cover', 'Cover and crop'), ('stretch', 'Stretch')]
OUTLINE_TEXT = [('picture', 'Picture transparency'), ('frame', 'Keep the frame outline'), ('opaque', 'Opaque frame')]
STRENGTH_TEXT = [('', 'Automatic (1.0, then 0.75)'), ('1.0', '1.0 Full dithering'), ('0.75', '0.75'), ('0.5', '0.5'), ('0.25', '0.25'), ('0', '0 No dithering')]
VIEW_BG = '#181820'

class EditError(ValueError):
    pass

def backup_name(path, when=None):
    """<image>.<date-time>.bak beside the image, never the name of one already there."""
    first = f'{path}.{time.strftime(BACKUP_TIME, time.localtime(when))}.bak'
    name, n = (first, 1)
    while os.path.exists(name):
        n += 1
        name = f'{first}.{n}'
    return name

class Bundle:
    """One disk image and the pictures staged for it."""

    def __init__(self, path):
        self.path = path
        try:
            self.raw, self.header, self.disk, part = open_hdi(path)
            self.fs = Fat12W(self.disk, part)
        except Exception as e:
            raise EditError(f'{os.path.basename(path)}: cannot read this image — {e}') from None
        self.names = []
        for name, _entry in self.fs.walk():
            parts = name.upper().split('/')
            if len(parts) == 2 and parts[0] == DIR and re.fullmatch('FC[0-9A-F]{4}\\.BIN', parts[1]):
                self.names.append(parts[1][:-4])
        self.names.sort()
        if not self.names:
            raise EditError(f'{os.path.basename(path)}: missing {DIR}\\FC*.BIN; this is not a supported game image')
        self._entries = {}
        self.staged = {}

    def entries(self, stem):
        if stem not in self._entries:
            e = self.fs.find(f'{DIR}/{stem}.BIN')
            blob = bytes(self.fs.read_chain(e['cluster'], e['size']))
            try:
                self._entries[stem] = fcimage.entries(blob)
            except Exception as ex:
                raise EditError(f'{stem}.BIN: cannot read its entries — {ex}') from None
        return self._entries[stem]

    def image(self, stem, k):
        return fcimage.Image(self.entries(stem)[k])

    def stage(self, stem, k, fit):
        self.staged[stem, k] = fit

    def drop(self, stem, k=None):
        for key in [key for key in self.staged if key[0] == stem and (k is None or key[1] == k)]:
            del self.staged[key]

    def files_to_write(self):
        """{FC file name: rebuilt bytes} for every file holding staged pictures."""
        out = {}
        for stem in sorted({s for s, _k in self.staged}):
            entries = list(self.entries(stem))
            for (s, k), fit in sorted(self.staged.items()):
                if s == stem:
                    entries[k] = fcfit.apply(entries[k], fit)
            out[stem] = b''.join((struct.pack('<I', len(e)) + e for e in entries))
        return out

    def room_for(self, files):
        """(clusters needed, clusters free) once the files these pictures grow are written."""
        cs = self.fs.bpb.cluster_size
        need = 0
        for stem, blob in files.items():
            e = self.fs.find(f'{DIR}/{stem}.BIN')
            have = len(self.fs.chain(e['cluster'])) if e['cluster'] else 0
            need += max(1, (len(blob) + cs - 1) // cs) - have
        return (need, len(self.fs.free_clusters()))

    def write(self, files):
        """Write the files into the image and put it in place of the one on disk; returns the backup."""
        need, free = self.room_for(files)
        if need > free:
            raise EditError(f'Insufficient image space: needs {need - free} clusters (each {self.fs.bpb.cluster_size} bytes), but free space is only {free}')
        for stem, blob in files.items():
            self.fs.replace(f'{DIR}/{stem}.BIN', blob)
        out = bytearray(self.raw)
        out[self.header:] = self.disk
        tmp = self.path + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(bytes(out))
        kept = backup_name(self.path)
        os.replace(self.path, kept)
        os.replace(tmp, self.path)
        self._entries = {}
        self.staged = {}
        return kept

def frame_image(bundle, stem, k, f):
    """The frame as an RGB image: the staged picture where there is one, else the game's own."""
    img = bundle.image(stem, k)
    fit = bundle.staged.get((stem, k))
    if fit is not None and f in fit.index:
        return fcfit.preview(fit, img, f)
    if fit is not None:
        words = fit.palettes[0]
        table = [fcimage.pc98_rgb(v) for v in words] + [(40, 40, 48)]
        w, h, pix = img.indices(f)
        out = Image.new('RGB', (w, h))
        out.putdata([table[16 if c is None else c] for c in pix])
        return out
    png = gfx.frame_png(img, f)
    return png.convert('RGB') if png is not None else Image.new('RGB', (8, 8), (40, 40, 48))

def shared_with(img, f):
    """The frame whose picture this one repeats, or None."""
    offs = fcencode.frame_offsets(img.layout) if len(img.layout) >= 4 else []
    if f >= len(offs):
        return None
    owner = offs.index(offs[f])
    return None if owner == f else owner

def palette_words(bundle, stem, k):
    """The colours the entry will be drawn in: a staged fit's, else the entry's own palette 0."""
    img = bundle.image(stem, k)
    fit = bundle.staged.get((stem, k))
    if fit is not None:
        return fit.palettes[0]
    return list(img.palettes[0]) if img.palettes else [0] * 16

def indexed_png(bundle, stem, k, f):
    """The frame as an indexed PNG in the colours it is drawn in, a staged picture included."""
    img = bundle.image(stem, k)
    fit = bundle.staged.get((stem, k))
    w, h = fcfit.frame_size(img, f)
    if not w or not h:
        return None
    im = Image.new('P', (w, h))
    im.putpalette(gfx.palette_rgb(palette_words(bundle, stem, k)))
    if fit is not None and f in fit.index:
        im.putdata([int(v) for v in fit.index[f].reshape(-1)])
    else:
        im.putdata([gfx.TRANSPARENT if c is None else c for c in img.indices(f)[2]])
    return im

def exact_indices(bundle, stem, k, f, path):
    """The pixels of a PNG that is this frame exported and edited - an indexed PNG of the frame's size
    whose palette is the one it was exported with. Anything else is a picture to be converted, and
    comes back as None."""
    img = bundle.image(stem, k)
    w, h = fcfit.frame_size(img, f)
    try:
        im = Image.open(path)
        if im.mode != 'P' or im.size != (w, h):
            return None
        if not gfx.palette_compatible(im.getpalette() or [], gfx.palette_rgb(palette_words(bundle, stem, k))):
            return None
        data = list(im.get_flattened_data())
    except (OSError, ValueError):
        return None
    if any((v > gfx.TRANSPARENT for v in data)):
        return None
    return np.array(data, np.uint8).reshape(h, w)

def stage_indices(bundle, stem, k, f, index):
    """Stage one frame's own pixels, keeping whatever the entry already has staged."""
    img = bundle.image(stem, k)
    fit = bundle.staged.get((stem, k))
    merged = dict(fit.index) if fit else {}
    merged[f] = index
    counts, size = fcencode.cell_cost(bundle.entries(stem)[k], fcfit.edits_of(img, merged))
    if not fcfit.fits(counts, size):
        raise EditError(f'Picture exceeds capacity: cells {max(counts.values())} / {fcfit.CELL_LIMIT}, decoded {size} / {fcfit.MEMORY_CAP} bytes')
    palettes = fit.palettes if fit else [list(p) for p in img.palettes]
    bundle.stage(stem, k, fcfit.Fit(palettes, merged, 'Keep indexed PNG pixels unchanged', counts, size, ['The PNG palette matches this entry; indexed pixels are used unchanged.']))

def export_file(bundle, out, stem, keys=None):
    """<out>/<stem>/<entry>_<frame>.png for every frame of the entries `keys` (all of them when it is
    None), with manifest.json beside them; returns how many PNG files were written."""
    folder = os.path.join(out, stem)
    os.makedirs(folder, exist_ok=True)
    manifest = {'file': stem + '.BIN', 'image': os.path.basename(bundle.path), 'entries': []}
    made = 0
    for k, entry in enumerate(bundle.entries(stem)):
        img = fcimage.Image(entry)
        fit = bundle.staged.get((stem, k))
        info = {'entry': k, 'palettes': [[f'{v:04X}' for v in p] for p in (fit.palettes if fit else img.palettes)], 'sets_colours': fcfit.owned(img), 'edited': fit is not None, 'frames': []}
        if keys is None or k in keys:
            for f in range(len(img.frames)):
                owner = shared_with(img, f)
                name = f'{k:02d}_{(owner if owner is not None else f):03d}.png'
                x, y = fcfit.frame_origin(img, f)
                w, h = fcfit.frame_size(img, f)
                info['frames'].append({'x': x, 'y': y, 'w': w, 'h': h, 'png': name})
                if owner is not None:
                    continue
                im = indexed_png(bundle, stem, k, f)
                if im is not None:
                    im.save(os.path.join(folder, name), transparency=gfx.TRANSPARENT)
                    made += 1
        manifest['entries'].append(info)
    with open(os.path.join(folder, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)
    return made

class Worker:
    """A conversion running beside the window, reporting through a queue."""

    def __init__(self, fn, on_done, on_line, root):
        self.q = queue.Queue()
        self.on_done, self.on_line, self.root = (on_done, on_line, root)
        self.thread = threading.Thread(target=self._run, args=(fn,), daemon=True)
        self.thread.start()
        self.root.after(50, self._poll)

    def _run(self, fn):
        try:
            self.q.put(('done', fn(lambda text: self.q.put(('line', text)))))
        except Exception as e:
            self.q.put(('error', e))

    def _poll(self):
        if not self.root.winfo_exists():
            return
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == 'line':
                    self.on_line(payload)
                else:
                    self.on_done(kind, payload)
                    return
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

class Convert(tk.Toplevel):
    """Turn one picture into one frame: the options, what it costs, and the result side by side."""

    def __init__(self, app, stem, k, f, path):
        super().__init__(app)
        self.app, self.stem, self.k, self.f, self.path = (app, stem, k, f, path)
        self.img = app.bundle.image(stem, k)
        self.source = Image.open(path)
        self.source.load()
        self.fit = None
        self.title(f'{stem} entry {k} frame {f} ← {os.path.basename(path)}')
        self.transient(app)
        self.resizable(False, False)
        w, h = fcfit.frame_size(self.img, f)
        top = ttk.Frame(self, padding=8)
        top.pack(fill='x')
        ttk.Label(top, text=f'画面 {w}×{h} picture {self.source.width}×{self.source.height}').pack(side='left')
        opts = ttk.Frame(self, padding=(8, 0))
        opts.pack(fill='x')
        self.place = tk.StringVar(value='cover' if self.source.size != (w, h) else 'stretch')
        self.palette = tk.StringVar(value='auto')
        self.outline = tk.StringVar(value='picture' if self._has_alpha() else 'opaque')
        self.strength = tk.StringVar(value='')
        self.slots = tk.StringVar(value='')
        self._row(opts, 'Placement', self.place, PLACE_TEXT)
        self._row(opts, 'Palette', self.palette, [('auto', 'Refit the colors of owned slots'), ('own', 'Use owned slots without changing colors'), ('keep', "Keep the entry's 16 colors")])
        self._row(opts, 'Outline', self.outline, OUTLINE_TEXT)
        self._row(opts, 'Dithering', self.strength, STRENGTH_TEXT)
        self._text_row(opts, 'Allowed slots', self.slots, "Empty allows every slot in the selected mode. '0 4' uses black and white, dithering gray.")
        mid = ttk.Frame(self, padding=8)
        mid.pack(fill='both', expand=True)
        self.view_source = tk.Label(mid, bg=VIEW_BG, bd=0)
        self.view_source.grid(row=0, column=0, padx=(0, 6))
        self.view_result = tk.Label(mid, bg=VIEW_BG, bd=0)
        self.view_result.grid(row=0, column=1)
        ttk.Label(mid, text='Source (placed)').grid(row=1, column=0)
        ttk.Label(mid, text='Converted game picture').grid(row=1, column=1)
        self.report = tk.Text(self, height=6, width=92, wrap='word', relief='flat', background='#f4f4f7')
        self.report.pack(fill='x', padx=8)
        self.report.configure(state='disabled')
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill='x')
        self.b_run = ttk.Button(bar, text='Conversion preview', command=self.run)
        self.b_run.pack(side='left')
        self.b_ok = ttk.Button(bar, text='Use this result', command=self.accept, state='disabled')
        self.b_ok.pack(side='left', padx=6)
        ttk.Button(bar, text='Cancel', command=self.destroy).pack(side='left')
        self.same = tk.BooleanVar(value=False)
        if len(self._own_frames()) > 1:
            ttk.Checkbutton(bar, text='Replace the other frames of this entry with the same picture', variable=self.same, command=self._changed).pack(side='right')
        self.run()

    def _has_alpha(self):
        return self.source.mode in ('RGBA', 'LA') or 'transparency' in self.source.info

    def _own_frames(self):
        first = fcencode.unique_frames(self.img)
        return sorted(first.values())

    def _slots(self):
        """The slots the 「限槽」 box asks for, or None when it is empty."""
        text = self.slots.get().replace('，', ' ').replace(',', ' ').strip()
        if not text:
            return None
        got = [int(s) for s in text.split()]
        if any((not 0 <= i <= 15 for i in got)):
            raise ValueError(text)
        return got

    def _text_row(self, parent, label, var, hint):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=2)
        ttk.Label(row, text=label, width=5).pack(side='left')
        box = ttk.Entry(row, textvariable=var, width=10)
        box.pack(side='left', padx=(0, 10))
        box.bind('<KeyRelease>', lambda _e: self._changed())
        ttk.Label(row, text=hint).pack(side='left')

    def _row(self, parent, label, var, choices):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=2)
        ttk.Label(row, text=label, width=5).pack(side='left')
        for value, text in choices:
            ttk.Radiobutton(row, text=text, value=value, variable=var, command=self._changed).pack(side='left', padx=(0, 10))

    def _changed(self):
        self.b_ok.configure(state='disabled')
        self.fit = None

    def _say(self, text):
        self.report.configure(state='normal')
        self.report.insert('end', text + '\n')
        self.report.see('end')
        self.report.configure(state='disabled')

    def run(self):
        self.report.configure(state='normal')
        self.report.delete('1.0', 'end')
        self.report.configure(state='disabled')
        self.b_run.configure(state='disabled')
        self.b_ok.configure(state='disabled')
        self._say('Converting…')
        frames = self._own_frames() if self.same.get() else [self.f]
        entry = self.app.bundle.entries(self.stem)[self.k]
        pictures = {f: self.source for f in frames}
        strength = float(self.strength.get()) if self.strength.get() else None
        try:
            slots = self._slots()
        except ValueError:
            self.b_run.configure(state='normal')
            self.b_ok.configure(state='normal')
            self._say('Allowed slots must be 0–15, separated by spaces or commas. Empty means unrestricted.')
            return
        opts = dict(palette=self.palette.get(), slots=slots, strength=strength, placement=self.place.get(), outline=self.outline.get())
        Worker(lambda say: fcfit.fit(entry, pictures, progress=say, **opts), self._done, self._say, self)

    def _done(self, kind, payload):
        self.b_run.configure(state='normal')
        if kind == 'error':
            self._say(f'Conversion failed: {payload}')
            return
        self.fit = payload
        self._say(f'{self.fit.how}; total cells {self.fit.cells} / limit {fcfit.CELL_LIMIT}, decoded size {self.fit.bytes} / limit {fcfit.MEMORY_CAP} bytes')
        for note in self.fit.notes:
            self._say('· ' + note)
        w, h = fcfit.frame_size(self.img, self.f)
        placed = fcfit.place(self.source, w, h, self.place.get()).convert('RGB')
        self._show(self.view_source, placed)
        self._show(self.view_result, fcfit.preview(self.fit, self.img, self.f))
        self.b_ok.configure(state='normal')

    def _show(self, label, im):
        scale = max(1, min(2, 420 // max(im.width, 1), 320 // max(im.height, 1)))
        shown = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        if shown.width > 460:
            shown = im.resize((460, max(1, im.height * 460 // im.width)), Image.LANCZOS)
        label.photo = ImageTk.PhotoImage(shown)
        label.configure(image=label.photo)

    def accept(self):
        if self.fit is None:
            return
        self.app.bundle.stage(self.stem, self.k, self.fit)
        self.app.refresh_tree_marks()
        self.app.show_selected()
        self.app.status(f'{self.stem} entry {self.k}：{len(self.fit.index)} frames replaced, not written yet')
        self.destroy()

def sharp_on_hidpi():
    """Windows stretches a program that has not said it draws at the screen's own resolution, which
    leaves the pictures and the text of a Tk window blurred. Said before the window is made."""
    if sys.platform == 'win32':
        ctypes.windll.user32.SetProcessDPIAware()

class App(tk.Tk):

    def __init__(self, path=None):
        super().__init__()
        self.title(TITLE)
        self.tk.call('tk', 'scaling', self.winfo_fpixels('1i') / 72.0)
        wide = min(int(self.winfo_screenwidth() * 0.78), int(self.winfo_fpixels('1i') / 96 * 1400))
        tall = min(int(self.winfo_screenheight() * 0.82), int(self.winfo_fpixels('1i') / 96 * 900))
        self.geometry(f'{wide}x{tall}')
        self.bundle = None
        self.nodes = {}
        self._build()
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        if path:
            self.open_image(path)

    def _build(self):
        bar = ttk.Frame(self, padding=(8, 6))
        bar.pack(fill='x')
        ttk.Button(bar, text='Open image…', command=self.ask_open).pack(side='left')
        self.path_var = tk.StringVar(value='(No image open)')
        ttk.Label(bar, textvariable=self.path_var, foreground='#3b6072').pack(side='left', padx=8)
        ttk.Button(bar, text='Write image', command=self.write_back).pack(side='right')
        ttk.Button(bar, text='Undo all changes', command=self.drop_all).pack(side='right', padx=6)
        ttk.Button(bar, text='Export…', command=self.export).pack(side='right')
        panes = ttk.PanedWindow(self, orient='horizontal')
        panes.pack(fill='both', expand=True, padx=8, pady=(0, 4))
        left = ttk.Frame(panes)
        panes.add(left, weight=1)
        self.tree = ttk.Treeview(left, columns=('what',), show='tree headings', selectmode='browse')
        self.tree.heading('#0', text='Artwork files in the image')
        self.tree.heading('what', text='Information')
        step = max(1.0, self.winfo_fpixels('1i') / 96)
        self.tree.column('#0', width=int(210 * step), stretch=False)
        self.tree.column('what', width=int(260 * step))
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<<TreeviewOpen>>', self.on_open_node)
        self.tree.bind('<<TreeviewSelect>>', lambda _e: self.show_selected())
        self.tree.tag_configure('edited', foreground='#a4501e')
        self.tree.tag_configure('locked', foreground='#888888')
        right = ttk.Frame(panes)
        panes.add(right, weight=3)
        self.view = tk.Label(right, bg=VIEW_BG, bd=0)
        self.view.pack(fill='both', expand=True)
        strip = ttk.Frame(right)
        strip.pack(fill='x', pady=4)
        self.swatches = []
        for i in range(16):
            box = tk.Label(strip, width=4, height=1, bd=1, relief='solid', text=f'{i}', font=('', 7), fg='#ffffff', bg=VIEW_BG)
            box.pack(side='left', padx=1)
            self.swatches.append(box)
        self.info = tk.Text(right, height=7, wrap='word', relief='flat', background='#f4f4f7')
        self.info.pack(fill='x')
        self.info.configure(state='disabled')
        acts = ttk.Frame(right, padding=(0, 6))
        acts.pack(fill='x')
        self.b_replace = ttk.Button(acts, text='Replace picture…', command=self.replace_frame, state='disabled')
        self.b_replace.pack(side='left')
        self.b_revert = ttk.Button(acts, text='Undo this entry', command=self.drop_entry, state='disabled')
        self.b_revert.pack(side='left', padx=6)
        self.status_var = tk.StringVar(value='Open an HDI image to begin.')
        ttk.Label(self, textvariable=self.status_var, anchor='w', padding=(10, 4)).pack(fill='x', side='bottom')

    def status(self, text):
        self.status_var.set(text)

    def say(self, text):
        self.info.configure(state='normal')
        self.info.delete('1.0', 'end')
        self.info.insert('1.0', text)
        self.info.configure(state='disabled')

    def ask_open(self):
        path = filedialog.askopenfilename(title='Open image', filetypes=IMAGE_TYPES)
        if path:
            self.open_image(path)

    def open_image(self, path):
        if self.bundle and self.bundle.staged and (not messagebox.askokcancel(TITLE, 'Discard unwritten changes and open another image?')):
            return
        try:
            self.bundle = Bundle(path)
        except EditError as e:
            messagebox.showerror(TITLE, str(e))
            return
        self.path_var.set(path)
        self.title(f'{TITLE} — {os.path.basename(path)}')
        self.fill_tree()
        self.status(f'{len(self.bundle.names)} graphics files. Select a frame and replace its picture.')

    def on_close(self):
        if self.bundle and self.bundle.staged and (not messagebox.askokcancel(TITLE, 'Discard unwritten changes and close?')):
            return
        self.destroy()

    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        for stem in self.bundle.names:
            node = self.tree.insert('', 'end', text=stem, values=('',), open=False)
            self.nodes[node] = ('file', stem, None, None)
            self.tree.insert(node, 'end', text='…')

    def on_open_node(self, _event):
        node = self.tree.focus()
        kind, stem, k, _f = self.nodes.get(node, (None, None, None, None))
        children = self.tree.get_children(node)
        if not children or self.nodes.get(children[0]) is not None:
            return
        self.tree.delete(*children)
        try:
            if kind == 'file':
                self.fill_entries(node, stem)
            elif kind == 'entry':
                self.fill_frames(node, stem, k)
        except EditError as e:
            self.tree.insert(node, 'end', text='Cannot read', values=(str(e),))

    def fill_entries(self, node, stem):
        for k, entry in enumerate(self.bundle.entries(stem)):
            img = fcimage.Image(entry)
            why = fcfit.editable(entry)
            sets = fcfit.owned(img)
            what = f'{len(img.frames)} frames; owned colors {len(sets)}; {len(img.palettes)} palettes' + ('' if why is None else '\u3000（不能改写）')
            child = self.tree.insert(node, 'end', text=f'Entry {k}', values=(what,), tags=('locked',) if why else ())
            self.nodes[child] = ('entry', stem, k, None)
            if img.frames:
                self.tree.insert(child, 'end', text='…')

    def fill_frames(self, node, stem, k):
        img = self.bundle.image(stem, k)
        for f in range(len(img.frames)):
            w, h = fcfit.frame_size(img, f)
            owner = shared_with(img, f)
            what = f'{w}×{h}' + ('' if owner is None else f' with frame {owner} shared picture')
            child = self.tree.insert(node, 'end', text=f'Frame {f}', values=(what,))
            self.nodes[child] = ('frame', stem, k, f)
        self.refresh_tree_marks()

    def refresh_tree_marks(self):
        for node, (kind, stem, k, _f) in self.nodes.items():
            if kind != 'entry' or not self.tree.exists(node):
                continue
            edited = (stem, k) in self.bundle.staged
            tags = list(self.tree.item(node, 'tags'))
            tags = [t for t in tags if t != 'edited'] + (['edited'] if edited else [])
            self.tree.item(node, tags=tags)
            text = f'Entry {k}' + (' * Replaced' if edited else '')
            self.tree.item(node, text=text)

    def selection(self):
        node = self.tree.focus()
        return self.nodes.get(node, (None, None, None, None))

    def show_selected(self):
        kind, stem, k, f = self.selection()
        self.b_replace.configure(state='disabled')
        self.b_revert.configure(state='disabled')
        if kind is None or self.bundle is None:
            return
        if kind == 'file':
            self.view.configure(image='')
            self.say(f'{stem}.BIN：{len(self.bundle.entries(stem))} entries. Expand to select entries and frames.')
            return
        img = self.bundle.image(stem, k)
        why = fcfit.editable(self.bundle.entries(stem)[k])
        self.b_revert.configure(state='normal' if (stem, k) in self.bundle.staged else 'disabled')
        self.paint_palette(stem, k)
        if kind == 'entry' or f is None:
            self.view.configure(image='')
            self.say(self.entry_text(stem, k, img, why))
            return
        owner = shared_with(img, f)
        self.show_frame(stem, k, f if owner is None else owner)
        lines = [self.entry_text(stem, k, img, why)]
        w, h = fcfit.frame_size(img, f)
        x, y = fcfit.frame_origin(img, f)
        lines.append(f'Frame {f}：{w}×{h}, screen position ({x}, {y})' + ('' if owner is None else f'; shares frame {owner}; edit that frame'))
        self.say('\n'.join(lines))
        if why is None and owner is None:
            self.b_replace.configure(state='normal')

    def entry_text(self, stem, k, img, why):
        sets = fcfit.owned(img)
        out = [f'{stem} entry {k}：{len(img.frames)} frames; {len(img.palettes)} palettes; cell dictionaries {list(img.counts)}']
        out.append('Color slots this entry owns: ' + ('、'.join(map(str, sets)) if sets else 'None') + '. Other slots come from other pictures on screen and are preserved.')
        if why:
            out.append('Cannot write: ' + why)
        fit = self.bundle.staged.get((stem, k))
        if fit is not None:
            out.append(f'Replaced: {sorted(fit.index)} frames; {fit.how}，cell {fit.cells}, decoded {fit.bytes} bytes (not written yet)')
        return '\n'.join(out)

    def paint_palette(self, stem, k):
        words = palette_words(self.bundle, stem, k)
        sets = set(fcfit.owned(self.bundle.image(stem, k)))
        for i, box in enumerate(self.swatches):
            r, g, b = fcimage.pc98_rgb(words[i])
            box.configure(bg=f'#{r:02x}{g:02x}{b:02x}', fg='#000000' if r + g + b > 330 else '#ffffff', text=f'{i}' + ('' if i in sets else '·'))

    def show_frame(self, stem, k, f):
        im = frame_image(self.bundle, stem, k, f)
        box = (max(self.view.winfo_width(), 320), max(self.view.winfo_height(), 240))
        scale = min(box[0] / im.width, box[1] / im.height)
        scale = max(1, int(scale)) if scale >= 1 else scale
        if scale != 1:
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.NEAREST if scale > 1 else Image.LANCZOS)
        self.view.photo = ImageTk.PhotoImage(im)
        self.view.configure(image=self.view.photo)

    def replace_frame(self):
        kind, stem, k, f = self.selection()
        if kind != 'frame':
            return
        path = filedialog.askopenfilename(title='Select a picture', filetypes=PICTURE_TYPES)
        if not path:
            return
        exact = exact_indices(self.bundle, stem, k, f, path)
        if exact is None:
            Convert(self, stem, k, f, path)
            return
        try:
            stage_indices(self.bundle, stem, k, f, exact)
        except EditError as e:
            messagebox.showerror(TITLE, str(e))
            return
        self.refresh_tree_marks()
        self.show_selected()
        self.status(f'{stem} entry {k} frame {f}: indexed pixels replaced, not written yet')

    def drop_entry(self):
        _kind, stem, k, _f = self.selection()
        if stem is None or k is None:
            return
        self.bundle.drop(stem, k)
        self.refresh_tree_marks()
        self.show_selected()
        self.status(f'{stem} entry {k}: edits discarded')

    def drop_all(self):
        if not self.bundle or not self.bundle.staged:
            return
        if messagebox.askokcancel(TITLE, 'Discard all changes not yet written to the image?'):
            self.bundle.staged = {}
            self.refresh_tree_marks()
            self.show_selected()
            self.status('All changes discarded')

    def export(self):
        if not self.bundle:
            return
        kind, stem, k, f = self.selection()
        out = filedialog.askdirectory(title='Choose an export folder')
        if not out:
            return
        if kind == 'frame':
            stems = {stem: [k]}
        elif kind == 'entry':
            stems = {stem: [k]}
        elif kind == 'file':
            stems = {stem: None}
        else:
            if not messagebox.askokcancel(TITLE, f'No file selected. Export all {len(self.bundle.names)} graphics files?'):
                return
            stems = {s: None for s in self.bundle.names}
        n = 0
        for name, keys in stems.items():
            n += export_file(self.bundle, out, name, keys)
        self.status(f'Exported {n} PNGs to {out}')

    def write_back(self):
        if not self.bundle or not self.bundle.staged:
            messagebox.showinfo(TITLE, 'No changes to write.')
            return
        try:
            files = self.bundle.files_to_write()
        except (fcfit.FitError, fcencode.EncodeError) as e:
            messagebox.showerror(TITLE, f'Encoding failed: {e}')
            return
        need, free = self.bundle.room_for(files)
        what = '、'.join((f'{s}.BIN（{len(b)} bytes)' for s, b in sorted(files.items())))
        if not messagebox.askokcancel(TITLE, f'Write {len(files)} files: {what}\n\nAdditional space needed: {max(need, 0)} clusters; free {free} files.\nThe original image will be saved as .bak. Continue?'):
            return
        try:
            kept = self.bundle.write(files)
        except (EditError, OSError) as e:
            messagebox.showerror(TITLE, f'Write failed: {e}')
            return
        self.fill_tree()
        self.show_selected()
        self.status(f'Wrote {os.path.basename(self.bundle.path)}; original saved as {os.path.basename(kept)}')
        messagebox.showinfo(TITLE, f'Write complete.\nOriginal image saved as:\n{kept}')

def main(argv):
    sharp_on_hidpi()
    app = App(argv[0] if argv else None)
    app.mainloop()
    return 0
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
