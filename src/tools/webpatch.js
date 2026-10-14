// webpatch.js - the patch core of the web patches (tools/mkwebpatch.py), the same code in the browser and in
// Node (tools/webpatch_test.py). It is tools/cnpatch.py and tools/winpatch.py over tools/fat12.py, fat12w.py,
// mapdoors.py, ddscrypt.py and fcimage.entries, step for step, so an image it makes is byte for byte the one the
// Python patches and tools/autoboot.py make of the same image:
//
//   translate(fs, cn)   cnpatch.apply_to: the files of the edition into DDS98\ (written over, or made), the drop
//                       list taken out, AUTOEXEC.BAT completely replaced by the payload's startup script; and when the image
//                       already holds the Windows art (FC1400 with a door per wall set), every map section's door
//                       byte set to its wall set, since the map files come in with the game's own
//   artwork(fs, win)    winpatch.apply_to: each art file checked against the original it replaces and the file it
//                       makes (SHA-1), written; the door bytes; DDS98.EXE's two allocator fixes (tools/nospace.py,
//                       tools/slotorder.py), whose original and fixed bytes the payload carries
//
//   inspect / retouch   tools/cnretouch.py: an image that already carries the Chinese version - its edition, its
//                       saves, whether its negotiation scripts and its battle pacing are this release's, which art
//                       it has, its options, which add-ons - and this release's negotiation text (the scripts, the
//                       glyphs merged into its font), its battle pacing (the battle message files, the program's
//                       sites of tools/holdshow.py), the options, and/or the other art written into it: artwork for
//                       the Windows art, the game's own pictures and door bytes back for the PC-98 art; the add-ons
//                       in or out; or, on an image without saves, the other edition's whole patch
//   applyOptions        tools/options.apply: the player's two options, 月相加速 (DDS98.EXE's sites, コアシールド's
//                       description in ET0001) and 等级差经验 (DDS98.EXE's sites, MS00DD.BIN), each in or out
//   applyAddons         tools/addons.apply: 选择对象时暂停 (DDS98.EXE's sites, DDS98\MS00D9.BIN) and 手柄操作
//                       (DDS98\DDS98.COM), each into the image or out of it, after everything else
//
// The page reads the chosen image first. A Japanese one gets translate for the edition the player picked, the options
// they changed, artwork on the result when they picked the Windows art, and the add-ons they ticked: one patch takes it
// to the chosen Giten_CN.hdi. A Chinese one gets retouch with what the player picked; its edition changes only when it
// holds no save (原版 and 再平衡版 saves do not carry over). Errors are PatchError with the Python patches' messages.
(function (root) {
  "use strict";

  class PatchError extends Error {}

  const DIR = "DDS98";
  const SHARED_DOORS = 5;                      // the game's own FC1400: five doors the wall sets share
  const WALL_AT = 0x22, DOOR_AT = 0x24, NEED = 0x26;
  const sjis = new TextDecoder("shift_jis");

  const u16 = (b, o) => b[o] | (b[o + 1] << 8);
  const u32 = (b, o) => (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0;
  function put16(b, o, v) { b[o] = v & 0xFF; b[o + 1] = (v >> 8) & 0xFF; }
  function put32(b, o, v) { b[o] = v & 0xFF; b[o + 1] = (v >> 8) & 0xFF; b[o + 2] = (v >> 16) & 0xFF; b[o + 3] = (v >>> 24) & 0xFF; }
  function concat(parts) {
    let n = 0;
    for (const p of parts) n += p.length;
    const out = new Uint8Array(n);
    let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }
  function same(a, b) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }
  // Names are compared without case.
  const upper = s => s.toUpperCase();
  const ascii = s => new TextEncoder().encode(s);

  // ---- the HDI and its partition (fat12.open_hdi)
  function openHdi(raw) {
    const hdr = u32(raw, 8);
    const disk = raw.subarray(hdr);
    const sect = u32(raw, 16), spt = u32(raw, 20), heads = u32(raw, 24);
    // PC-98 partition table in sector 1: dumps of this game come with 256- and 512-byte sectors alike
    const pt = disk.subarray(sect, sect + 32);
    const lba = (u16(pt, 10) * heads + pt[9]) * spt + pt[8];
    return {raw, hdr, disk, sect, part: lba * sect};
  }

  // tools/autoboot.py: NEC's menu IPL keeps this flag six bytes before the sector's end, for both dump sizes.
  function autoboot(img) {
    const boot = img.disk.subarray(0, img.sect);
    if (!same(boot.subarray(4, 8), ascii("IPL1")) || !same(boot.subarray(-2), new Uint8Array([0x55, 0xAA])))
      throw new PatchError("镜像不是本作使用的 NEC 启动菜单，无法安全设置自动启动。");
    const at = img.sect - 6;
    if (boot[at] !== 0 && boot[at] !== 0x80)
      throw new PatchError(`镜像的自动启动标志异常（${boot[at]}），没有生成镜像。`);
    boot[at] = 0x80;
  }

  // ---- FAT12 / FAT16 (fat12.Fat12 + fat12w.Fat12W)
  class Fat {
    constructor(data, base) {
      this.data = data;
      this.base = base;
      const b = data.subarray(base, base + 64);
      this.bps = u16(b, 11);
      this.spc = b[13];
      this.reserved = u16(b, 14);
      this.fats = b[16];
      this.rootEntries = u16(b, 17);
      this.total = u16(b, 19) || u32(b, 32);
      this.spf = u16(b, 22);
      this.rootSectors = Math.floor((this.rootEntries * 32 + this.bps - 1) / this.bps);
      this.fatOff = this.reserved * this.bps;
      this.rootOff = (this.reserved + this.fats * this.spf) * this.bps;
      this.dataOff = this.rootOff + this.rootSectors * this.bps;
      this.cs = this.bps * this.spc;
      const dataSectors = this.total - (this.reserved + this.fats * this.spf + this.rootSectors);
      this.bits = Math.floor(dataSectors / this.spc) < 4085 ? 12 : 16;
      this.eoc = this.bits === 12 ? 0xFFF : 0xFFFF;
      this.firstReserved = this.eoc - 0xF;
    }
    fatAt(i) { return this.base + this.fatOff + i * this.spf * this.bps; }
    getFat(c) {
      const f = this.fatAt(0), d = this.data;
      if (this.bits === 16) return d[f + c * 2] | (d[f + c * 2 + 1] << 8);
      const o = f + c + (c >> 1);
      const v = d[o] | (d[o + 1] << 8);
      return (c & 1) ? (v >> 4) : (v & 0x0FFF);
    }
    setFat(c, value) {
      const d = this.data;
      for (let i = 0; i < this.fats; i++) {
        const f = this.fatAt(i);
        if (this.bits === 16) { d[f + c * 2] = value & 0xFF; d[f + c * 2 + 1] = (value >> 8) & 0xFF; continue; }
        const o = f + c + (c >> 1);
        let cur = d[o] | (d[o + 1] << 8);
        cur = (c & 1) ? ((cur & 0x000F) | ((value & 0x0FFF) << 4)) : ((cur & 0xF000) | (value & 0x0FFF));
        d[o] = cur & 0xFF;
        d[o + 1] = (cur >> 8) & 0xFF;
      }
    }
    clusterOff(c) { return this.base + this.dataOff + (c - 2) * this.cs; }
    chain(start) {
      const out = [], seen = new Set();
      let c = start;
      while (c >= 2 && c < this.firstReserved && !seen.has(c)) { seen.add(c); out.push(c); c = this.getFat(c); }
      return out;
    }
    readChain(start, size) {
      const parts = this.chain(start).map(c => this.data.subarray(this.clusterOff(c), this.clusterOff(c) + this.cs));
      const all = concat(parts);
      return size === undefined ? all : all.slice(0, size);
    }
    readDir(start) {
      let raw, locs;
      if (start === null) {
        const o = this.base + this.rootOff;
        raw = this.data.slice(o, o + this.rootSectors * this.bps);
        locs = [];
        for (let i = 0; i < raw.length / 32; i++) locs.push(o + i * 32);
      } else {
        raw = this.readChain(start);
        locs = [];
        const per = this.cs / 32;
        for (const c of this.chain(start)) for (let i = 0; i < per; i++) locs.push(this.clusterOff(c) + i * 32);
      }
      const out = [];
      for (let i = 0; i < Math.floor(raw.length / 32); i++) {
        const e = raw.subarray(i * 32, (i + 1) * 32);
        if (e[0] === 0x00) break;
        if (e[0] === 0xE5 || (e[11] & 0x0F) === 0x0F) continue;
        const name = sjis.decode(e.subarray(0, 8)).replace(/\s+$/, "");
        const ext = sjis.decode(e.subarray(8, 11)).replace(/\s+$/, "");
        out.push({name: ext ? `${name}.${ext}` : name, attr: e[11], cluster: u16(e, 26), size: u32(e, 28),
                  isDir: !!(e[11] & 0x10), entryOff: locs[i]});
      }
      return out;
    }
    *walk(cluster = null, path = "") {
      for (const e of this.readDir(cluster)) {
        if (e.name === "." || e.name === "..") continue;
        const full = path ? `${path}/${e.name}` : e.name;
        if (e.isDir) yield* this.walk(e.cluster, full);
        else yield [full, e];
      }
    }
    find(path) {
      const parts = path.replace(/^\/+|\/+$/g, "").split("/");
      let cur = null;
      for (let i = 0; i < parts.length; i++) {
        const want = upper(parts[i]);
        let e;
        for (const x of this.readDir(cur)) if (upper(x.name) === want) e = x;      // the last of a name wins
        if (e === undefined) return null;
        if (i === parts.length - 1) return e;
        cur = e.cluster;
      }
      return null;
    }
    read(path) {
      const e = this.find(path);
      return e === null ? null : this.readChain(e.cluster, e.size);
    }
    maxCluster() {
      const dataSectors = this.total - (this.reserved + this.fats * this.spf + this.rootSectors);
      return 1 + Math.floor(dataSectors / this.spc);
    }
    freeClusters() {
      const out = [];
      for (let c = 2; c <= this.maxCluster(); c++) if (this.getFat(c) === 0) out.push(c);
      return out;
    }
    alloc(n) {
      const free = this.freeClusters();
      if (free.length < n) throw new PatchError(`镜像里的空间不够：需要 ${n} 个簇，只剩 ${free.length} 个`);
      const chain = free.slice(0, n);
      chain.forEach((c, i) => this.setFat(c, i + 1 < n ? chain[i + 1] : this.eoc));
      return chain;
    }
    freeChain(start) { for (const c of this.chain(start)) this.setFat(c, 0); }
    writeClusters(chain, payload) {
      const buf = new Uint8Array(chain.length * this.cs);
      buf.set(payload);
      chain.forEach((c, i) => this.data.set(buf.subarray(i * this.cs, (i + 1) * this.cs), this.clusterOff(c)));
    }
    replace(path, payload) {
      const e = this.find(path);
      if (e === null) throw new PatchError(`镜像里没有 ${path}`);
      const need = Math.max(1, Math.floor((payload.length + this.cs - 1) / this.cs));
      let chain = e.cluster ? this.chain(e.cluster) : [];
      if (chain.length !== need) {
        if (chain.length) this.freeChain(e.cluster);
        chain = this.alloc(need);
        put16(this.data, e.entryOff + 26, chain[0]);
      }
      this.writeClusters(chain, payload);
      put32(this.data, e.entryOff + 28, payload.length);
      return chain.length;
    }
    remove(path) {
      const e = this.find(path);
      if (e === null) throw new PatchError(`镜像里没有 ${path}`);
      if (e.isDir) throw new PatchError(`${path} 是文件夹`);
      if (e.cluster) this.freeChain(e.cluster);
      this.data[e.entryOff] = 0xE5;
    }
    *dirSlots(dirPath) {
      if (dirPath === null) {
        const b = this.base + this.rootOff;
        for (let i = 0; i < this.rootEntries; i++) yield b + i * 32;
        return;
      }
      const e = this.find(dirPath);
      if (e === null || !e.isDir) throw new PatchError(`镜像里没有文件夹 ${dirPath}`);
      const per = this.cs / 32;
      for (const c of this.chain(e.cluster)) for (let i = 0; i < per; i++) yield this.clusterOff(c) + i * 32;
    }
    create(dirPath, name, payload, attr = 0x20) {
      const dot = name.indexOf(".");
      const nm = dot < 0 ? name : name.slice(0, dot), ext = dot < 0 ? "" : name.slice(dot + 1);
      const raw = new TextEncoder().encode(upper(nm).padEnd(8).slice(0, 8) + upper(ext).padEnd(3).slice(0, 3));
      let slot = null;
      for (const off of this.dirSlots(dirPath)) {
        const first = this.data[off];
        if (first === 0x00 || first === 0xE5) {
          if (slot === null) slot = off;
          if (first === 0x00) break;
        } else if (same(this.data.subarray(off, off + 11), raw)) {
          this.replace(dirPath ? `${dirPath}/${name}` : name, payload);
          return;
        }
      }
      if (slot === null) throw new PatchError(`${dirPath} 里没有空的目录项`);
      const need = Math.max(1, Math.floor((payload.length + this.cs - 1) / this.cs));
      const chain = this.alloc(need);
      this.writeClusters(chain, payload);
      const ent = new Uint8Array(32);
      ent.set(raw, 0);
      ent[11] = attr;
      put16(ent, 22, 0x6000);                  // time 12:00:00
      put16(ent, 24, 0x38BC);                  // date 1998-05-28 (matches siblings)
      put16(ent, 26, chain[0]);
      put32(ent, 28, payload.length);
      this.data.set(ent, slot);
    }
  }

  // ---- the data-file cipher (ddscrypt) and FC entries (fcimage.entries)
  function decrypt(data) {
    const w = u16(data, 0);
    let state = (w & 0xFF) ^ (w >> 8);
    const out = new Uint8Array(data.length - 2);
    for (let i = 2; i < data.length; i++) { out[i - 2] = data[i] ^ state; state = data[i]; }
    return [w, out];
  }
  function encrypt(plain, w) {
    let state = (w & 0xFF) ^ (w >> 8);
    const out = new Uint8Array(plain.length + 2);
    put16(out, 0, w);
    for (let i = 0; i < plain.length; i++) { const c = plain[i] ^ state; out[i + 2] = c; state = c; }
    return out;
  }
  function fcEntryCount(data) {
    let pos = 0, n = 0;
    while (pos < data.length) {
      if (pos + 4 > data.length) throw new PatchError("FC1400.BIN 的格式不对：条目长度不完整");
      const len = u32(data, pos);
      if (pos + 4 + len > data.length) throw new PatchError("FC1400.BIN 的格式不对：条目超出文件末尾");
      n++;
      pos += 4 + len;
    }
    return n;
  }

  // ---- the door bytes (mapdoors)
  function* sections(plain) {
    if (plain.length < 6) return;
    const cnt = u16(plain, 4);
    if (cnt === 0 || 6 + 2 * cnt > plain.length) return;
    for (let i = 0; i < cnt; i++) {
      const o = u16(plain, 6 + 2 * i);
      if (o + NEED > plain.length || plain[o + WALL_AT] === 0xFF) continue;
      yield [o, plain[o + WALL_AT]];
    }
  }
  function remapBlob(data) {
    const [w, plain] = decrypt(data);
    const out = plain.slice();
    let n = 0;
    for (const [o, wall] of sections(plain)) if (out[o + DOOR_AT] !== wall) { out[o + DOOR_AT] = wall; n++; }
    return n ? [encrypt(out, w), n] : [data, 0];
  }
  function remapImage(fs) {
    let files = 0, secs = 0;
    const d = fs.find(DIR);
    if (d === null) return [0, 0];
    for (const e of fs.readDir(d.cluster)) {
      const name = upper(e.name);
      if (e.isDir || !name.startsWith("M0") || !name.endsWith(".BIN")) continue;
      const [blob, n] = remapBlob(fs.readChain(e.cluster, e.size));
      if (!n) continue;
      fs.replace(`${DIR}/${e.name}`, blob);
      files++;
      secs += n;
    }
    return [files, secs];
  }
  const perWall = fc1400 => fcEntryCount(fc1400) > SHARED_DOORS;

  // ---- the translation (cnpatch.apply_to on an opened image)
  function translate(fs, cn, say) {
    if (fs.find(`${DIR}/DDS98.EXE`) === null) throw new PatchError("镜像里没有 DDS98\\DDS98.EXE，这不是本作的镜像");
    let wrote = 0, made = 0;
    for (const name of Object.keys(cn.files).sort()) {
      if (fs.find(`${DIR}/${name}`) === null) { fs.create(DIR, name, cn.files[name]); made++; }
      else { fs.replace(`${DIR}/${name}`, cn.files[name]); wrote++; }
    }
    let gone = 0;
    for (const name of cn.drop) {
      const under = name.endsWith("/") ? name : name + "/";      // a folder's files ("DDS98/VM/")
      const hits = [];
      for (const [n] of fs.walk()) if (upper(n) === name || upper(n).startsWith(under)) hits.push(n);
      for (const n of hits) { fs.remove(n); gone++; }
    }
    if (cn.autoexec !== null) {
      const e = fs.find("AUTOEXEC.BAT");
      if (e === null) fs.create(null, "AUTOEXEC.BAT", cn.autoexec);
      else fs.replace("AUTOEXEC.BAT", cn.autoexec);
    }
    say(`写入 ${wrote} 个文件，新增 ${made} 个，删除 ${gone} 个` +
        (cn.autoexec !== null ? "，并改写了 AUTOEXEC.BAT" : ""));
    const fc = fs.read(`${DIR}/FC1400.BIN`);
    if (fc !== null && perWall(fc)) {
      const [nMaps, nSec] = remapImage(fs);
      say(`地图门号：镜像里是 Windows 素材版的门，${nMaps} 个文件、${nSec} 个分区改为跟随墙套`);
    }
  }

  // ---- the Windows art (winpatch.apply_to on an opened image); sha1 is async (the caller's)
  // nospace.state / slotorder.state: 'orig' or 'fixed' at every site, else the message winpatch.exe_state gives
  function exeForm(exe, sites, message) {
    const forms = new Set();
    for (const s of sites) {
      const now = exe.subarray(s.at, s.at + s.orig.length);
      if (same(now, s.orig)) forms.add("orig");
      else if (same(now, s.fixed)) forms.add("fixed");
      else throw new PatchError(message);
    }
    if (forms.size !== 1) throw new PatchError(message);
    return [...forms][0];
  }

  async function artwork(fs, win, sha1, say, complete) {
    if (fs.find(`${DIR}/DDS98.EXE`) === null) throw new PatchError("镜像里没有 DDS98\\DDS98.EXE，这不是本作的镜像");
    const exe = fs.read(`${DIR}/DDS98.EXE`);
    const printed = exeForm(exe, win.exe.nospace, "DDS98.EXE 里调色板报错（no space）那一处既不是原样也不是已屏蔽的内容，" +
                            "补丁不认识这个版本的程序，没有写入任何东西。");
    const order = exeForm(exe, win.exe.slotorder, "DDS98.EXE 里分配颜色槽的那两处既不是原样也不是修改后的内容，" +
                          "补丁不认识这个版本的程序，没有写入任何东西。");
    const state = {ready: [], done: [], missing: [], other: []};
    for (const name of Object.keys(win.files).sort()) {
      const blob = fs.read(`${DIR}/${name}`);
      if (blob === null) { state.missing.push(name); continue; }
      const got = await sha1(blob);
      if (got === win.hashes[name].now) state.done.push(name);
      else if (got === win.hashes[name].was) state.ready.push(name);
      else state.other.push(name);
    }
    say(`${Object.keys(win.files).length} 个素材文件：${state.ready.length} 个待替换，${state.done.length} 个已经是补丁版，` +
        `${state.missing.length} 个镜像里没有，${state.other.length} 个被别的改动动过`);
    if (state.other.length) {
      say("被动过的：" + state.other.join("、"));
      throw new PatchError("这些文件不是补丁认识的原样，直接覆盖会把那边的改动抹掉，补丁没有写入。");
    }
    const todo = state.ready.concat(state.missing);
    if (todo.length) {
      let need = 0;
      for (const name of state.ready) {
        const e = fs.find(`${DIR}/${name}`);
        need += Math.floor((win.files[name].length + fs.cs - 1) / fs.cs) - (e.cluster ? fs.chain(e.cluster).length : 0);
      }
      for (const name of state.missing) need += Math.floor((win.files[name].length + fs.cs - 1) / fs.cs);
      const free = fs.freeClusters().length;
      if (need > free) throw new PatchError(`镜像里的空间不够：还要 ${need * fs.cs} 字节，只剩 ${free * fs.cs} 字节。`);
      let wrote = 0, made = 0;
      const delta = name => {
        const e = fs.find(`${DIR}/${name}`);
        return Math.ceil(win.files[name].length / fs.cs) - (e && e.cluster ? fs.chain(e.cluster).length : 0);
      };
      // Release shrinking resources before growing others; the preflight checks net capacity.
      for (const name of todo.sort((a, b) => delta(a) - delta(b) || a.localeCompare(b))) {
        if (fs.find(`${DIR}/${name}`) === null) { fs.create(DIR, name, win.files[name]); made++; }
        else { fs.replace(`${DIR}/${name}`, win.files[name]); wrote++; }
      }
      say(`写入 ${wrote} 个文件` + (made ? `，新增 ${made} 个` : "") + `，镜像里还剩 ${(free - need) * fs.cs} 字节`);
    }
    const [nMaps, nSec] = remapImage(fs);
    say(nSec ? `地图门号：${nMaps} 个文件、${nSec} 个分区改为跟随墙套` : "地图门号：已经全部跟随墙套");
    let newExe = exe;
    for (const [form, sites, done, already] of [
        [printed, win.exe.nospace, "屏蔽调色板报错（no space）", "调色板报错已经屏蔽"],
        [order, win.exe.slotorder, "战斗中敌人从高位取颜色槽，背景不再被染色", "战斗颜色槽已经从高位分配"]]) {
      if (form === "orig") {
        newExe = newExe.slice();
        for (const s of sites) newExe.set(s.fixed, s.at);
        say(`DDS98.EXE：${done}`);
      } else say(`DDS98.EXE：${already}`);
    }
    if (newExe !== exe) fs.replace(`${DIR}/DDS98.EXE`, newExe);
    if (!complete && !todo.length && !nSec && newExe === exe)
      throw new PatchError("这个镜像里的素材已经全是补丁版了，没有要写的。");
  }

  // ---- SHA-1 (hex), for the art files' checks; plain code, so a page opened from disk needs nothing else
  function sha1hex(bytes) {
    const ml = bytes.length;
    const words = ((ml + 8) >> 6) + 1;
    const w = new Uint32Array(words * 16);
    for (let i = 0; i < ml; i++) w[i >> 2] |= bytes[i] << (24 - (i % 4) * 8);
    w[ml >> 2] |= 0x80 << (24 - (ml % 4) * 8);
    w[words * 16 - 1] = (ml * 8) >>> 0;
    w[words * 16 - 2] = Math.floor(ml / 0x20000000);
    let h0 = 0x67452301, h1 = 0xEFCDAB89, h2 = 0x98BADCFE, h3 = 0x10325476, h4 = 0xC3D2E1F0;
    const x = new Uint32Array(80);
    for (let blk = 0; blk < words * 16; blk += 16) {
      for (let t = 0; t < 16; t++) x[t] = w[blk + t];
      for (let t = 16; t < 80; t++) { const v = x[t - 3] ^ x[t - 8] ^ x[t - 14] ^ x[t - 16]; x[t] = (v << 1) | (v >>> 31); }
      let a = h0, b = h1, c = h2, d = h3, e = h4;
      for (let t = 0; t < 80; t++) {
        let f, k;
        if (t < 20) { f = (b & c) | (~b & d); k = 0x5A827999; }
        else if (t < 40) { f = b ^ c ^ d; k = 0x6ED9EBA1; }
        else if (t < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDC; }
        else { f = b ^ c ^ d; k = 0xCA62C1D6; }
        const tmp = (((a << 5) | (a >>> 27)) + f + e + k + x[t]) >>> 0;
        e = d; d = c; c = (b << 30) | (b >>> 2); b = a; a = tmp;
      }
      h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0; h4 = (h4 + e) >>> 0;
    }
    return [h0, h1, h2, h3, h4].map(v => (v >>> 0).toString(16).padStart(8, "0")).join("");
  }

  // ---- the payload a page carries: base64 of raw deflate over [u32 manifest length][manifest JSON][file bytes...]
  async function inflate(b64) {
    const bin = atob(b64);
    const z = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) z[i] = bin.charCodeAt(i);
    const stream = new Blob([z]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }
  function hex(s) {
    const out = new Uint8Array(s.length / 2);
    for (let i = 0; i < out.length; i++) out[i] = parseInt(s.substr(i * 2, 2), 16);
    return out;
  }
  async function unpack(b64) {
    const all = await inflate(b64);
    const mlen = u32(all, 0);
    const m = JSON.parse(new TextDecoder("utf-8").decode(all.subarray(4, 4 + mlen)));
    // the distinct files in order, then each edition and the art naming theirs by index
    let pos = 4 + mlen;
    const blobs = m.blobs.map(len => { const b = all.subarray(pos, pos + len); pos += len; return b; });
    if (pos !== all.length) throw new PatchError("补丁数据不完整");
    const take = list => {
      const out = {};
      for (const [name, i] of list) out[name] = blobs[i];
      return out;
    };
    const p = {cn: {}, art: null, enhancement: null, update: null, pace: null, options: null, editionSites: null,
               addons: null};
    for (const [edition, c] of Object.entries(m.cn)) p.cn[edition] = {files: take(c.files), drop: c.drop, autoexec: hex(c.autoexec)};
    const sites = l => l.map(s => ({at: s.at, orig: hex(s.orig), fixed: hex(s.fixed)}));
    const siteSets = o => Object.fromEntries(Object.entries(o).map(([k, l]) => [k, sites(l)]));
    if (m.art !== null) p.art = {files: take(m.art.files), hashes: m.art.hashes, partition: m.art.partition,
             exe: {nospace: sites(m.art.exe.nospace), slotorder: sites(m.art.exe.slotorder)},
             pc98: m.art.pc98 ? take(m.art.pc98) : null, pc98sha: m.art.pc98sha || null, doors: m.art.doors || null};
    if (m.update) p.update = {files: take(m.update.files), font: blobs[m.update.font]};
    if (m.pace) p.pace = {files: take(m.pace.files), summary: m.pace.summary, font: blobs[m.pace.font],
                          dd: Object.fromEntries(Object.entries(m.pace.dd).map(([k, i]) => [k, blobs[i]])),
                          sites: siteSets(m.pace.sites)};
    if (m.options) p.options = {moon: {...m.options.moon, forms: m.options.moon.forms.map(([a, b]) => [hex(a), hex(b)])},
                                sites: siteSets(m.options.sites), defaults: m.options.defaults};
    if (m.edition) p.editionSites = sites(m.edition);
    // the add-ons: the question in each language the page writes (zh for this page; jp and en for the English
    // add-on page, which tells them apart by lang, the bytes the English translation changes in DDS98.EXE)
    if (m.addons) {
      const t = m.addons.target;
      const texts = Object.fromEntries(Object.entries(t.texts).map(([lang, i]) => [lang, blobs[i]]));
      p.addons = {
        target: {hdr: t.hdr, name: t.name, texts, data: texts.zh || null,
                 sites: t.sites.map(([kind, off, orig, fixed]) => ({kind, off, orig: hex(orig), fixed: hex(fixed)}))},
        pad: {name: m.addons.pad.name, data: blobs[m.addons.pad.data]},
        lang: m.addons.lang ? m.addons.lang.map(([at, jp, en]) => ({at, jp: hex(jp), en: hex(en)})) : null};
    }
    if (m.enhancement) p.enhancement = {...m.enhancement, files: take(m.enhancement.files)};
    return p;
  }

  const OUT_NAME = "Giten_CN.hdi";
  function opened(bytes) {
    const img = openHdi(bytes.slice());
    if (img.hdr < 32 || img.hdr >= bytes.length) throw new PatchError("这不像是一个 .hdi 硬盘镜像");
    return img;
  }
  // The patch on an image's bytes, for the edition ("main" / "rebalance"), with the options ({moon, gap}: the
  // edition's as built for one left out), the Windows art or not, and the add-ons addons ({target, pad}) ticks: a new
  // array (the given one is left alone), as the Python patches write a new file beside the image. The input's name is
  // checked as cnpatch.apply_to checks it.
  async function patch(name, bytes, p, edition, win, say, addons, options) {
    if (!p.cn[edition]) throw new PatchError(`没有「${edition}」这个版本`);
    if (name.toLowerCase() === OUT_NAME.toLowerCase())
      throw new PatchError(`${OUT_NAME} 是汉化版自己的名字，这个文件看上去已经是汉化过的了。请把原始日文版的镜像选进来。`);
    const img = opened(bytes);
    autoboot(img);
    const fs = new Fat(img.disk, img.part);
    translate(fs, p.cn[edition], say);
    if (options) applyOptions(fs, p, options, say);
    if (win) await artwork(fs, p.art, async b => sha1hex(b), say, true);
    if (addons) applyAddons(fs, p.addons, addons, say);
    say("已设置自动启动游戏，无需在 NEC 启动菜单输入按键。");
    return img.raw;
  }

  // ---- an image that already carries the Chinese version (tools/cnretouch.py, step for step): what it is, and
  // this release's negotiation text and/or the other art written into it. Nothing else of it changes.
  const FONT = "CNFONT.DAT";
  function fontRecords(b) {
    if (!same(b.subarray(0, 4), ascii("GTCN"))) throw new PatchError(`${DIR}\\${FONT} 不是汉化补丁的字库文件`);
    const n = u16(b, 4);
    if (b.length !== 6 + 34 * n) throw new PatchError(`${DIR}\\${FONT} 的长度不对`);
    const out = new Map();
    for (let i = 0; i < n; i++) out.set(u16(b, 6 + 34 * i), b.subarray(8 + 34 * i, 40 + 34 * i));
    return out;
  }
  // the image's glyphs with this release's added; a code both have takes this release's pattern
  function mergedFont(old, add) {
    const glyphs = fontRecords(old);
    for (const [code, pat] of fontRecords(add)) glyphs.set(code, pat);
    const codes = [...glyphs.keys()].sort((a, b) => a - b);
    const out = new Uint8Array(6 + 34 * codes.length);
    out.set(ascii("GTCN"), 0);
    put16(out, 4, codes.length);
    codes.forEach((code, i) => { put16(out, 6 + 34 * i, code); out.set(glyphs.get(code), 8 + 34 * i); });
    return out;
  }
  function inspectFs(fs, p) {
    if (fs.find(`${DIR}/DDS98.EXE`) === null) throw new PatchError("镜像里没有 DDS98\\DDS98.EXE，这不是本作的镜像");
    if (fs.find(`${DIR}/${FONT}`) === null) return {kind: "jp"};
    let pc = 0, win = 0, other = 0, now = 0;
    const names = Object.keys(p.art.files).sort();
    for (const name of names) {
      const got = fs.read(`${DIR}/${name}`);
      const h = got === null ? null : sha1hex(got);
      const mine = p.art.pc98sha[name], marks = p.art.hashes[name];
      if (h === marks.now) now++;
      if (h === mine) { if (mine !== marks.now) pc++; }       // a file the art patch leaves as the game's own tells nothing
      else if (h === marks.now || h === marks.was) win++;
      else other++;
    }
    const art = other ? "other" : !win ? "pc98" : !pc ? "win" : "mixed";
    let latest = true;
    for (const [name, blob] of Object.entries(p.update.files)) {
      const got = fs.read(`${DIR}/${name}`);
      if (got === null || !same(got, blob)) { latest = false; break; }
    }
    let addons;
    try { addons = addonState(fs, p.addons); }
    catch (e) { if (e instanceof PatchError) throw new PatchError(`${e.message}，没有生成镜像。`); throw e; }
    return {kind: "cn", edition: editionOf(fs.read(EXE_PATH), p), saves: savesIn(fs), art,
            current: now === names.length, latest, pace: paceState(fs, p.pace), options: optionsOf(fs, p.options), addons};
  }
  function updateTalk(fs, upd, say) {
    let wrote = 0, made = 0;
    for (const name of Object.keys(upd.files).sort()) {
      const got = fs.read(`${DIR}/${name}`);
      if (got === null) { fs.create(DIR, name, upd.files[name]); made++; }
      else if (!same(got, upd.files[name])) { fs.replace(`${DIR}/${name}`, upd.files[name]); wrote++; }
    }
    const old = fs.read(`${DIR}/${FONT}`), font = mergedFont(old, upd.font);
    const added = fontRecords(font).size - fontRecords(old).size;
    if (!same(font, old)) fs.replace(`${DIR}/${FONT}`, font);
    say(`交涉翻译：写入 ${wrote} 个文件` + (made ? `，新增 ${made} 个` : "") + (added ? `；字库补上 ${added} 个字` : "；字库不用补字"));
  }

  // ---- the battle pacing (cnretouch.site_form, summary_form, pace_state, update_pace)
  const EXE_PATH = `${DIR}/DDS98.EXE`;
  function siteForm(exe, sites) {                    // "orig" or "fixed" when every site holds it, else null
    const forms = new Set();
    for (const s of sites) {
      const now = exe.subarray(s.at, s.at + s.orig.length);
      forms.add(same(now, s.orig) ? "orig" : same(now, s.fixed) ? "fixed" : null);
    }
    return forms.size === 1 ? [...forms][0] : null;
  }
  function summaryForm(exe, s) {                     // the EXP line's form the program goes with, or null
    const show = siteForm(exe, s.show), gap = siteForm(exe, s.gap), needs = siteForm(exe, s.needs);
    if (gap === "fixed" && needs === "fixed" && siteForm(exe, s.show.slice(0, 1)) === "fixed") return "gap";
    if (gap === "orig" && (show === "fixed" || show === "orig")) return show === "fixed" ? "shown" : "off";
    return null;
  }
  function paceState(fs, pace) {                     // true this release's, false older, null the program cannot tell
    const exe = fs.read(EXE_PATH);
    const form = summaryForm(exe, pace.sites), hold = siteForm(exe, pace.sites.hold);
    if (form === null || hold === null) return null;
    if (hold !== "fixed") return false;
    const dd = fs.read(`${DIR}/${pace.summary}`);
    if (dd === null || !same(dd, pace.dd[form])) return false;
    for (const [name, blob] of Object.entries(pace.files)) {
      const got = fs.read(`${DIR}/${name}`);
      if (got === null || !same(got, blob)) return false;
    }
    return true;
  }
  const FORM_NAMES = {off: "经验值显示修复关着", shown: "经验值显示修复开着", gap: "等级差经验开着"};
  function updatePace(fs, pace, say) {
    let exe = fs.read(EXE_PATH);
    const form = summaryForm(exe, pace.sites), hold = siteForm(exe, pace.sites.hold);
    if (form === null || hold === null)
      throw new PatchError("镜像里的游戏程序认不出（经验值显示修复、等级差经验或停顿显示的几处既不是原版也不是这一版），" +
                           "战斗消息节奏没法更新，没有生成镜像。");
    const files = {...pace.files, [pace.summary]: pace.dd[form]};
    let wrote = 0, made = 0;
    for (const name of Object.keys(files).sort()) {
      const got = fs.read(`${DIR}/${name}`);
      if (got === null) { fs.create(DIR, name, files[name]); made++; }
      else if (!same(got, files[name])) { fs.replace(`${DIR}/${name}`, files[name]); wrote++; }
    }
    if (hold === "orig") {
      exe = exe.slice();
      for (const s of pace.sites.hold) exe.set(s.fixed, s.at);
      fs.replace(EXE_PATH, exe);
    }
    const old = fs.read(`${DIR}/${FONT}`), font = mergedFont(old, pace.font);
    const added = fontRecords(font).size - fontRecords(old).size;
    if (!same(font, old)) fs.replace(`${DIR}/${FONT}`, font);
    say(`战斗消息节奏：写入 ${wrote} 个文件` + (made ? `，新增 ${made} 个` : "") +
        `（结算的经验值那一行照镜像里的开关：${FORM_NAMES[form]}）` +
        (hold === "orig" ? "；游戏程序改了停顿显示的几处" : "；游戏程序已经是这一版") +
        (added ? `；字库补上 ${added} 个字` : "；字库不用补字"));
  }

  // ---- the player's options (tools/options.py, moonfast.desc_at / mend_table, expgap.mend_exe)
  const OPTIONS = ["moon", "gap"];
  const OPTION_NAMES = {moon: "月相加速", gap: "等级差经验"};
  function optionExe(exe, o) {                       // options.exe_states
    const out = {};
    for (const name of OPTIONS) {
      const form = siteForm(exe, o.sites[name]);
      if (form === null) throw new PatchError(`镜像里的游戏程序认不出${OPTION_NAMES[name]}是开是关（它的几处既不是原版也不是打开的样子）`);
      out[name] = form === "fixed";
    }
    return out;
  }
  function descAt(plain, m) {                        // moonfast.desc_at: [start of コアシールド's description, end of its entry]
    const count = u16(plain, 0), offs = [];
    for (let i = 0; i < count; i++) offs.push(u16(plain, 2 + 2 * i));
    if (!count || offs[0] !== 2 + 2 * count || offs.some((v, i) => i && v < offs[i - 1]) || offs[count - 1] > plain.length)
      throw new PatchError(`${m.table} 不是表格文件`);
    const at = offs[m.entry], end = m.entry + 1 < count ? offs[m.entry + 1] : plain.length;
    const e = plain.subarray(at, end);
    if (e.length <= 4 || e[4] !== m.kind) throw new PatchError(`${m.table} 第 ${m.entry} 条不是第 ${m.kind} 类物品`);
    const nameEnd = e.indexOf(0, m.header);
    if (nameEnd < 0) throw new PatchError(`${m.table} 第 ${m.entry} 条没有名字的结尾`);
    return [at + nameEnd + 1, at + e.length];
  }
  function moonTable(blob, m, on) {                  // moonfast.mend_table: the description in the form `on` asks for
    const [w, plain] = decrypt(blob);
    if (w !== plain.length) throw new PatchError(`${m.table} 不止一块`);
    const [start, end] = descAt(plain, m);
    const hits = m.forms.filter(([a, b]) => start + a.length <= end &&
      (same(plain.subarray(start, start + a.length), a) || same(plain.subarray(start, start + a.length), b)));
    if (hits.length !== 1) throw new PatchError(`${m.table} 第 ${m.entry} 条（核心护盾）的说明既不是原版也不是修复后的内容`);
    const out = plain.slice();
    out.set(on ? hits[0][1] : hits[0][0], start);
    return encrypt(out, w);
  }
  function optionState(fs, o) {                      // options.state
    const have = optionExe(fs.read(EXE_PATH), o);
    const table = fs.read(`${DIR}/${o.moon.table}`);
    if (!same(moonTable(table, o.moon, have.moon), table))
      throw new PatchError(`镜像里${OPTION_NAMES.moon}只打了一半（游戏程序和核心护盾的说明对不上）`);
    return have;
  }
  function optionsOf(fs, o) {                        // cnretouch.options_of
    try { return optionState(fs, o); }
    catch (e) { if (e instanceof PatchError) return null; throw e; }
  }
  function applyOptions(fs, p, want, say) {          // options.apply
    const o = p.options, have = optionState(fs, o), changed = [];
    for (const name of OPTIONS) {
      if (!(name in want) || want[name] === have[name]) continue;
      const exe = fs.read(EXE_PATH).slice();
      for (const s of o.sites[name]) exe.set(want[name] ? s.fixed : s.orig, s.at);
      if (name === "moon") {
        const table = moonTable(fs.read(`${DIR}/${o.moon.table}`), o.moon, want.moon);
        fs.replace(EXE_PATH, exe);
        fs.replace(`${DIR}/${o.moon.table}`, table);
      } else {
        const dd = fs.read(`${DIR}/${p.pace.summary}`);
        if (dd === null || !same(dd, p.pace.dd[have.gap ? "gap" : "shown"]))
          throw new PatchError(`镜像里的战斗消息文件不是这一版的，要先更新战斗消息节奏才能改${OPTION_NAMES.gap}`);
        fs.replace(EXE_PATH, exe);
        fs.replace(`${DIR}/${p.pace.summary}`, p.pace.dd[want.gap ? "gap" : "shown"]);
      }
      have[name] = want[name];
      say(`${OPTION_NAMES[name]}：${want[name] ? "打开" : "关掉"}`);
      changed.push(name);
    }
    return changed;
  }

  // ---- the edition and the saves (cnretouch.edition_of, saves_in)
  const EDITION_NAMES = {main: "原版", rebalance: "再平衡版"};
  function editionOf(exe, p) {
    const form = siteForm(exe, p.editionSites);
    return form === "orig" ? "main" : form === "fixed" ? "rebalance" : null;
  }
  function savesIn(fs) {
    const d = fs.find(DIR);
    return fs.readDir(d.cluster).filter(e => !e.isDir && /^SAVE[0-9A-F]{4}\.DDS$/.test(upper(e.name))).length;
  }
  function restoreDoors(fs, doors) {
    let files = 0, secs = 0;
    const d = fs.find(DIR);
    for (const e of fs.readDir(d.cluster)) {
      const name = upper(e.name);
      if (e.isDir || !name.startsWith("M0") || !name.endsWith(".BIN")) continue;
      if (!doors[name]) throw new PatchError(`${DIR}\\${e.name} 不是本作的地图文件，补丁不认识，没有生成镜像。`);
      const [w, plain] = decrypt(fs.readChain(e.cluster, e.size));
      const list = [...sections(plain)];
      if (list.length !== doors[name].length)
        throw new PatchError(`${DIR}\\${e.name} 的分区和原始日文版的对不上，补丁不认识，没有生成镜像。`);
      const out = plain.slice();
      let n = 0;
      list.forEach(([o], i) => { if (out[o + DOOR_AT] !== doors[name][i]) { out[o + DOOR_AT] = doors[name][i]; n++; } });
      if (n) { fs.replace(`${DIR}/${e.name}`, encrypt(out, w)); files++; secs += n; }
    }
    return [files, secs];
  }
  function restoreArt(fs, art, say) {
    const state = {ready: [], done: [], other: []};
    for (const name of Object.keys(art.files).sort()) {
      const got = fs.read(`${DIR}/${name}`);
      const h = got === null ? null : sha1hex(got);
      if (h === art.pc98sha[name]) state.done.push(name);
      else if (h === art.hashes[name].now || h === art.hashes[name].was) state.ready.push(name);
      else state.other.push(name);
    }
    say(`${Object.keys(art.files).length} 个素材文件：${state.ready.length} 个换回原版，${state.done.length} 个已经是原版，` +
        `${state.other.length} 个不认识`);
    if (state.other.length) {
      say("不认识的：" + state.other.join("、"));
      throw new PatchError("这些文件既不是原版也不是 Windows 素材补丁写的，换回去会把那边的改动抹掉，没有生成镜像。");
    }
    const delta = name => {
      const e = fs.find(`${DIR}/${name}`);
      return Math.ceil(art.pc98[name].length / fs.cs) - (e.cluster ? fs.chain(e.cluster).length : 0);
    };
    let need = 0;
    for (const name of state.ready) need += delta(name);
    const free = fs.freeClusters().length;
    if (need > free) throw new PatchError(`镜像里的空间不够：还要 ${need * fs.cs} 字节，只剩 ${free * fs.cs} 字节。`);
    const keyed = state.ready.map(name => [delta(name), name]);
    keyed.sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
    for (const [, name] of keyed) fs.replace(`${DIR}/${name}`, art.pc98[name]);
    const [nMaps, nSec] = restoreDoors(fs, art.doors);
    say(nSec ? `地图门号：${nMaps} 个文件、${nSec} 个分区改回原版` : "地图门号：已经是原版");
  }
  // ---- the add-ons (tools/addons.py: tools/targetprompt.py and tools/gamepad.py, step for step): each goes into an
  // image or comes out of it, in ADDONS order, and nothing else of the image changes
  const ADDONS = ["target", "pad"];
  const ADDON_NAMES = {target: "选择对象时暂停", pad: "手柄操作"};
  function ovOffset(exe, number) {                   // targetprompt.ov_offset: overlay `number`'s image in the file
    const cblp = u16(exe, 2), cp = u16(exe, 4);
    let pos = (((cp - 1) * 512 + (cblp || 512)) + 511) & ~511;
    while (pos + 0x20 < exe.length) {
      if (exe[pos] === 0x4D && exe[pos + 1] === 0x5A) {
        const oCblp = u16(exe, pos + 2), oCp = u16(exe, pos + 4), oPar = u16(exe, pos + 8);
        if (u16(exe, pos + 0x1A) === number) return pos + oPar * 16;
        pos = (pos + (oCp - 1) * 512 + (oCblp || 512) + 511) & ~511;
      } else pos += 512;
    }
    throw new PatchError(`DDS98.EXE 里找不到覆盖段 ${number}`);
  }
  function targetSites(exe, t) {
    const ov = t.sites.some(s => s.kind === "ov16") ? ovOffset(exe, 16) : 0;
    return t.sites.map(s => ({at: (s.kind === "ov16" ? ov : t.hdr) + s.off, orig: s.orig, fixed: s.fixed}));
  }
  function targetForm(exe, t) {                      // targetprompt.state
    const forms = new Set();
    for (const s of targetSites(exe, t)) {
      const now = exe.subarray(s.at, s.at + s.orig.length);
      if (same(now, s.orig)) forms.add("orig");
      else if (same(now, s.fixed)) forms.add("fixed");
      else throw new PatchError(`DDS98.EXE 第 0x${s.at.toString(16)} 字节起既不是原版也不是本项改动后的内容`);
    }
    if (forms.size !== 1) throw new PatchError("DDS98.EXE 里本项的各处改动不一致（有的打了，有的没打）");
    return [...forms][0];
  }
  function addonState(fs, a) {                       // addons.state
    const exe = fs.read(`${DIR}/DDS98.EXE`);
    if (exe === null) throw new PatchError("镜像里没有 DDS98\\DDS98.EXE，这不是本作的镜像");
    const target = targetForm(exe, a.target) === "fixed";
    if (target !== (fs.find(`${DIR}/${a.target.name}`) !== null))
      throw new PatchError(`镜像里${ADDON_NAMES.target}只打了一半（DDS98.EXE 和 ${a.target.name} 对不上）`);
    const com = fs.read(`${DIR}/${a.pad.name}`);
    if (com !== null && !same(com, a.pad.data))
      throw new PatchError(`镜像里的 ${DIR}\\${a.pad.name} 不是本补丁的${ADDON_NAMES.pad}程序，补丁不认识，不动它`);
    return {target, pad: com !== null};
  }
  function applyAddons(fs, a, want, say) {           // addons.apply
    const have = addonState(fs, a), changed = [];
    for (const name of ADDONS) {
      if (!(name in want) || want[name] === have[name]) continue;
      if (name === "target") {
        const exe = fs.read(`${DIR}/DDS98.EXE`).slice();
        for (const s of targetSites(exe, a.target)) exe.set(want.target ? s.fixed : s.orig, s.at);
        fs.replace(`${DIR}/DDS98.EXE`, exe);
        if (want.target) fs.create(DIR, a.target.name, a.target.data);
        else fs.remove(`${DIR}/${a.target.name}`);
      } else if (want.pad) fs.create(DIR, a.pad.name, a.pad.data);
      else fs.remove(`${DIR}/${a.pad.name}`);
      say(`${ADDON_NAMES[name]}：${want[name] ? "加上" : "去掉"}`);
      changed.push(name);
    }
    return changed;
  }

  // What a chosen image is: {kind: "jp"} or {kind: "cn", edition: "main" | "rebalance" | null, saves, art: "pc98" |
  // "win" | "mixed" | "other", current, latest, pace: true | false | null, options: {moon, gap} | null, addons: {target,
  // pad}}.
  function inspect(bytes, p) {
    const img = opened(bytes);
    return inspectFs(new Fat(img.disk, img.part), p);
  }
  // A Chinese image with the art "pc98" or "win", when update is true this release's negotiation text, and what more
  // ({pace, options, edition}) and addons ({target, pad}) ask for: the battle pacing, the options ({moon, gap}), the
  // add-ons (true in, false out; none to keep them), or the other edition (only without saves): a new array, the given
  // one left alone (cnretouch.retouch_fs). With nothing to change it refuses.
  async function retouch(bytes, p, art, update, say, addons, more) {
    const {pace = false, options = null, edition = null} = more || {};
    const img = opened(bytes);
    const fs = new Fat(img.disk, img.part);
    const info = inspectFs(fs, p);
    if (info.kind !== "cn")
      throw new PatchError("这不是打过汉化补丁的镜像（里面没有中文字库）。原始日文版镜像请选版本和美术，打整个补丁。");
    if (edition !== null && edition !== info.edition) {
      await convert(fs, p, info, edition, art, options, addons, say);
      return img.raw;
    }
    const doUpdate = update && !info.latest, doPace = pace && info.pace !== true;
    const doOptions = options !== null && (info.options === null || Object.keys(options).some(n => options[n] !== info.options[n]));
    const doWin = art === "win" && !info.current, doPc = art === "pc98" && info.art !== "pc98";
    const doAddons = !!addons && Object.keys(addons).some(n => addons[n] !== info.addons[n]);
    if (!doUpdate && !doPace && !doOptions && !doWin && !doPc && !doAddons) throw new PatchError("这个镜像已经是这样了，没有要改的。");
    if (doUpdate) updateTalk(fs, p.update, say);
    if (doPace) updatePace(fs, p.pace, say);
    if (doOptions) applyOptions(fs, p, options, say);
    if (doWin) await artwork(fs, p.art, async b => sha1hex(b), say, true);
    if (doPc) restoreArt(fs, p.art, say);
    if (doAddons) applyAddons(fs, p.addons, addons, say);
    return img.raw;
  }
  // cnretouch.convert: the other edition's whole patch onto an image without saves, then its options as asked or else
  // that edition's defaults, and the art and the add-ons as asked or else as they were
  async function convert(fs, p, info, edition, art, options, addons, say) {
    if (info.edition === null)
      throw new PatchError("认不出镜像是原版还是再平衡版（游戏程序里再平衡的几处既不是原版的也不是再平衡版的），没法转换版本");
    if (info.saves)
      throw new PatchError(`镜像里有 ${info.saves} 个存档：两个版本的成长和加点规则不一样，存档不通用，有存档的镜像不能转换版本（没有存档的才可以）`);
    const wantOptions = {...p.options.defaults[edition], ...(options || {})};
    const wantAddons = {...info.addons, ...(addons || {})};
    if (info.addons.target) applyAddons(fs, p.addons, {target: false}, () => {});
    say(`版本：${EDITION_NAMES[info.edition]} → ${EDITION_NAMES[edition]}，整个补丁重新写入`);
    translate(fs, p.cn[edition], say);
    applyOptions(fs, p, wantOptions, say);
    const after = inspectFs(fs, p);
    if (art === "win" && !after.current) await artwork(fs, p.art, async b => sha1hex(b), say, true);
    if (art === "pc98" && after.art !== "pc98") restoreArt(fs, p.art, say);
    applyAddons(fs, p.addons, wantAddons, say);
  }

  // Language-preserving enhancements use the same file writer and artwork engine. Their manifest
  // identifies every required file before any writing, and leaves the input's DOS boot setup intact.
  function artworkPartition(img, layout, say) {
    if (!layout) return;
    // This particular reference disk has fourteen unpartitioned cylinders after its DOS volume.
    // Reclaim those cylinders as an explicit part of installing its artwork, without resizing the
    // image, relocating files, changing FAT width, or guessing a layout for other disks.
    const header = hex(layout.header), partition = hex(layout.partition), bpb = hex(layout.bpb);
    if (!same(img.raw.subarray(0, header.length), header) || img.part !== layout.part) return;
    const pt = img.disk.subarray(img.sect, img.sect + 32), boot = img.disk.subarray(img.part, img.part + bpb.length);
    if (!same(pt, partition) || !same(boot, bpb)) return;
    if (img.raw.length !== img.hdr + u32(img.raw, 12)) throw new PatchError("The reference HDI is truncated.");
    if (img.disk.subarray(img.sect + 32, img.sect * 2).some(v => v !== 0))
      throw new PatchError("Another partition occupies the reference disk's partition table. No output was created.");
    const fs = new Fat(img.disk, img.part);
    const end = img.part + layout.total * fs.bps;
    const clusters = Math.floor((layout.total - fs.reserved - fs.fats * fs.spf - fs.rootSectors) / fs.spc);
    if (end !== img.disk.length || fs.bits !== 12 || clusters >= 4085 ||
        Math.ceil((clusters + 2) * 1.5) > fs.spf * fs.bps)
      throw new PatchError("Unsupported reference FAT geometry. No output was created.");
    if (img.disk.subarray(img.part + fs.total * fs.bps, end).some(v => v !== 0 && v !== 0xE5))
      throw new PatchError("The reference disk's unpartitioned tail contains data. No output was created.");
    // Reserved FAT entries beyond the old volume must also be unused.
    for (let c = fs.maxCluster() + 1; c <= clusters + 1; c++)
      if (fs.getFat(c) !== 0) throw new PatchError("The unused FAT tail is not empty. No output was created.");
    put16(img.disk, img.sect + 14, layout.lastCylinder);
    put16(img.disk, img.part + 19, layout.total);
    say("Extended the reference DOS partition into its unused 693 KiB tail. Image size and existing files are unchanged.");
  }

  async function enhance(bytes, p, kind, say, addons) {
    if (kind === "addons") return addonEnhance(bytes, p, say, addons);   // tools/enhancement_runtime.js
    const img = opened(bytes);
    if (kind === "art") {
      if (!p.art) throw new PatchError("This page has no artwork payload.");
      artworkPartition(img, p.art.partition, say);
      const fs = new Fat(img.disk, img.part);
      await artwork(fs, p.art, async b => sha1hex(b), say, false);
      return img.raw;
    }
    const fs = new Fat(img.disk, img.part);
    const changes = p.enhancement;
    if (!changes || changes.kind !== kind) throw new PatchError("This page has the wrong patch payload.");
    // the target prompt add-on's file (tools/targetprompt.py): with it in, DDS98.EXE is no state this patch knows
    if (changes.addon && fs.find(`${DIR}/${changes.addon}`) !== null)
      throw new PatchError("This image has the target prompt add-on, which changes DDS98.EXE. Untick it on " +
                           "Apply Add-ons.html, apply this patch, then tick it again. No output was created.");
    const english = changes.english;
    const executable = fs.read(`${DIR}/DDS98.EXE`);
    if (english && executable && Object.values(english.exe).some(hashes => hashes.includes(sha1hex(executable)))) {
      structuralEnhance(fs, english, kind, say);
      return img.raw;
    }
    const wrong = [];
    for (const [name, accepted] of Object.entries(changes.requires)) {
      const current = fs.read(`${DIR}/${name}`);
      const hash = current === null ? null : sha1hex(current);
      if (!accepted.includes(hash)) wrong.push(name);
    }
    if (wrong.length) throw new PatchError(
      (kind === "rebalance" ? "Apply the Fixes patch first. " : "A required game file is missing or modified. ") +
      "Unsupported files: " + wrong.join(", ") + ". No output was created.");
    say("Verified " + Object.keys(changes.requires).length + " game files.");
    translate(fs, {files: changes.files, drop: [], autoexec: null}, say);
    say("Game text remains Japanese. Saves and the DOS boot configuration are preserved.");
    return img.raw;
  }

  root.WebPatch = {PatchError, openHdi, Fat, translate, artwork, sha1hex, unpack, patch, inspect, retouch, enhance,
                   addonState, applyAddons, ADDONS, OPTIONS, OUT_NAME};
  if (typeof module !== "undefined") module.exports = root.WebPatch;
})(typeof globalThis !== "undefined" ? globalThis : this);
