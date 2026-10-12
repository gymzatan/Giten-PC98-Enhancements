"""Shared script rebuilding and gameplay repairs used by every build entry point.

The repair order and rules are the accepted make.py implementation. Translation
selection and image packaging are kept outside this language-neutral module.
"""
import os
import balance, bagexpand, battlefield, checkfix, ctxfree, ddsfile, exefix, exekeys
import expgap, expshow, holds, mkholdbat, moonfast, nospace, rebalance, records
import skillfix, slotorder, statfix, storyfix, vmswap, worldbackdrop
from checkvm import dictionary_sizes, verify
from ddsvm import tokenize
from textbuild import layout_record
from units import script_units

SRC = 'files/DDS98'

class ScriptInputs:
    """Consume existing parsed record/unit identities without replacing text."""
    def __init__(self, src=SRC):
        self.records = { (stem, ci, pos): (rec, toks, units)
                         for stem, ci, pos, rec, toks, units in script_units(src) if units }
        self.script = {}
        self.table = {}

    def chars(self):
        return set()

class JapaneseText:
    """The original game's encoding, without a replacement font or allocated Chinese glyphs."""

    @staticmethod
    def encode_char(ch):
        return ch.encode("cp932")


def build_scripts(texts, charmap, hold_table, wait_table, src=SRC):
    """(script files with translated units, battle line holds and dialogue waits written in, where
    the holds the table adds ended up in them). hold_table is tools/holds.load()'s table, wait_table
    tools/talkwait.table()'s; a record may have translations, holds, waits, or any of them. Only the
    holds are reported back: they are what patch/关闭 汉化节奏.bat rewrites, while a wait mends the
    game's own dialogue and stays."""
    sizes = dictionary_sizes(src)
    changed, holds_at = {}, {}
    by_file = {}
    for key in set(texts.script) | set(hold_table) | set(wait_table):
        by_file.setdefault(key[0], []).append(key)
    for stem, keys in sorted(by_file.items()):
        parsed = ddsfile.parse(open(os.path.join(src, stem + ".BIN"), "rb").read())
        touched, added = False, {}
        for key in sorted(keys):
            _stem, ci, pos = key
            r = parsed[ci][pos]
            if key in texts.records:
                (rid, cond, payload), toks, units = texts.records[key]
                if (r.rid, r.cond, r.payload) != (rid, cond, payload):
                    raise SystemExit(f"{stem}/{ci}/{pos}: record order differs from the extraction")
            else:                                  # a record with no text of its own, only a hold
                payload, toks, units = r.payload, tokenize(r.payload), []
            try:
                commands, appends = holds.edits(key, payload, toks, units,
                                                hold_table.get(key, {"after": {}, "original": {}}))
            except holds.HoldError as e:
                raise SystemExit(f"text/holds.json: {e}")
            waits = wait_table.get(key, {})
            if set(waits) & set(appends):
                raise SystemExit(f"{stem}/{ci}/{pos}: a pacing hold and a dialogue wait on one line")
            if not commands and not appends and not waits and key not in texts.script:
                continue                           # a listed hold left as the game has it
            new, placed = layout_record(payload, toks, units, texts.script.get(key, {}), charmap,
                                        commands, {**appends, **waits})
            problems, _ = verify(new, sizes, False)
            if problems:
                raise SystemExit(f"{stem}/{ci}/{pos}: rebuilt record fails: {problems}")
            r.payload = new
            # where each added hold landed: its piece follows the token's own bytes, and the frame
            # count is its last byte (patch/恢复原版节奏.bat writes to exactly these)
            added[(ci, pos)] = [placed[i][0] + placed[i][1] + len(raw) - 1
                                for i, raw in sorted(appends.items())]
            touched = True
        if touched:
            changed[stem + ".BIN"] = ddsfile.build(parsed)
            if any(added.values()):
                holds_at[stem + ".BIN"] = mkholdbat.in_file(parsed, added)
    return changed, holds_at


