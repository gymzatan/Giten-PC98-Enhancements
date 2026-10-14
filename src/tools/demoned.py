"""偽典・女神転生\u3000数值编辑器 / データエディタ

    demoned.py [IMAGE.hdi] [TABLE.json]

Demons, magic and gear are all edited here. Every record, its names in both languages and the numbers
the game shipped come with the editor, so it opens and is used with no image at all; an image is what
the changes are written into, and can be opened whenever, or asked for by the button that writes.

Every change is kept as a pair, the original value and the wanted one, in an edit table that can be
saved and opened, so putting a field back to what the game shipped is the same as having no edit for
it. Nothing is written to the image until the button that says so is pressed; a write keeps the image
it replaces, beside it under the same name with the time of the write in it.
"""
import math
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balance
import gamedata as gd
import gameimage
import mkpatchbat
import records
TEXT = {'title': ('Giten Redux — Numeric Editor', '偽典・女神転生\u3000データエディタ'), 'search': ('Search', '検索'), 'only_edited': ('Edited only', '変更したものだけ'), 'original': ('Original', '元の値'), 'reset_demon': ('Reset this record', 'このレコードを全て元に戻す'), 'reset_all': ('Discard all edits', '全ての変更を破棄'), 'new': ('New edit table', '新しい変更表'), 'open': ('Open…', '開く…'), 'save': ('Save', 'Save'), 'save_as': ('Save as…', '名前を付けて保存…'), 'make_patch': ('Export BAT patch', 'bat パッチを書き出す'), 'apply': ('Write image', 'イメージに書き込む'), 'revert': ('Restore image', 'イメージを元に戻す'), 'image': ('Image', 'イメージ'), 'browse': ('Open image…', 'イメージを開く…'), 'pick_image': ('Select the HDI to write', '書き込む .hdi イメージを選んでください'), 'kept': ('Original image saved as {name}', '元のイメージを {name} として保存しました'), 'wrote': ('{image}: {doing} completed\n{names}', '{image}：{doing}しました\n{names}'), 'doing_apply': ('Write', '書き込み'), 'doing_revert': ('Restore', '復元'), 'no_change': ('The image already has these values.', 'イメージは既にこの数値です'), 'patch_dir': ('Choose a folder for the BAT patches', 'bat パッチの書き出し先'), 'table_title': ('Edit table name', '変更表の名前'), 'note': ('Notes', 'メモ'), 'unsaved': ('Unsaved changes', '未保存の変更があります'), 'saved': ('Saved to {path}', '{path} に保存しました'), 'made': ('Created: {files}', '書き出しました：{files}'), 'ok': ('Done', '完了'), 'failed': ('Failed', '失敗しました'), 'bad_value': ("'{v}' is not valid for this field", '「{v}」はこの項目に使えない書き方です'), 'lang': ('日本語', 'English'), 'no_selection': ('Select a record on the left', '左でレコードを選んでください'), 'confirm_all': ('Discard all {n} changes?', '{n} 件の変更を全て破棄しますか？'), 'confirm_new': ('Discard the unsaved edit table?', '今の変更表は未保存です。破棄しますか？'), 'nothing': ('No changes', '変更はありません'), 'absent': ('This record has no such field', 'このレコードには無い項目')}
ID = ('id', 'ID', '番号', 'center')
NAME = ('name', 'Name', '名前', 'w')
CHANGES = ('changes', 'Edits', '変更', 'center')
COLUMNS = {gd.DEMON: [ID, NAME, ('race', 'Race', '種族', 'center'), ('deity', 'Deity', 'Deity', 'center'), ('level', 'Level', 'レベル', 'center'), CHANGES], gd.SKILLS: [ID, NAME, CHANGES], gd.GEAR: [ID, NAME, ('kind', 'Kind', '種類', 'center'), CHANGES]}
ALL_COLUMNS = ['id', 'name', 'race', 'deity', 'level', 'kind', 'changes']
CELL_PAD = 14
RESIST_WORDS = {'Immune': 0, '無効': 0, 'Absorb': 252, '吸収': 252, 'Reflect': 255}
COMBO_WIDTH = {'named:行動パターン': 40}
TABLE_TYPES = [('Edit table JSON', '*.json'), ('*', '*')]
IMAGE_TYPES = [('PC-98 HDI', '*.hdi'), ('*', '*')]

