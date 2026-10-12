#!/usr/bin/env python3
"""Build three language-preserving enhancement patches with English interfaces through the existing game and web engines.

python tools/mkenhancements.py --english-image <English.hdi>  build game payloads, pages, documentation and ZIP packages
python tools/mkenhancements.py --pack-only  reuse build/enhancements game payloads after a documentation/UI edit
"""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import zipfile
import markdown

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
sys.path[:0] = [str(HERE), str(WORK)]
import nativebuild
import mapdoors
import webpayload
import nospace
import slotorder
import p2fields
import poolfix
import rebalance
import records
import tables
import enhancement_plan

STAGE = WORK / "build" / "enhancements"
OUT = WORK / "dist" / "English"
DOCS = WORK / "docs" / "enhancements"
PACKAGES = {
    "fixes": ("Giten Fixes (EN)", "Apply Fixes.html", "Giten_Fixed.hdi",
              "Gameplay repairs and quality-of-life improvements for the PC-98 game, preserving Japanese or tested English game text."),
    "art": ("Giten Windows Artwork (EN)", "Apply Windows Artwork.html", "Giten_WIN.hdi",
            "Windows remake artwork for the PC-98 game. Works independently, or with Fixes and Rebalance."),
    "rebalance": ("Giten Rebalance (EN)", "Apply Rebalance.html", "Giten_Rebalanced.hdi",
                  "Reworked combat and progression. Apply Fixes first; Windows artwork is optional."),
}


def load_files(directory):
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir()) if p.is_file()}


def build_files():
    for edition, rb in (("fixed", False), ("rebalance", True)):
        built = nativebuild.build(rebalance_on=rb)
        files = {**built["files"], **built["added"]}
        dest = STAGE / edition
        dest.mkdir(parents=True, exist_ok=True)
        # Only remove stale entries belonging to this generated payload directory.
        for p in dest.iterdir():
            if p.is_file() and p.name not in files:
                p.unlink()
        for name, blob in files.items():
            (dest / name).write_bytes(blob)


def forms(name, blob):
    """Accepted states are exact existing native/artwork outputs, never a relaxed executable match."""
    if blob is None:
        return [None]
    variants = [blob]
    if name.startswith("M0") and name.endswith(".BIN"):
        variants.append(mapdoors.remap_blob(blob)[0])
    if name == "DDS98.EXE":
        variants.append(slotorder.apply_to(nospace.apply_to(blob)))
    return sorted({hashlib.sha1(b).hexdigest() for b in variants})


def payload(kind, fixed, rebalanced):
    blobs = []
    def take(files):
        refs = []
        for name, data in sorted(files.items()):
            refs.append([name, len(blobs)])
            blobs.append(data)
        return refs
    manifest = {"cn": {}, "art": None}
    if kind == "art":
        files, hashes, exe = webpayload.art_part()
        manifest["art"] = {"files": take(files), "hashes": hashes, "exe": exe, "partition": {
            "header": "00000000000000000010000000aadb0100010000210000000600000067020000",
            "partition": "a18100000000010000000100000058024d532d444f5320362e32302020202020",
            "bpb": "eb45904e45432020352e3000040801000200070474f8060021000600c600000000000000800029151c1a35474954454e2020202020204641543132202020c600",
            "part": 50688, "total": 30393, "lastCylinder": 614}}
    else:
        original = load_files(WORK / "files" / "DDS98")
        if kind == "fixes":
            files = fixed
            required = {n: list(dict.fromkeys(forms(n, original.get(n)) + forms(n, b))) for n, b in files.items()}
        else:
            # Rebalance is a delta on the complete Fixes payload, including its shared prerequisites.
            files = {n: b for n, b in rebalanced.items() if b != fixed.get(n, original.get(n))}
            required = {n: list(dict.fromkeys(forms(n, fixed.get(n, original.get(n))) +
                                             forms(n, rebalanced.get(n, fixed.get(n, original.get(n))))))
                        for n in sorted(set(fixed) | set(files))}
        english = STAGE / 'english-adaptation'
        en_original = load_files(english / 'source')
        en_fixed = load_files(english / 'fixed')
        en_rebalanced = load_files(english / 'rebalance')
        exe_forms = {label: forms('DDS98.EXE', data['DDS98.EXE']) for label, data in
                     (('original', en_original), ('fixed', en_fixed), ('rebalance', en_rebalanced))}
        en_plan = enhancement_plan.compile_plan(en_original, en_fixed, en_rebalanced, kind, exe_forms)
        manifest["enhancement"] = {"kind": kind, "files": take(files), "requires": required, "english": en_plan}
    manifest["blobs"] = [len(b) for b in blobs]
    return webpayload.packed(manifest, blobs)[0]


