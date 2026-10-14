// webpatch_run.js PAGE.html IMAGE NAME OUT EDITION ART [EXTRA] - the web patch (tools/mkwebpatch.py) run under Node the way
// the page runs it: the page's own patch core (its first inline script) and its own payload (the text/plain script),
// on the bytes of IMAGE given the file name NAME (the page sees the name the browser gives it), with the player's
// two choices: EDITION main | rebalance, ART pc98 | win. Writes what the page would save to OUT and prints one JSON
// line: {"ok": true, "lines": [...]} or {"ok": false, "refused": true|false, "message": ...} - refused for a
// PatchError, the page's 「没能完成」. tools/webpatch_test.py drives it.
"use strict";
const fs = require("fs");
const vm = require("vm");

// EDITION "inspect" prints what the page reads off the image ({"ok": true, "inspect": {...}}, OUT unused); EDITION "cn"
// is the path for a Chinese image: WebPatch.retouch with ART, the negotiation update when an argument "update" is
// given, the pacing update for "pace", and the other edition for "edition=main" or "edition=rebalance". An argument
// "addons=target:1,pad:0" ticks the add-ons (both paths; without it the Japanese path adds none and the Chinese one
// keeps the image's), "options=moon:1,gap:0" the options (both paths; without it the Japanese path keeps the
// edition's as built and the Chinese one the image's). With ART "enhancement" PAGE is an English page
// (tools/mkenhancements.py) and EDITION its kind (fixes, rebalance, art, addons) or "inspect" (the add-on page's
// WebPatch.addonInspect).
const [page, image, name, out, edition, art, ...rest] = process.argv.slice(2);
const extra = rest.includes("update") ? "update" : undefined;
function ticks(key) {
  const arg = rest.find(a => a.startsWith(key + "="));
  return arg ? Object.fromEntries(arg.slice(key.length + 1).split(",").map(p => { const [k, v] = p.split(":"); return [k, v === "1"]; })) : undefined;
}
const addons = ticks("addons"), options = ticks("options");
const convertTo = rest.find(a => a.startsWith("edition="));
const more = {pace: rest.includes("pace"), options: options || null, edition: convertTo ? convertTo.slice(8) : null};
const enhancement = art === "enhancement";
if (enhancement ? !["fixes", "rebalance", "art", "addons", "inspect"].includes(edition) :
    edition === "inspect" ? false :
    edition === "cn" ? !["pc98", "win"].includes(art) :
    (!["main", "rebalance"].includes(edition) || !["pc98", "win"].includes(art)))
  throw new Error(`edition must be main or rebalance, art pc98 or win: ${edition} ${art}`);
const html = fs.readFileSync(page, "utf8");
const scripts = [...html.matchAll(/<script(?: type="([^"]+)")?(?: id="([^"]+)")?>([\s\S]*?)<\/script>/g)];
const core = scripts.find(m => !m[1] && m[3].includes("root.WebPatch"));
const data = scripts.find(m => m[2] === "payload");
if (!core || !data) throw new Error(`${page}: no patch core or payload`);
const ctx = vm.createContext({TextDecoder, TextEncoder, Blob, Response, DecompressionStream, atob, console});
vm.runInContext(core[3], ctx);
const WP = ctx.WebPatch;
const lines = [];
(async () => {
  try {
    const p = await WP.unpack(data[3].trim());
    const bytes = new Uint8Array(fs.readFileSync(image));
    if (edition === "inspect") {
      console.log(JSON.stringify({ok: true, inspect: enhancement ? WP.addonInspect(bytes, p) : WP.inspect(bytes, p), lines}));
      return;
    }
    const say = t => lines.push(t);
    const made = enhancement ? await WP.enhance(bytes, p, edition, say, addons) :
      edition === "cn" ? await WP.retouch(bytes, p, art, extra === "update", say, addons, more) :
      await WP.patch(name, bytes, p, edition, art === "win", say, addons, options);
    fs.writeFileSync(out, made);
    console.log(JSON.stringify({ok: true, lines}));
  } catch (e) {
    console.log(JSON.stringify({ok: false, refused: e instanceof WP.PatchError, message: String(e && e.message || e),
                                lines}));
  }
})();