class App(tk.Tk):

    def __init__(self, image=None, table_path=None, edition='main'):
        super().__init__()
        self.lang = 'zh'
        self.edition = edition
        self.withdraw()
        try:
            self.data = gd.Game(image, table_path, edition)
        except (gameimage.ImageError, balance.BalanceError, records.RecordError, OSError) as e:
            self.destroy()
            raise SystemExit(str(e))
        self.source = gd.DEMON
        self.sort = ('id', False)
        self.target = None
        self.dirty = False
        self.rows = {}
        self.image = tk.StringVar()
        self.geometry('1220x800')
        self.minsize(1000, 640)
        self._build()
        self._show_image()
        self._fill_list()
        self._retitle()
        self.deiconify()

    def _show_image(self):
        self.image.set(self.data.image.path if self.data.image else '')

    def t(self, key, **kw):
        s = TEXT[key][0 if self.lang == 'zh' else 1]
        return s.format(**kw) if kw else s

    def _retitle(self):
        name = os.path.basename(self.data.path)
        edition = gd.EDITIONS[self.edition][0 if self.lang == 'zh' else 1]
        self.title(f"{self.t('title')}{edition} — {self.data.table['title'] or name}" + (' *' if self.dirty else ''))

    def _mark_dirty(self):
        self.dirty = True
        self._retitle()

    def _build(self):
        bar = ttk.Frame(self, padding=(8, 6))
        bar.pack(fill='x')
        self.lang_btn = ttk.Button(bar, text=TEXT['lang'][0], width=9, command=self._toggle_lang)
        self.lang_btn.pack(side='left')
        ttk.Separator(bar, orient='vertical').pack(side='left', fill='y', padx=8)
        self.b_new = ttk.Button(bar, command=self._new)
        self.b_new.pack(side='left', padx=2)
        self.l_table = ttk.Label(bar)
        self.l_table.pack(side='left', padx=(10, 0))
        self.table_title = tk.StringVar(value=self.data.table['title'])
        self.table_title.trace_add('write', lambda *_a: self._title_changed())
        ttk.Entry(bar, textvariable=self.table_title, width=22).pack(side='left', padx=(4, 10))
        self.b_open = ttk.Button(bar, command=self._open)
        self.b_open.pack(side='left', padx=2)
        self.b_save = ttk.Button(bar, command=self._save)
        self.b_save.pack(side='left', padx=2)
        self.b_save_as = ttk.Button(bar, command=self._save_as)
        self.b_save_as.pack(side='left', padx=2)
        self.b_patch = ttk.Button(bar, command=self._make_patch)
        self.b_patch.pack(side='left', padx=2)
        row2 = ttk.Frame(self, padding=(8, 0))
        row2.pack(fill='x')
        self.l_image = ttk.Label(row2)
        self.l_image.pack(side='left')
        ttk.Entry(row2, textvariable=self.image, width=58, state='readonly').pack(side='left', padx=4)
        self.b_browse = ttk.Button(row2, width=12, command=self._browse)
        self.b_browse.pack(side='left')
        self.b_apply = ttk.Button(row2, command=lambda: self._image_action('apply'))
        self.b_apply.pack(side='left', padx=2)
        self.b_revert = ttk.Button(row2, command=lambda: self._image_action('revert'))
        self.b_revert.pack(side='left', padx=2)
        panes = ttk.PanedWindow(self, orient='horizontal')
        panes.pack(fill='both', expand=True, padx=8, pady=8)
        left = ttk.Frame(panes)
        panes.add(left, weight=0)
        self.kinds = ttk.Notebook(left)
        self.kinds.pack(fill='x')
        self.kind_tabs = {}
        for key, zh, _ja in gd.SOURCES:
            frame = ttk.Frame(self.kinds)
            self.kinds.add(frame, text=zh)
            self.kind_tabs[key] = frame
        self.kinds.bind('<<NotebookTabChanged>>', self._on_kind)
        top = ttk.Frame(left)
        top.pack(fill='x', pady=4)
        self.l_search = ttk.Label(top)
        self.l_search.pack(side='left')
        self.search = tk.StringVar()
        self.search.trace_add('write', lambda *_a: self._fill_list())
        ttk.Entry(top, textvariable=self.search, width=16).pack(side='left', padx=4)
        self.only_edited = tk.BooleanVar(value=False)
        self.c_only = ttk.Checkbutton(top, variable=self.only_edited, command=self._fill_list)
        self.c_only.pack(side='left')
        self.scroll = ttk.Scrollbar(left, orient='vertical')
        self.scroll.pack(side='right', fill='y')
        self.tree = ttk.Treeview(left, columns=ALL_COLUMNS, show='headings', selectmode='browse', yscrollcommand=self.scroll.set)
        self.scroll.configure(command=self.tree.yview)
        self.tree.pack(side='left', fill='both', expand=True)
        style = ttk.Style()
        self.tab_font = tkfont.Font(font=style.lookup('TNotebook.Tab', 'font') or 'TkDefaultFont')
        self.cell_font = tkfont.Font(font=style.lookup('Treeview', 'font') or 'TkDefaultFont')
        self.head_font = tkfont.Font(font=style.lookup('Treeview.Heading', 'font') or 'TkHeadingFont')
        self._set_columns()
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.tag_configure('edited', foreground='#b35c00')
        right = ttk.Frame(panes)
        panes.add(right, weight=1)
        head = ttk.Frame(right)
        head.pack(fill='x', pady=(0, 4))
        self.who = ttk.Label(head, font=('', 12, 'bold'))
        self.who.pack(side='left')
        self.b_reset_demon = ttk.Button(head, command=self._reset_record)
        self.b_reset_demon.pack(side='right')
        self.b_reset_all = ttk.Button(head, command=self._reset_all)
        self.b_reset_all.pack(side='right', padx=6)
        self.desc = ttk.Label(right, foreground='#3b6072', anchor='w', wraplength=760)
        self.desc.pack(fill='x', pady=(0, 4))
        noterow = ttk.Frame(right)
        noterow.pack(fill='x', pady=(0, 6))
        self.l_note = ttk.Label(noterow)
        self.l_note.pack(side='left')
        self.note = tk.StringVar()
        self.note.trace_add('write', lambda *_a: self._note_changed())
        ttk.Entry(noterow, textvariable=self.note).pack(side='left', fill='x', expand=True, padx=4)
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill='both', expand=True)
        self.tabs = {}
        self.moon_canvas = None
        self._relabel()

    def _build_fields(self, fields):
        for tab in self.tabs.values():
            tab.destroy()
        self.tabs, self.rows, self.moon_canvas = ({}, {}, None)
        groups = []
        for f in fields:
            if (f[0], f[1]) not in groups:
                groups.append((f[0], f[1]))
        for zh, ja in groups:
            frame = ttk.Frame(self.nb, padding=8)
            self.nb.add(frame, text=zh if self.lang == 'zh' else ja)
            self.tabs[zh] = frame
        for zh, _ja in groups:
            self._build_group(zh, [f for f in fields if f[0] == zh])
        self.groups = groups

    def _build_group(self, group, fields):
        parent = self.tabs[group]
        cols = 2 if len(fields) > 8 else 1
        per_col = (len(fields) + cols - 1) // cols
        for n, (_g, _gja, zh, ja, off, width, kind) in enumerate(fields):
            box = ttk.Frame(parent)
            box.grid(row=n % per_col, column=n // per_col, sticky='ew', padx=(0, 18), pady=2)
            label = ttk.Label(box, width=13, anchor='w', text=zh if self.lang == 'zh' else ja)
            label.grid(row=0, column=0, sticky='w')
            var = tk.StringVar()
            if kind in (gd.SKILL, gd.ITEM, gd.LEARN, gd.TALK, gd.AFFINITY) or kind.startswith('named:'):
                w = ttk.Combobox(box, textvariable=var, width=COMBO_WIDTH.get(kind, 24), state='readonly')
            elif kind == gd.MOON:
                w = ttk.Spinbox(box, textvariable=var, width=10, wrap=True, values=list(range(len(self.data.moon))), command=lambda o=off, wd=width: self._commit(o, wd))
            elif kind in (gd.INT, gd.RATE, gd.RAW):
                w = ttk.Spinbox(box, textvariable=var, width=12, from_=0, to=256 ** width - 1, command=lambda o=off, wd=width: self._commit(o, wd))
            else:
                w = ttk.Entry(box, textvariable=var, width=12)
            w.grid(row=0, column=1, sticky='w')
            w.bind('<FocusOut>', lambda _e, o=off, wd=width: self._commit(o, wd))
            w.bind('<Return>', lambda _e, o=off, wd=width: self._commit(o, wd))
            w.bind('<<ComboboxSelected>>', lambda _e, o=off, wd=width: self._commit(o, wd))
            hint = ttk.Label(box, foreground='#2c5468')
            hint.grid(row=0, column=2, sticky='w', padx=(4, 0))
            btn = ttk.Button(box, text='↺', width=3, command=lambda o=off, wd=width: self._reset_field(o, wd))
            btn.grid(row=0, column=3, sticky='w', padx=(4, 0))
            orig = ttk.Label(box, foreground='#777', anchor='w')
            orig.grid(row=1, column=1, columnspan=3, sticky='w')
            orig.grid_remove()
            self.rows[off, width] = {'label': label, 'var': var, 'widget': w, 'orig': orig, 'hint': hint, 'zh': zh, 'ja': ja, 'kind': kind}
        for c in range(cols):
            parent.columnconfigure(c, weight=1)
        if group == 'Basic':
            self.moon_canvas = tk.Canvas(parent, highlightthickness=1, highlightbackground='#9fc8dc', background='#dff1fa')
            self.moon_canvas.grid(row=per_col, column=0, columnspan=cols, sticky='nsew', pady=(14, 0))
            parent.rowconfigure(per_col, weight=1)
            self.moon_canvas.bind('<Configure>', lambda _e: self._draw_moon())

    def _draw_moon(self):
        """The day's damage multiplier of the record's 月齢対応 row (ET0003; 2v/100 in 原版, √(v/50) in 再平衡版)
        over the 28 moon ages, on a doubling scale so that x2 and x0.5 sit the same distance from x1; the guide's
        five words shade the bands they cover. Resting on a day's dot shows its number."""
        c = self.moon_canvas
        if c is None:
            return
        c.delete('all')
        w, h = (c.winfo_width(), c.winfo_height())
        if w < 60 or h < 60:
            return
        ja = self.lang == 'ja'
        if self.target is None:
            c.create_text(w / 2, h / 2, text=self.t('no_selection'), fill='#5a7f92')
            return
        value = self.data.current(self.target, 88, 1)
        curve = self.data.moon_curve(value)
        name = f'月齢対応 {value}' if ja else f'Moon table {value}'
        if curve is None:
            last = len(self.data.moon) - 1
            c.create_text(w / 2, h / 2, fill='#5a7f92', text=name + (f'：月齢表（0～{last}）の外。ゲームは表の後ろのデータを読む' if ja else f'：超出月龄表（0～{last}），游戏会读到表后面的数据'))
            return
        left, right, top, bottom = (56, w - 16, 24, h - 34)
        low, high = (math.log2(gd.MOON_MIN), math.log2(gd.MOON_MAX))

        def y_of(mult):
            mult = min(max(mult, gd.MOON_MIN), gd.MOON_MAX)
            return bottom - (math.log2(mult) - low) / (high - low) * (bottom - top)
        shades = ['#eef7fb', '#dff1fa', '#e9f6ee', '#fbf1df', '#fbe4df']
        for (a, b), names, shade in zip(self.data.moon_bands(), gd.MOON_LEVELS, shades):
            c.create_rectangle(left, y_of(b), right, y_of(a), fill=shade, outline='')
            c.create_text(right - 4, (y_of(a) + y_of(b)) / 2, anchor='e', fill='#7a98a8', text=names[1] if ja else names[0], font=('', 7))
        for mult in (0.25, 0.5, 1, 2, 4):
            y = y_of(mult)
            c.create_line(left, y, right, y, fill='#5f9fbf' if mult == 1 else '#b8dcec', width=2 if mult == 1 else 1)
            c.create_text(left - 6, y, anchor='e', fill='#2c5468', text=f'×{mult:g}', font=('', 8))
        step_x = (right - left) / (gd.MOON_DAYS - 1)
        for day in range(gd.MOON_DAYS):
            x = left + day * step_x
            c.create_line(x, top, x, bottom, fill='#c2e2f0')
            if day in (0, 14) or (day + 1) % 5 == 0 or day == gd.MOON_DAYS - 1:
                c.create_text(x, bottom + 8, text=str(day + 1), fill='#2c5468', font=('', 7))
        c.create_line(left, top, left, bottom, fill='#7fb4cc')
        c.create_line(left, bottom, right, bottom, fill='#7fb4cc')
        c.create_text(left, bottom + 22, text='New moon', fill='#2c5468', font=('', 8))
        c.create_text(left + 14 * step_x, bottom + 22, text='満月' if ja else 'Full moon', fill='#2c5468', font=('', 8))
        top_m, low_m = (max(curve), min(curve))
        days_of = lambda m: '、'.join((str(d + 1) for d, v in enumerate(curve) if v == m))
        c.create_text(right, top - 10, anchor='e', fill='#2c5468', font=('', 8), text=f'{name}\u3000最高 ×{top_m:.3g}（{days_of(top_m)}/28）\u3000最低 ×{low_m:.3g}（{days_of(low_m)}/28）')
        pts = [(left + day * step_x, y_of(m)) for day, m in enumerate(curve)]
        c.create_line(*[v for p in pts for v in p], fill='#111111', width=2)
        for day, ((x, y), m) in enumerate(zip(pts, curve)):
            dot = c.create_oval(x - 3, y - 3, x + 3, y + 3, fill='#d02020', outline='')
            c.tag_bind(dot, '<Enter>', lambda _e, x=x, y=y, day=day, m=m: self._moon_tip(x, y, day, m))
            c.tag_bind(dot, '<Leave>', lambda _e: c.delete('tip'))

    def _moon_tip(self, x, y, day, mult):
        c = self.moon_canvas
        c.delete('tip')
        text = f'{day + 1}/28\u3000×{mult:.3g}'
        anchor = 'sw' if x < c.winfo_width() - 90 else 'se'
        label = c.create_text(x + (6 if anchor == 'sw' else -6), y - 6, anchor=anchor, text=text, fill='#111111', font=('', 8), tags='tip')
        box = c.bbox(label)
        c.tag_lower(c.create_rectangle(box[0] - 3, box[1] - 1, box[2] + 3, box[3] + 1, fill='#ffffff', outline='#7fb4cc', tags='tip'), label)

    def _toggle_lang(self):
        self.lang = 'ja' if self.lang == 'zh' else 'zh'
        self._relabel()
        self._set_columns()
        self._fill_list()
        if self.target:
            self.shape = None
            self._show(self.target)
        self._retitle()

    def _relabel(self):
        i = 0 if self.lang == 'zh' else 1
        self.lang_btn.configure(text=TEXT['lang'][i])
        for btn, key in ((self.b_new, 'new'), (self.b_open, 'open'), (self.b_save, 'save'), (self.b_save_as, 'save_as'), (self.b_patch, 'make_patch'), (self.b_apply, 'apply'), (self.b_revert, 'revert'), (self.b_browse, 'browse'), (self.b_reset_demon, 'reset_demon'), (self.b_reset_all, 'reset_all')):
            btn.configure(text=self.t(key))
        self.l_image.configure(text=self.t('image'))
        self.l_table.configure(text=self.t('table_title'))
        self.l_search.configure(text=self.t('search'))
        self.c_only.configure(text=self.t('only_edited'))
        self.l_note.configure(text=self.t('note'))
        self._head_labels()
        self._tab_labels()
        for n, (zh, ja) in enumerate(getattr(self, 'groups', [])):
            self.nb.tab(n, text=zh if self.lang == 'zh' else ja)
        for row in self.rows.values():
            row['label'].configure(text=row['zh'] if self.lang == 'zh' else row['ja'])

    def _tab_labels(self):
        """The three tabs are all made the width of the widest label there is, in either language.
        A themed tab is as wide as its text and takes no width of its own, so the text is padded to
        that width, a space at a time, either side in turn so it stays in the middle."""
        target = max((self.tab_font.measure(t) for _k, zh, ja in gd.SOURCES for t in (zh, ja)))
        for n, (_key, zh, ja) in enumerate(gd.SOURCES):
            text = zh if self.lang == 'zh' else ja
            left = right = 0
            while self.tab_font.measure(' ' * left + text + ' ' * right) < target:
                if left <= right:
                    left += 1
                else:
                    right += 1
            self.kinds.tab(n, text=' ' * left + text + ' ' * right)

    def _on_kind(self, _event=None):
        n = self.kinds.index(self.kinds.select())
        self.source = gd.SOURCES[n][0]
        self.target = None
        self._set_columns()
        self._fill_list()

    def _set_columns(self):
        """Each kind of record is listed by what it has: only a demon has a 种族, a level and so on.
        Every column is made as wide as the widest thing that goes in it."""
        cols = COLUMNS[self.source]
        if self.sort[0] not in {c[0] for c in cols}:
            self.sort = ('id', False)
        self.tree.configure(displaycolumns=[c[0] for c in cols])
        rows = self.data.of_source(self.source)
        for key, _zh, _ja, anchor in cols:
            widest = max([self.cell_font.measure(str(self._cell(e, key))) for e in rows] or [0])
            width = max(widest, self.head_font.measure(self._head_text(key))) + CELL_PAD
            self.tree.column(key, width=width, minwidth=width, anchor=anchor, stretch=False)
            self.tree.heading(key, command=lambda k=key: self._sort_by(k))
        self._head_labels()

    def _head_text(self, key):
        """A column's name, with a mark on the one the list is in the order of. The mark is part of
        the widest case, so the column does not jump when the order changes."""
        zh, ja = next(((c[1], c[2]) for c in COLUMNS[self.source] if c[0] == key))
        mark = (' ▲' if not self.sort[1] else ' ▼') if key == self.sort[0] else '\u3000'
        return (zh if self.lang == 'zh' else ja) + mark

    def _head_labels(self):
        for key, _zh, _ja, _anchor in COLUMNS[self.source]:
            self.tree.heading(key, text=self._head_text(key))

    def _sort_by(self, key):
        """Sort by a column; the same column again turns the order round."""
        self.sort = (key, not self.sort[1] if self.sort[0] == key else False)
        self._head_labels()
        self._fill_list()

    def _cell(self, e, key):
        ja = self.lang == 'ja'
        if key == 'id':
            return e.target
        if key == 'name':
            return e.jp if ja else e.zh
        if key in ('race', 'deity'):
            return (e.race if key == 'race' else e.deity)[0 if ja else 1]
        if key == 'level':
            level = self.data.level(e.target)
            return '' if level is None else level
        if key == 'kind':
            return e.note
        n = self.data.edit_count(e.target)
        return n if n else ''

    def _sort_key(self, e, key):
        if key == 'id':
            return gd.Game._order(e.target)
        if key in ('level', 'changes'):
            value = self._cell(e, key)
            return -(value if value != '' else 0)
        return str(self._cell(e, key))

    def _fill_list(self):
        want = self.search.get().strip().lower()
        rows = []
        for e in self.data.of_source(self.source):
            n = self.data.edit_count(e.target)
            if self.only_edited.get() and (not n):
                continue
            if want and want not in f'{e.target} {e.jp} {e.zh}'.lower():
                continue
            rows.append(e)
        key, down = self.sort
        rows.sort(key=lambda e: (self._sort_key(e, key), gd.Game._order(e.target)), reverse=down)
        self.tree.delete(*self.tree.get_children())
        for e in rows:
            n = self.data.edit_count(e.target)
            self.tree.insert('', 'end', iid=e.target, values=[self._cell(e, c) for c in ALL_COLUMNS], tags=('edited',) if n else ())
        if self.target and self.tree.exists(self.target):
            self.tree.selection_set(self.target)

    def _on_select(self, _event):
        sel = self.tree.selection()
        if sel:
            self._show(sel[0])

    def _show(self, target):
        fields = self.data.fields(target)
        shape = tuple(((f[0], f[2], f[4], f[5], f[6]) for f in fields))
        if shape != getattr(self, 'shape', None):
            self._build_fields(fields)
            self.shape = shape
        self.target = target
        e = self.data.entries[target]
        self.who.configure(text=f'{target}\u3000{e.jp}\u3000/\u3000{e.zh}\u3000{e.note}')
        text = e.desc[0 if self.lang == 'ja' else 1]
        self.desc.configure(text=text.replace('＠', '▏').replace('\n', ' '))
        entry = self.data.table['edits'].get(target) or {}
        self._loading = True
        self.note.set(entry.get('note', ''))
        self._loading = False
        for (off, width), row in self.rows.items():
            self._load_row(target, off, width, row)
        self._draw_moon()

    def _load_row(self, target, off, width, row):
        kind = row['kind']
        if not self.data.has(target, off, width):
            row['var'].set('')
            row['hint'].configure(text='')
            row['orig'].configure(text=self.t('absent'))
            row['orig'].grid()
            row['widget'].configure(state='disabled')
            return
        cur = self.data.current(target, off, width)
        orig = self.data.original(target, off, width)
        picker = kind in (gd.SKILL, gd.ITEM, gd.LEARN, gd.TALK, gd.AFFINITY) or kind.startswith('named:')
        row['widget'].configure(state='readonly' if picker else 'normal')
        if picker:
            row['widget'].configure(values=self._choices(kind, cur))
        row['var'].set(self._render(kind, cur))
        row['hint'].configure(text=self._hint(kind, cur))
        if cur == orig:
            row['orig'].grid_remove()
        else:
            row['orig'].configure(text=f"{self.t('original')} {self._render(kind, orig)}")
            row['orig'].grid()
        row['widget'].configure(foreground='black' if cur == orig else '#b35c00')

    def _choices(self, kind, current=None):
        """What the drop-down offers. Each line carries the number as well as the word, so values that
        share a word stay apart, and a value the table does not know is offered as itself."""
        d = self.data
        if kind == gd.SKILL:
            return [d.skill_text(v, self.lang) for v in [0] + sorted(d.skills)]
        if kind == gd.ITEM:
            return [d.item_text(v, self.lang) for v in [0] + sorted(d.items)]
        group = {gd.LEARN: '習得系統', gd.TALK: '会話タイプ', gd.AFFINITY: '装備相性'}.get(kind) or kind.split(':', 1)[1]
        known = sorted((int(v) for v in d.enums[group]))
        if current is not None and current not in known:
            known = sorted(known + [current])
        return [d.enum_text(group, v, self.lang) for v in known]

    def _hint(self, kind, v):
        return self.data.rate_bucket(v, self.lang) if kind == gd.RATE else ''

    def _render(self, kind, v):
        d = self.data
        if kind == gd.RESIST:
            return d.resist_text(v, self.lang)
        if kind == gd.SKILL:
            return d.skill_text(v, self.lang)
        if kind == gd.ITEM:
            return d.item_text(v, self.lang)
        if kind in (gd.LEARN, gd.TALK, gd.AFFINITY) or kind.startswith('named:'):
            group = {gd.LEARN: '習得系統', gd.TALK: '会話タイプ', gd.AFFINITY: '装備相性'}.get(kind) or kind.split(':', 1)[1]
            return d.enum_text(group, v, self.lang)
        return str(v)

    def _parse(self, kind, text, width):
        text = text.strip()
        if kind == gd.RESIST:
            if text in RESIST_WORDS:
                return RESIST_WORDS[text]
            if text.startswith('Special'):
                try:
                    return int(text[2:], 16)
                except ValueError:
                    return None
            if text.endswith('%'):
                try:
                    pct = int(text[:-1])
                except ValueError:
                    return None
                return pct // 2 if pct % 2 == 0 and 0 <= pct <= 498 else None
            return None
        if kind in (gd.SKILL, gd.ITEM, gd.LEARN, gd.TALK, gd.AFFINITY) or kind.startswith('named:'):
            m = re.match('\\d+', text)
            if not m:
                return None
            v = int(m.group())
        else:
            try:
                v = int(text)
            except ValueError:
                return None
        return v if 0 <= v < 256 ** width else None

    def _commit(self, off, width):
        if not self.target or not self.data.has(self.target, off, width):
            return
        row = self.rows[off, width]
        v = self._parse(row['kind'], row['var'].get(), width)
        if v is None:
            messagebox.showwarning(self.t('failed'), self.t('bad_value', v=row['var'].get()))
            self._load_row(self.target, off, width, row)
            return
        if v != self.data.current(self.target, off, width):
            self.data.set(self.target, off, width, v)
            self._mark_dirty()
        self._load_row(self.target, off, width, row)
        self._refresh_row_marks()
        if off == 88:
            self._draw_moon()

    def _note_changed(self):
        if getattr(self, '_loading', False) or not self.target:
            return
        entry = self.data.table['edits'].get(self.target)
        if entry is not None and entry.get('note', '') != self.note.get():
            entry['note'] = self.note.get()
            self._mark_dirty()

    def _title_changed(self):
        if self.data.table['title'] != self.table_title.get():
            self.data.table['title'] = self.table_title.get()
            self._mark_dirty()

    def _refresh_row_marks(self):
        """The row of the record being edited, as it reads now — its level and its count of changes
        both follow what was just typed."""
        if self.target and self.tree.exists(self.target):
            e = self.data.entries[self.target]
            n = self.data.edit_count(self.target)
            self.tree.item(self.target, tags=('edited',) if n else (), values=[self._cell(e, c) for c in ALL_COLUMNS])

    def _reset_field(self, off, width):
        if not self.target or not self.data.has(self.target, off, width):
            return
        self.data.reset(self.target, off, width)
        self._mark_dirty()
        self._load_row(self.target, off, width, self.rows[off, width])
        self._refresh_row_marks()
        if off == 88:
            self._draw_moon()

    def _reset_record(self):
        if not self.target:
            messagebox.showinfo(self.t('title'), self.t('no_selection'))
            return
        self.data.reset(self.target)
        self._mark_dirty()
        self._show(self.target)
        self._refresh_row_marks()

    def _reset_all(self):
        n = len(self.data.table['edits'])
        if not n:
            messagebox.showinfo(self.t('title'), self.t('nothing'))
            return
        if not messagebox.askyesno(self.t('title'), self.t('confirm_all', n=n)):
            return
        self.data.table['edits'].clear()
        self._mark_dirty()
        self._fill_list()
        if self.target:
            self._show(self.target)

    def _new(self):
        if self.dirty and (not messagebox.askyesno(self.t('title'), self.t('confirm_new'))):
            return
        self.data.new_table('')
        self.table_title.set('')
        self.dirty = False
        self._after_table_change()

    def _open(self):
        path = filedialog.askopenfilename(filetypes=TABLE_TYPES, initialdir=gd.app_dir())
        if not path:
            return
        try:
            self.data.open_table(path)
        except balance.BalanceError as e:
            messagebox.showerror(self.t('failed'), str(e))
            return
        self.table_title.set(self.data.table['title'])
        self.dirty = False
        self._after_table_change()

    def _after_table_change(self):
        self._fill_list()
        if self.target:
            self._show(self.target)
        self._retitle()

    def _save(self):
        path = self.data.save_table()
        self.dirty = False
        self._retitle()
        self._fill_list()
        messagebox.showinfo(self.t('ok'), self.t('saved', path=os.path.basename(path)))

    def _save_as(self):
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=TABLE_TYPES, initialdir=gd.app_dir())
        if not path:
            return
        self.data.save_table(path)
        self.dirty = False
        self._retitle()
        messagebox.showinfo(self.t('ok'), self.t('saved', path=os.path.basename(path)))

    def _make_patch(self):
        if not self.data.table['edits']:
            messagebox.showinfo(self.t('title'), self.t('nothing'))
            return
        here = os.path.dirname(self.data.image.path) if self.data.image else gd.app_dir()
        outdir = filedialog.askdirectory(parent=self, title=self.t('patch_dir'), initialdir=here)
        if not outdir:
            return
        try:
            written = mkpatchbat.main(outdir, self.data.table, self.data.blob)
        except (SystemExit, KeyError) as e:
            messagebox.showerror(self.t('failed'), str(e))
            return
        messagebox.showinfo(self.t('ok'), self.t('made', files='\n'.join((os.path.basename(p) for p in written))))

    def _browse(self):
        """Open an image to write into, keeping the edit table in hand. True when one was opened."""
        here = os.path.dirname(self.data.image.path) if self.data.image else gd.app_dir()
        path = filedialog.askopenfilename(parent=self, title=self.t('pick_image'), filetypes=IMAGE_TYPES, initialdir=here)
        if not path:
            return False
        try:
            data = gd.Game(path, self.data.path, self.edition)
        except (gameimage.ImageError, balance.BalanceError, records.RecordError, OSError) as e:
            messagebox.showerror(self.t('failed'), str(e))
            return False
        data.table, data.path = (self.data.table, self.data.path)
        self.data = data
        self._show_image()
        self.shape = None
        self._fill_list()
        if self.target and self.target in self.data.entries:
            self._show(self.target)
        else:
            self.target = None
        self._retitle()
        return True

    def _image_action(self, action):
        if self.data.image is None and (not self._browse()):
            return
        if not self.data.table['edits']:
            messagebox.showinfo(self.t('title'), self.t('nothing'))
            return
        try:
            wrote, kept = self.data.write_image(revert=action == 'revert')
        except (balance.BalanceError, records.RecordError, gameimage.ImageError, OSError) as e:
            messagebox.showerror(self.t('failed'), str(e))
            return
        if not wrote:
            messagebox.showinfo(self.t('ok'), self.t('no_change'))
            return
        note = self.t('kept', name=os.path.basename(kept)) if kept else ''
        messagebox.showinfo(self.t('ok'), self.t('wrote', image=os.path.basename(self.data.image.path), doing=self.t('doing_' + action), names='、'.join(wrote) + ('\n' + note if note else '')))
        if self.target:
            self._show(self.target)
if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--rebalance']
    if getattr(sys, 'frozen', False):
        edition = gd.packed_edition()
    else:
        edition = 'rebalance' if '--rebalance' in sys.argv[1:] else 'main'
    App(*args[:2], edition=edition).mainloop()