def english_core():
    core = Path(webpayload.CORE).read_text(encoding="utf-8")
    messages = json.loads((HERE / "webpatch_en.json").read_text(encoding="utf-8"))
    for source, translated in messages.items():
        if source not in core:
            raise ValueError(f"English message source changed: {source}")
        core = core.replace(source, translated)
    # All user-facing Chinese messages have explicit English equivalents.
    for line in core.splitlines():
        if re.search(r"[\u3400-\u9fff]", line) and not line.lstrip().startswith("//"):
            raise ValueError(f"Untranslated core message: {line}")
    runtime = (HERE / 'enhancement_runtime.js').read_text(encoding='utf-8')
    return core.replace('  root.WebPatch =', runtime + '\n  root.WebPatch =')


def documentation():
    """English presentation of authoritative formula coefficients and balance record edits."""
    attributes = dict(zip(rebalance.ATTRS, ("Intuition", "Willpower", "Magic", "Intelligence", "Grace",
                                           "Strength", "Vitality", "Agility", "Dexterity", "Charm", "Luck")))
    sources = {**attributes, "gear_hit": "equipmentSwordAccuracy", "gear_atk": "equipmentSwordAttack",
               "gear_eva": "equipmentEvasion", "gear_def": "equipmentDefense", "gear_ghit": "equipmentGunAccuracy",
               "gear_gatk": "equipmentGunAndAmmoAttack", "mgear_eva": "equipmentMagicEvasion",
               "mgear_hit": "equipmentMagicAccuracy", "mgear_atk": "equipmentMagicAttack",
               "mgear_def": "equipmentMagicDefense", "lv": "level", "lead": "L", "dex_gun": "gunDexterity",
               "gun_bonus": "gunLevelBonus", "sw_lv": "swordSkillLevel", "gun_lv": "gunSkillLevel",
               "mg_lv": "magicSkillLevel", "cp_lv": "COMPSkillLevel"}
    values = dict(zip((row[0] for row in rebalance.FORMULAS),
                      ("Sword accuracy", "Sword attack", "Sword evasion", "Physical defense", "Gun accuracy",
                       "Gun attack (status screen)", "Gun evasion", "Magic accuracy", "Magic attack", "Magic evasion",
                       "Magic defense", "COMP accuracy", "COMP attack")))
    lines = ["# Formula and data reference", "", "## Derived battle stats", "",
             "Generated from the same coefficients used to patch the executable. Multiplications shown here already include equipment weights.", "",
             "| Statistic | Formula |", "| --- | --- |"]
    for key, _at, boosted, terms in rebalance.FORMULAS:
        formula = " + ".join(("" if c == 40 else f"{c / 40:g} * ") + sources[s] for s, c in terms)
        if boosted:
            formula = f"({formula}) * (2000 + L) / 2000"
        lines.append(f"| {values[key]} | `{formula}` |")
    lines += ["", "`gunLevelBonus` is `2 * (gunSkillLevel + 5)` when that skill level is at least 1, otherwise zero. "
              "`gunDexterity` is Dexterity for a human with an equipped gun, otherwise zero. `L` is the protagonist's Charm "
              "for allied demons when the protagonist has awakened COMP, otherwise zero. Skill levels in these formulas are human skill levels; demons use zero.",
              "", "The game rounds the total once and clamps derived values to 1–999. HP, damage, hit probability, growth, negotiation and other rules are described in REBALANCE.md.",
              "", "## Added learning candidates", "", "Japanese labels identify the original skill names; record IDs also apply to the English translation. The gun route's learn thresholds are 1, 5, 5, 10, 15, 20, 25, 35 and 35, in the order below. "
              "The original learning roll still decides acquisition.", "", "| Route | Skill ID | In-game name |", "| --- | --- | --- |"]
    names = poolfix.skill_names()
    ids = {name: i for i, name in names.items()}
    for pid, added in poolfix.ADD:
        route = {-3: "Magic", -2: "Gun"}[pid]
        for name in added:
            lines.append(f"| {route} | {ids[name]} | {name} |")
    lines += ["", "## Complete numerical edit ledger", "", "This ledger includes the shared Dantalion adjustment and every boss/Newton edit from the rebalanced data plan. "
              "Before/after values are the stored integer values against the original Japanese records. Resistance bytes below 250 represent twice their value as a damage percentage; "
              "250–255 are special codes, not ordinary percentages. Skill/equipment values are record IDs. Japanese names identify the source records; the same record IDs are used in the English translation. "
              "The same rows are available in Rebalance-Changes.csv. Executable formulas and learning-pool additions are documented separately above.",
              "", "| Profile | Record | In-game name | Field / record offset | Width | Original | Patched |", "| --- | --- | --- | --- | --- | --- | --- |"]
    field_names = {**attributes, "ＥＸＰ": "EXP", "魔货": "Currency", "ＭＡＧ": "MAG", "ＨＰ": "HP", "ＭＰ": "MP",
                   "等级": "Level", "ＣＰ": "CP", "月龄对应": "Moon table", "取得率": "Acquisition rate",
                   "会话类型": "Negotiation type", "速度": "Enemy speed", "行动模式": "AI action row"}
    demon_fields = {off: field_names[label] for off, _width, label in p2fields.FIELDS}
    demon_fields.update({p2fields.SKILLS_AT + i * 2: f"Skill slot {i + 1}" for i in range(p2fields.SKILL_SLOTS)})
    demon_fields.update({off: f"Equipment slot {i + 1}" for i, (off, _label) in enumerate(p2fields.EQUIP_AT)})
    demon_fields.update({p2fields.RESIST_AT + i: f"{label} resistance code" for i, label in enumerate(
        ("Physical", "Gun", "Fire", "Ice", "Force", "Electricity", "Expel", "Magic", "Curse", "Nerve"))})
    rows = []
    for profile, filename in (("Fixes", "balance.json"), ("Rebalance", "balance_redesign.json")):
        data = json.loads((WORK / filename).read_text(encoding="utf-8"))
        for target, edit in data["edits"].items():
            stem, index = records.parse(target)
            plain = records.plain_of((WORK / "files" / "DDS98" / (stem + ".BIN")).read_bytes())
            base = records.base_of(plain, target)
            name_at = p2fields.NAME_AT if index is None else tables.ITEM_HEADER[plain[base + 4]]
            native_name = bytes(plain[base + name_at:]).split(b"\0", 1)[0].decode("cp932").strip()
            for width in ("u8", "u16", "u32"):
                for offset, (old, new) in edit.get(width, {}).items():
                    off = int(offset, 16)
                    label = demon_fields[off] if index is None else "Equipment data"
                    row = [profile, target, native_name, f"{label} @0x{offset}", width, old, new]
                    rows.append(row)
                    lines.append("| " + " | ".join(str(v) for v in row) + " |")
    (DOCS / "REFERENCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (DOCS / "Rebalance-Changes.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(("Profile", "Record", "In-game name", "Field / record offset", "Width", "Original", "Patched"))
        writer.writerows(rows)
    order = ("README", "FIXES", "WINDOWS-ARTWORK", "REBALANCE", "REFERENCE", "TROUBLESHOOTING", "CREDITS", "VALIDATION")
    sections = [f'<section id="{name}">' + markdown.markdown((DOCS / (name + ".md")).read_text(encoding="utf-8"),
                extensions=["tables", "fenced_code"]) + "</section>" for name in order]
    toc = " · ".join(f'<a href="#{name}">{name.title().replace("-", " ")}</a>' for name in order)
    document = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>Giten Enhancement Documentation</title><style>body{font:17px/1.7 system-ui,sans-serif;background:#f4f1ea;color:#222;max-width:1000px;margin:auto;padding:32px}'
                'section{margin:50px 0}h1{border-bottom:2px solid #823628}h2{margin-top:32px}a{color:#823628}code{background:#e8e2d8;padding:2px 4px;overflow-wrap:anywhere}'
                'table{display:block;overflow-x:auto;border-collapse:collapse;font-size:14px}td,th{border:1px solid #ccc;padding:8px;text-align:left;vertical-align:top}th{background:#e8e2d8}'
                '</style><nav>' + toc + '</nav>' + "\n".join(sections) + '</html>')
    (DOCS / "Documentation.html").write_text(document, encoding="utf-8")


def page(kind, b64, core):
    title, _name, output, desc = PACKAGES[kind]
    css = webpayload.CSS
    prereq = "Use the output of Apply Fixes.html." if kind == "rebalance" else "Select a supported Japanese or tested English PC-98 game image."
    return (TEMPLATE.replace("{{TITLE}}", html.escape(title)).replace("{{DESC}}", html.escape(desc))
            .replace("{{PREREQ}}", prereq).replace("{{OUTPUT}}", output).replace("{{KIND}}", kind)
            .replace("{{CSS}}", css).replace("{{CORE}}", core.replace("</", "<\\/"))
            .replace("{{PAYLOAD}}", b64))


TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}}</title><style>{{CSS}}
main{max-width:850px;margin:40px auto;padding:0 24px}section{margin:24px 0;padding:24px;border:1px solid var(--line);background:var(--surface);border-radius:12px}
button,.download{display:inline-block;padding:12px 18px;margin:12px 12px 8px 0;border:0;border-radius:6px;background:var(--accent);color:var(--accent-ink);font:inherit;text-decoration:none}
button:disabled{opacity:.5}#drop{border:2px dashed var(--line);padding:20px;border-radius:8px}#drop.over{border-color:var(--accent)}
#log{overflow-wrap:anywhere;line-height:1.7}#log .error{color:var(--bad)}[hidden]{display:none!important}h1{font-size:clamp(26px,5vw,38px);line-height:1.2}input{max-width:100%}
</style></head><body><main>
<p>GITEN MEGAMI TENSEI · TOKYO MOKUSHIROKU</p><h1>{{TITLE}}</h1><p>{{DESC}}</p>
<p><strong>Supports the Japanese game and the tested English translation. Your game language is retained.</strong></p>
<p>For English play, apply the translation BPS first, then these enhancements. Script text edits can remain compatible; changed event logic or program code must pass the patch checks. See the compatibility table and tested BPS in <a href="Documentation.html">Documentation.html</a>.</p>
<section><h2>1. Choose your image</h2><p>{{PREREQ}} Your selected file is read only. The result is downloaded as a separate HDI.</p>
<div id="drop"><label for="image">Choose or drop an .hdi file</label><br><input id="image" type="file" accept=".hdi"></div>
<p id="selected">No image selected.</p><button id="apply" disabled>2. Apply patch</button>
<ol id="log" aria-live="polite"></ol><a id="save" class="download" hidden>3. Save {{OUTPUT}}</a></section>
<section><h2>Before playing</h2><p>Fixes and Windows Artwork can be applied in either order. Rebalance requires Fixes. Artwork can be added before or after Rebalance.</p>
<p>The PepsimanGB pre-made HDI uses its companion boot floppy. Keep that floppy and mount both disks in your PC-98 emulator. These patches preserve the existing DOS boot setup.</p>
<p>Use an in-game save when changing patches; make a backup first. Emulator save states contain the old running program and should not be used to switch editions.</p>
<p>For installation, features, controls, formulas, compatibility and credits, open <a href="Documentation.html">Documentation.html</a> or read the included English Markdown files.</p>
<p>Everything runs locally. No image is uploaded; the page has no external scripts, fonts or network requests. It requires a browser with DecompressionStream support for deflate-raw.</p></section>
</main><script>{{CORE}}</script>
<script type="text/plain" id="payload">{{PAYLOAD}}</script>
<script>
(() => {
  const input=document.getElementById('image'), button=document.getElementById('apply'), drop=document.getElementById('drop');
  const log=document.getElementById('log'), save=document.getElementById('save'), selected=document.getElementById('selected');
  let chosen, url, busy=false;
  function clearResult(){save.hidden=true;if(url){URL.revokeObjectURL(url);url=undefined;}log.replaceChildren();}
  function pick(file){if(busy)return;chosen=file;clearResult();selected.textContent=file?file.name:'No image selected.';button.disabled=!file;}
  function say(text,error=false){const li=document.createElement('li');li.textContent=text;if(error)li.className='error';log.appendChild(li);}
  input.addEventListener('change',()=>pick(input.files[0]));
  for(const name of ['dragenter','dragover'])drop.addEventListener(name,e=>{e.preventDefault();if(!busy)drop.classList.add('over');});
  drop.addEventListener('dragleave',()=>drop.classList.remove('over'));
  drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('over');if(e.dataTransfer.files.length===1)pick(e.dataTransfer.files[0]);});
  button.addEventListener('click',async()=>{
    if(!chosen||busy)return;busy=true;button.disabled=true;input.disabled=true;clearResult();
    try{
      if(!/\.hdi$/i.test(chosen.name))throw new Error('Select an .hdi hard disk image.');
      if(typeof DecompressionStream==='undefined')throw new Error('This browser lacks DecompressionStream. Open this page in a browser that supports deflate-raw.');
      say('Reading the patch and selected image...');
      await new Promise(resolve=>setTimeout(resolve,30));
      const p=await WebPatch.unpack(document.getElementById('payload').textContent.trim());
      const bytes=new Uint8Array(await chosen.arrayBuffer());
      const result=await WebPatch.enhance(bytes,p,'{{KIND}}',say);
      url=URL.createObjectURL(new Blob([result],{type:'application/octet-stream'}));
      save.href=url;save.download='{{OUTPUT}}';save.hidden=false;
      say('Finished. Save the new image below; the original file has not been changed.');
    }catch(e){say(String(e.message||e),true);}
    finally{busy=false;button.disabled=!chosen;input.disabled=false;}
  });
})();
</script></body></html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-only", action="store_true")
    parser.add_argument("--english-image", type=Path, help="Verified English BPS output used to rebuild the native English payload")
    args = parser.parse_args()
    if not args.pack_only:
        if args.english_image is None:
            parser.error('A native rebuild requires --english-image; use --pack-only to reuse accepted payloads')
        build_files()
        import english_enhancements
        english_enhancements.build(args.english_image, STAGE / 'english-adaptation')
    fixed, rebalanced = load_files(STAGE / "fixed"), load_files(STAGE / "rebalance")
    core = english_core()
    documentation()
    for kind, (title, filename, _output, _desc) in PACKAGES.items():
        folder = OUT / title
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_text(page(kind, payload(kind, fixed, rebalanced), core), encoding="utf-8")
        docs = list(DOCS.glob("*"))
        if not docs:
            raise ValueError("English documentation is missing")
        for source in docs:
            if source.is_file():
                (folder / source.name).write_bytes(source.read_bytes())
        manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt"}
        (folder / "SHA256SUMS.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(manifest.items())), encoding="utf-8")
        archive = WORK / "dist" / (title + ".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(folder.iterdir()):
                if p.is_file():
                    z.write(p, title + "/" + p.name)
        print(f"{archive}: {archive.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