def build_fixes(files, fix, name, by_file=None, src=SRC):
    """Mend what a fix module lists in the game's scripts (tools/storyfix.py: the dead ends in its
    event logic; tools/checkfix.py: its story checks; tools/expshow.py: the summary's experience line),
    in the script files this build wrote or, for a file it left alone, in the game's own; by_file is
    the module's by_file() when it needs something of the build's. files gains every file the fixes
    touch. -> {file: {(chunk, record id): (payload as this build wrote it before the fix, sites,
    appended bytes)}}, what patch/关闭 <name>.bat needs to take them back out."""
    unmended = {}
    for stem, fixes in sorted((by_file or fix.by_file()).items()):
        name_bin = stem + ".BIN"
        parsed = ddsfile.parse(files.get(name_bin) or open(os.path.join(src, name_bin), "rb").read())
        before = {(ci, pos): r.payload for ci, recs in enumerate(parsed) for pos, r in enumerate(recs)}
        try:
            edits = fix.apply_to(parsed, fixes)
        except storyfix.StoryFixError as e:
            raise SystemExit(f"{name}：{e}") from None
        files[name_bin] = ddsfile.build(parsed)
        unmended[name_bin] = {(ci, parsed[ci][pos].rid): (before[(ci, pos)], sites, block)
                              for (ci, pos), (sites, block) in edits.items()}
    return unmended


def write_tables(files, *edit_tables, src=SRC):
    """Write edit tables (tools/balance.py's form) into this build's files, into the ones it has written (the
    numbers ahead of a record's name read the same in a translated file) or else the game's own. -> the names of
    the records written."""
    plains = {}

    def plain_of(stem):
        if stem not in plains:
            plains[stem] = records.plain_of(files.get(stem + ".BIN")
                                            or open(os.path.join(src, stem + ".BIN"), "rb").read())
        return plains[stem]

    wrote = []
    for t in edit_tables:
        wrote += balance.apply_table(t, plain_of)[0]
    for stem, plain in plains.items():
        files[stem + ".BIN"] = records.encode(plain)
    return wrote


