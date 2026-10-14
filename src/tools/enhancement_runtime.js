  // The grammar and edit plans are exported from the native build, not a second set of game fixes.
  function enhancementAtoms(data, grammar) {
    const parts = [];
    let pos = 0;
    const byte = () => { if (pos >= data.length) throw new PatchError('Truncated script operand.'); return data[pos++]; };
    const word = () => byte() | byte() << 8;
    let rel;
    function value() {
      const kind = byte(), at = pos;
      run(grammar.values[kind] || '');
      if ([1, 2, 5].includes(kind)) return u16(data, at);
      if (kind === 0) return data[at];
      if (kind === 4) return data[at] & 128 ? 0xFF00 | data[at] : data[at];
      return undefined;
    }
    function run(sig) {
      for (const c of sig) {
        if (c === 'b') byte();
        else if (c === 'w') word();
        else if (c === 'd') { word(); word(); }
        else if (c === 'r') { const field = pos, n = word(); rel.push([field, (pos + n) & 65535]); }
        else if (c === 'V') value();
        else if (c === 'L') { while (byte() !== 255) { if (byte()) run('r'); else run('bb'); } }
        else if (c === 'C') { let first; do { first = byte(); byte(); } while (first !== 255); }
        else if (c === 'D') { while (value() !== 65535) {} }
        else if (c === 'S') { const s = byte(); if (grammar.selBV.includes(s)) run('bV'); else if (grammar.selV.includes(s)) run('V'); }
        else if (c === 'M') { byte(); if ([0, 2].includes(byte())) byte(); }
        else if (c === 'B') { while (byte() !== 255) {} }
        else if (c === 'X') { if (byte()) run('bb'); else run('VVVVVV'); }
        else throw new PatchError('Unknown exported VM operand.');
      }
    }
    while (pos < data.length) {
      const start = pos, c = byte();
      rel = [];
      let text = false, code = c;
      if (c >= 0x81 && c <= 0x9F || c >= 0xE0 && c <= 0xFC) {
        const second = byte();
        text = second >= 0x40 && second <= 0x7E || second >= 0x80 && second <= 0xFC;
        code = c << 8 | second;
      } else if (c >= 0x20 && c <= 0x7E || c >= 0xA1 && c <= 0xDF) text = true;
      else {
        while (grammar.prefix[code] !== undefined) code = grammar.prefix[code] + byte();
        code = grammar.alias[code] === undefined ? code : grammar.alias[code];
        run(grammar.commands[code] || '');
        text = code === 10;
      }
      if (text && parts.length && parts[parts.length - 1].text) parts[parts.length - 1].end = pos;
      else parts.push({start, end:pos, text, rel});
    }
    for (const a of parts) {
      a.raw = data.slice(a.start, a.end);
      const clean = a.raw.slice(), refs = [];
      for (const [field, target] of a.rel) {
        let address;
        if (target === data.length) address = [parts.length, 0];
        else {
          const i = parts.findIndex(p => target === p.start || p.text && target >= p.start && target < p.end);
          address = i < 0 ? ['raw', u16(data, field)] : [i, target - parts[i].start];
        }
        refs.push([field - a.start, address]);
        put16(clean, field - a.start, 0);
      }
      a.desc = a.text ? ['T'] : [Array.from(clean, b => b.toString(16).padStart(2, '0')).join(''), refs];
    }
    return parts;
  }

  function enhancementMatch(parts, expected) {
    return parts.length === expected.length && parts.every((p, i) => {
      const e = expected[i];
      return e[0] === 'T' ? p.text && (e.length === 1 || same(p.raw, hex(e[1]))) :
        !p.text && JSON.stringify(p.desc) === JSON.stringify(e);
    });
  }

  function enhancementRecord(data, plan, grammar) {
    const parts = enhancementAtoms(data, grammar);
    if (enhancementMatch(parts, plan.after)) return data;
    if (plan.guard) throw new PatchError('Required Fixes instruction is missing or modified.');
    if (!enhancementMatch(parts, plan.before))
      throw new PatchError('Instruction signature or branch target conflicts with this patch.');
    const pieces = plan.recipe.map(x => x[0] === 'copy' ? parts[x[1]].raw : hex(x[1]));
    const offsets = [0];
    for (const b of pieces) offsets.push(offsets[offsets.length - 1] + b.length);
    if (offsets[offsets.length - 1] >= 65535) throw new PatchError('Patched script record is too long.');
    const out = new Uint8Array(offsets[offsets.length - 1]);
    pieces.forEach((b, i) => out.set(b, offsets[i]));
    plan.after.forEach((a, i) => {
      if (a[0] === 'T') return;
      for (const [local, target] of a[1]) {
        if (target[0] === 'raw') throw new PatchError('Patched script has an invalid branch.');
        const field = offsets[i] + local;
        put16(out, field, (offsets[target[0]] + target[1] - field - 2) & 65535);
      }
    });
    if (!enhancementMatch(enhancementAtoms(out, grammar), plan.after))
      throw new PatchError('Patched script failed structural verification.');
    return out;
  }

  function enhancementScript(data, plan, grammar) {
    const chunks = [];
    let pos = 0;
    while (pos < data.length) {
      if (pos + 2 > data.length || pos + 2 + u16(data, pos) > data.length) throw new PatchError('Truncated script chunk.');
      const length = u16(data, pos), chunk = data.subarray(pos, pos + 2 + length);
      const [, plain] = decrypt(chunk);
      if (plain.length < 2) throw new PatchError('Script chunk has no count.');
      const recs = [];
      let at = 2;
      while (at < plain.length) {
        if (at + 3 > plain.length) throw new PatchError('Truncated script record header.');
        const rid = plain[at];
        let size = u16(plain, at + 1), cond = null;
        at += 3;
        if (size === 65535) {
          if (at + 4 > plain.length) throw new PatchError('Truncated conditional record.');
          cond = [plain[at], plain[at + 1]]; size = u16(plain, at + 2); at += 4;
        }
        if (at + size > plain.length) throw new PatchError('Script record exceeds its chunk.');
        recs.push({rid, cond, data:plain.slice(at, at + size)}); at += size;
      }
      const count = u16(plain, 0), known = plan.counts.find(e => e[0] === chunks.length);
      if (count !== recs.length && !(known && count === known[1] && recs.length === known[2]))
        throw new PatchError('Unrecognized script record-count mismatch in chunk ' + chunks.length + '.');
      chunks.push(recs); pos += 2 + length;
    }
    for (const edit of plan.records) {
      try {
        const recs = chunks[edit.chunk];
        if (!recs) throw new PatchError('Missing chunk.');
        const hits = recs.filter(r => r.rid === edit.rid && JSON.stringify(r.cond) === JSON.stringify(edit.cond));
        if (edit.add !== undefined) {
          if (hits.length === 0) recs.push({rid:edit.rid, cond:edit.cond, data:hex(edit.add)});
          // A translator may supply this previously absent line. Keep that complete, printable record.
          else {
            if (hits.length !== 1) throw new PatchError('Added negotiation record is ambiguous.');
            const parts = enhancementAtoms(hits[0].data, grammar);
            if (!parts.length || parts[parts.length - 1].desc[0] !== '00' ||
                !parts.some(a => a.text && a.raw.some(b => b > 32)) ||
                parts.some(a => !a.text && a.desc[0] !== '00' && a.desc[0] !== '1e100101' &&
                  !a.desc[0].startsWith('1f01') && !a.desc[0].startsWith('1f02')))
              throw new PatchError('Existing negotiation line has unsupported control logic.');
          }
        } else {
          if (hits.length !== 1) throw new PatchError('Record identity is missing or ambiguous.');
          hits[0].data = enhancementRecord(hits[0].data, edit, grammar);
        }
      } catch (e) { throw new PatchError('chunk ' + edit.chunk + ', record ' + edit.rid.toString(16).toUpperCase() + ': ' + e.message); }
    }
    const encoded = chunks.map(recs => {
      const size = 2 + recs.reduce((n, r) => n + (r.cond === null ? 3 : 7) + r.data.length, 0);
      if (size > 65535) throw new PatchError('Patched script chunk is too long.');
      const plain = new Uint8Array(size); put16(plain, 0, recs.length);
      let at = 2;
      for (const r of recs) {
        plain[at] = r.rid; put16(plain, at + 1, r.cond === null ? r.data.length : 65535); at += 3;
        if (r.cond !== null) { plain.set(r.cond, at); put16(plain, at + 2, r.data.length); at += 4; }
        plain.set(r.data, at); at += r.data.length;
      }
      return encrypt(plain, size);
    });
    const out = new Uint8Array(encoded.reduce((n, b) => n + b.length, 0));
    let at = 0; for (const b of encoded) { out.set(b, at); at += b.length; }
    return out;
  }

  function enhancementFields(data, edits, base = 0, limit = data.length) {
    for (const [offset, oldHex, newHex] of edits) {
      const old = hex(oldHex), fixed = hex(newHex), at = base + offset;
      if (at < base || at + old.length > limit) throw new PatchError('Field exceeds record bounds.');
      const now = data.subarray(at, at + old.length);
      if (!same(now, old) && !same(now, fixed)) throw new PatchError('Field conflict at record offset 0x' + offset.toString(16) + '.');
      data.set(fixed, at);
    }
    return data;
  }

  function enhancementFile(name, data, plan, grammar) {
    if (plan.type === 'add') {
      const want = hex(plan.data);
      if (data !== null && !same(data, want)) throw new PatchError('Existing added resource conflicts.');
      return want;
    }
    if (data === null) throw new PatchError('Required file is missing.');
    if (plan.type === 'script') return enhancementScript(data, plan, grammar);
    if (plan.type === 'exact') {
      const want = hex(plan.data);
      if (name !== 'DDS98.EXE' && sha1hex(data) !== plan.before && !same(data, want)) throw new PatchError('Resource signature conflicts.');
      return want;
    }
    if (plan.type === 'fields') return enhancementFields(data.slice(), plan.edits);
    const [word, plain] = decrypt(data);
    if (word !== plain.length) throw new PatchError('Encrypted data length conflicts.');
    if (plan.type === 'cipher') enhancementFields(plain, plan.edits);
    else if (plan.type === 'table') {
      const count = u16(plain, 0);
      if (2 + count * 2 > plain.length) throw new PatchError('Invalid table pointer list.');
      for (const [rid, edits] of plan.records) {
        if (rid >= count) throw new PatchError('Missing table record ' + rid + '.');
        const base = u16(plain, 2 + rid * 2), limit = rid + 1 < count ? u16(plain, 4 + rid * 2) : plain.length;
        if (base < 2 + count * 2 || limit < base || limit > plain.length) throw new PatchError('Invalid table record bounds.');
        try { enhancementFields(plain, edits, base, limit); }
        catch (e) { throw new PatchError('record ' + rid + ': ' + e.message); }
      }
    } else throw new PatchError('Unknown enhancement plan.');
    return encrypt(plain, word);
  }

  function structuralEnhance(fs, plan, kind, say) {
    const hash = sha1hex(fs.read(`${DIR}/DDS98.EXE`));
    const state = Object.keys(plan.exe).find(k => plan.exe[k].includes(hash));
    if (kind === 'fixes' && state === 'rebalance') throw new PatchError('This image already has Rebalance. Fixes cannot downgrade it.');
    if (kind === 'rebalance' && state === 'original') throw new PatchError('Apply Fixes before Rebalance.');
    for (const [name, guard] of Object.entries(plan.guards)) {
      const before = fs.read(`${DIR}/${name}`);
      try {
        const checked = enhancementFile(name, before, guard, plan.grammar);
        if (before === null || !same(before, checked)) throw new PatchError('Required Fixes data is missing.');
      } catch (e) { throw new PatchError(name + ': ' + e.message + ' Apply Fixes first. No output was created.'); }
    }
    const files = {};
    for (const [name, edit] of Object.entries(plan.files)) {
      try { files[name] = enhancementFile(name, fs.read(`${DIR}/${name}`), edit, plan.grammar); }
      catch (e) { throw new PatchError(name + ': ' + e.message + ' No output was created.'); }
    }
    translate(fs, {files, drop:[], autoexec:null}, say);
    say('Applied checked record and field edits. Existing English text, saves and DOS boot files are preserved.');
  }

  // The add-ons (tools/addons.py) on a Japanese or English image, with or without the other patches. The image's
  // language is what DDS98.EXE says: every byte the English translation changes there (a.lang) holds either all of
  // the Japanese game's values or all of the translation's; no other patch writes them. The question goes in that
  // language. A Chinese image keeps its add-ons on its own Chinese patch page.
  function addonLanguage(fs, a) {
    if (fs.find(`${DIR}/CNFONT.DAT`) !== null)
      throw new PatchError('This image has the Chinese translation. Add or remove its add-ons with the Chinese patch page. No output was created.');
    const exe = fs.read(`${DIR}/DDS98.EXE`);
    if (exe === null) throw new PatchError('DDS98\\DDS98.EXE was not found. Select a Giten game image.');
    const all = lang => a.lang.every(r => same(exe.subarray(r.at, r.at + r[lang].length), r[lang]));
    if (all('en')) return 'en';
    if (all('jp')) return 'jp';
    throw new PatchError('DDS98.EXE is neither the Japanese game nor the tested English translation. No output was created.');
  }

  function addonsFor(a, lang) {
    return {...a, target: {...a.target, data: a.target.texts[lang]}};
  }

  // addons.shortfall: the clusters the image lacks for the change, taken in ADDONS order (a removal frees its file's
  // clusters before the next add-on; DDS98.EXE is rewritten at its own size).
  function addonShortfall(fs, a, want, have) {
    let free = fs.freeClusters().length, low = free;
    for (const name of ADDONS) {
      if (!(name in want) || want[name] === have[name]) continue;
      const file = name === 'target' ? a.target : a.pad;
      if (want[name]) free -= Math.ceil(file.data.length / fs.cs);
      else free += Math.ceil(fs.find(`${DIR}/${file.name}`).size / fs.cs);
      low = Math.min(low, free);
    }
    return Math.max(0, -low);
  }

  // tools/hdigrow.py step for step (the user, 2026-10-13: grow the disk when the add-ons do not fit): the image grown
  // by the fewest whole cylinders at its end that give its one DOS volume `more` new clusters, all free. Only a disk
  // the volume already fills is grown: the header's size is the image's and its geometry's, one partition entry
  // reaching the last cylinder, a FAT12 volume with a 16-bit sector count ending at the disk's end, the FAT's
  // entries past it zero and room in the FAT. The header's size and cylinders, the entry's end cylinder and the BPB's
  // sector count follow the new cylinders. -> [the new image, cylinders added]
  function addonGrow(img, more) {
    const raw = img.raw, hdr = img.hdr, sect = u32(raw, 16), spt = u32(raw, 20), heads = u32(raw, 24), cyls = u32(raw, 28);
    const size = raw.length - hdr, entry = hdr + sect;
    const fail = why => new PatchError('The disk has no room for the add-ons and cannot be grown: ' + why + '. No output was created.');
    if (u32(raw, 12) !== size || size !== cyls * heads * spt * sect) throw fail("the HDI header's size does not match the image");
    if (raw.subarray(entry + 32, hdr + 2 * sect).some(v => v !== 0)) throw fail('the disk has more than one partition');
    if (u16(raw, entry + 14) !== cyls - 1) throw fail("the partition does not reach the disk's last cylinder");
    const fs = new Fat(img.disk, img.part);
    const overhead = fs.reserved + fs.fats * fs.spf + fs.rootSectors, total16 = u16(img.disk, img.part + 19);
    if (total16 === 0 || Math.floor((total16 - overhead) / fs.spc) >= 4085) throw fail('the volume is not FAT12 with a 16-bit sector count');
    const tail = size - (img.part + total16 * fs.bps);
    if (tail < 0 || tail >= fs.bps) throw fail("the volume does not end at the disk's end");
    const cyl = heads * spt * sect, max = fs.maxCluster();
    let k, total, top;
    for (k = 1; ; k++) {
      total = Math.floor((size + k * cyl - img.part) / fs.bps);
      if (total > 0xFFFF || Math.floor((total - overhead) / fs.spc) >= 4085)
        throw fail(`the volume cannot gain ${more} more clusters and stay FAT12`);
      top = 1 + Math.floor((total - overhead) / fs.spc);
      if (top + (top >> 1) + 1 >= fs.spf * fs.bps) throw fail('the FAT has no room for more clusters');
      if (top - max >= more) break;
    }
    for (let c = max + 1; c <= top; c++) if (fs.getFat(c) !== 0) throw fail("the FAT's entries past the volume are not empty");
    const out = new Uint8Array(raw.length + k * cyl);
    out.set(raw);
    put32(out, 12, size + k * cyl);
    put32(out, 28, cyls + k);
    put16(out, entry + 14, cyls + k - 1);
    put16(out, hdr + img.part + 19, total);
    return [openHdi(out), k];
  }

  // What the add-on page shows for a chosen image: {lang: 'jp' | 'en', addons: {target, pad}}.
  function addonInspect(bytes, p) {
    const img = opened(bytes);
    const fs = new Fat(img.disk, img.part);
    const lang = addonLanguage(fs, p.addons);
    try { return {lang, addons: addonState(fs, addonsFor(p.addons, lang))}; }
    catch (e) { if (e instanceof PatchError) throw new PatchError(e.message + '. No output was created.'); throw e; }
  }

  // Each add-on in or out as want ({target, pad}: true in, false out) says: a new array, the given one left alone.
  // With nothing to change it refuses.
  function addonEnhance(bytes, p, say, want) {
    if (!p.addons || !p.addons.lang) throw new PatchError('This page has no add-on payload.');
    let img = opened(bytes);
    let fs = new Fat(img.disk, img.part);
    const lang = addonLanguage(fs, p.addons);
    const a = addonsFor(p.addons, lang);
    let have;
    try { have = addonState(fs, a); }
    catch (e) { if (e instanceof PatchError) throw new PatchError(e.message + '. No output was created.'); throw e; }
    if (!want || !ADDONS.some(n => n in want && want[n] !== have[n]))
      throw new PatchError('This image already has the add-ons as ticked. Nothing to change.');
    say(lang === 'en' ? 'English translation detected; the target question is in English.' :
        'Japanese game detected; the target question is in Japanese.');
    const more = addonShortfall(fs, a, want, have);
    if (more) {
      const [grown, k] = addonGrow(img, more);
      img = grown;
      fs = new Fat(img.disk, img.part);
      say(`The disk had no room for the add-ons' files: grew the image by ${k} cylinder${k === 1 ? '' : 's'} ` +
          `(${k * u32(img.raw, 20) * u32(img.raw, 24) * u32(img.raw, 16)} bytes) at its end.`);
    }
    applyAddons(fs, a, want, say);
    say('Nothing else in the image was changed. Saves and the DOS boot configuration are preserved.');
    return img.raw;
  }
