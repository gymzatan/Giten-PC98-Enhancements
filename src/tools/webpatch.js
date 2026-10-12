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
// The page runs translate for the edition the player picked and, when they picked the Windows art, artwork on the
// result: one patch takes the Japanese image to the chosen Giten_CN.hdi. Errors are PatchError with the Python
// patches' messages.
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
    const p = {cn: {}, art: null, enhancement: null};
    for (const [edition, c] of Object.entries(m.cn)) p.cn[edition] = {files: take(c.files), drop: c.drop, autoexec: hex(c.autoexec)};
    const sites = l => l.map(s => ({at: s.at, orig: hex(s.orig), fixed: hex(s.fixed)}));
    if (m.art !== null) p.art = {files: take(m.art.files), hashes: m.art.hashes, partition: m.art.partition,
             exe: {nospace: sites(m.art.exe.nospace), slotorder: sites(m.art.exe.slotorder)}};
    if (m.enhancement) p.enhancement = {...m.enhancement, files: take(m.enhancement.files)};
    return p;
  }

  const OUT_NAME = "Giten_CN.hdi";
  function opened(bytes) {
    const img = openHdi(bytes.slice());
    if (img.hdr < 32 || img.hdr >= bytes.length) throw new PatchError("这不像是一个 .hdi 硬盘镜像");
    return img;
  }
  // The patch on an image's bytes, for the edition ("main" / "rebalance") and with the Windows art or not: a new
  // array (the given one is left alone), as the Python patches write a new file beside the image. The input's name
  // is checked as cnpatch.apply_to checks it.
  async function patch(name, bytes, p, edition, win, say) {
    if (!p.cn[edition]) throw new PatchError(`没有「${edition}」这个版本`);
    if (name.toLowerCase() === OUT_NAME.toLowerCase())
      throw new PatchError(`${OUT_NAME} 是汉化版自己的名字，这个文件看上去已经是汉化过的了。请把原始日文版的镜像选进来（要升级旧的汉化版，先把它改个名）。`);
    const img = opened(bytes);
    autoboot(img);
    const fs = new Fat(img.disk, img.part);
    translate(fs, p.cn[edition], say);
    if (win) await artwork(fs, p.art, async b => sha1hex(b), say, true);
    say("已设置自动启动游戏，无需在 NEC 启动菜单输入按键。");
    return img.raw;
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

  async function enhance(bytes, p, kind, say) {
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

  root.WebPatch = {PatchError, openHdi, Fat, translate, artwork, sha1hex, unpack, patch, enhance, OUT_NAME};
  if (typeof module !== "undefined") module.exports = root.WebPatch;
})(typeof globalThis !== "undefined" ? globalThis : this);