def repair_files(files, src=SRC, extras=True, rebalance_on=False, charmap=None, english=False):
    unmended, unchecked, unshown, ungapped = {}, {}, {}, {}
    moon_forms = []
    added = {}
    # the world map's battle field goes in either way, like the negotiation questions: a battle
    # there then ends in black instead of showing that invisible map's ceiling and floor
    # (tools/battlefield.py)
    try:
        battlefield.apply_to(files, added, src)
    except battlefield.BattlefieldError as e:
        raise SystemExit(f"{battlefield.MAP}：{e}") from None
    # so do the backdrops of the world map's areas the game left without one: a battle there is
    # fought on its neighbours' backdrop instead of on black (tools/worldbackdrop.py)
    try:
        worldbackdrop.apply_to(files, src)
    except worldbackdrop.BackdropError as e:
        raise SystemExit(f"tools/worldbackdrop.py：{e}") from None
    # the story fixes go in either way, for the same reason as the item-list fix below: each
    # mends a dead end of the game's own. patch/关闭 剧情死局修复.bat takes them back. So do the
    # story checks (patch/关闭 剧情检定修复.bat) and the attribute and combat formulas
    # (patch/关闭 能力值修复.bat): each mends what the game's own data says it does. The
    # summary's experience line (patch/关闭 经验值显示修复.bat) says what each member really gains.
    unmended = build_fixes(files, storyfix, "剧情死局修复", src=src)
    unchecked = build_fixes(files, checkfix, checkfix.NAME, src=src)
    unshown = build_fixes(files, expshow, expshow.NAME, expshow.by_file(charmap, english=english), src)
    # 等级差经验 (patch/启用 等级差经验.bat) changes how the experience is shared out, so the plain
    # builds go without it and its .bat's record is worked out on a copy; the 再平衡版 carries it
    ungapped = build_fixes(files if rebalance_on else dict(files), expgap, expgap.NAME,
                           expgap.by_file(charmap, english=english), src)
    items = files.get(statfix.TABLE + ".BIN") or open(os.path.join(src, statfix.TABLE + ".BIN"), "rb").read()
    try:
        files[statfix.TABLE + ".BIN"] = statfix.apply_table(items)
    except statfix.StatFixError as e:
        raise SystemExit(f"{statfix.NAME}：{e}") from None
    # the attack skills (patch/关闭 攻击技能修复.bat) go in either way: each is a skill the game ships with
    # no power (tools/skillfix.py; the user counts it a fix)
    try:
        write_tables(files, skillfix.table(), src=src)
    except (skillfix.SkillError, balance.BalanceError) as e:
        raise SystemExit(f"{skillfix.NAME}：{e}") from None
    # the difficulty adjustment (balance.json: 但他林 II's resists; patch/关闭 难度调整.bat) is an extra, like
    # the faster moon below: it changes the game rather than mending it
    if extras:
        try:
            write_tables(files, balance.load(), src=src)
        except balance.BalanceError as e:
            raise SystemExit(f"难度调整：{e}") from None
    # the 再平衡版's late boss tables and learning pools (patch/关闭 再平衡.bat)
    if rebalance_on:
        try:
            rebalance.apply_to(files, src)
        except (rebalance.RebalanceError, balance.BalanceError) as e:
            raise SystemExit(f"{rebalance.NAME}：{e}") from None
    # the faster moon (patch/关闭 月相加速.bat) is an extra, like the keys: it changes the game's
    # pace rather than mending it. Its wording of コアシールド's description goes with it
    moon_forms = moonfast.desc_forms(charmap, english=english)
    if extras:
        try:
            files[moonfast.TABLE + ".BIN"] = moonfast.mend_table(files[moonfast.TABLE + ".BIN"], moon_forms)
        except moonfast.MoonFixError as e:
            raise SystemExit(f"{moonfast.NAME}：{e}") from None
    # the item-list fix goes in either way: it mends a bug of the game's own, and without it the
    # image still needs DLSPACE to clean up after that bug. So does the story fixes' part in the
    # game's own code, and the others' above, and - with no switch - the jump over the palette
    # allocator's debugging line (tools/nospace.py), the allocator handing a battle's enemies their
    # free slots from the top so the background behind them keeps its colours (tools/slotorder.py),
    # the script runner freeing the context node it leaked on every run (tools/ctxfree.py), the
    # virtual memory's swap going through XMS instead of DDS98\VM\V0000.BUF (tools/vmswap.py) and the
    # larger item bag (tools/bagexpand.py). The keys and the faster moon are extras.
    exe = files.get(exefix.FILE) or open(os.path.join(src, exefix.FILE), "rb").read()
    try:
        exe = expshow.mend_exe(statfix.apply_to(checkfix.mend_exe(storyfix.mend_exe(exefix.apply_to(exe)))))
        exe = vmswap.apply_to(ctxfree.apply_to(slotorder.apply_to(nospace.apply_to(exe))))
        exe = skillfix.mend_exe(bagexpand.apply_to(exe))
        if extras:
            exe = exekeys.apply_to(moonfast.mend_exe(exe))
        if rebalance_on:
            exe = rebalance.mend_exe(expgap.mend_exe(exe))
        files[exefix.FILE] = exe
    except (storyfix.StoryFixError, statfix.StatFixError, moonfast.MoonFixError, nospace.NoSpaceError,
            slotorder.SlotOrderError, ctxfree.CtxFreeError, vmswap.VmSwapError, bagexpand.BagError,
            skillfix.SkillError, rebalance.RebalanceError) as e:
        raise SystemExit(f"{exefix.FILE}：{e}") from None
    return dict(unmended=unmended, unchecked=unchecked, unshown=unshown, ungapped=ungapped, moon_forms=moon_forms, added=added)
