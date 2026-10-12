// webpatch_run.js PAGE.html IMAGE NAME OUT EDITION ART - the web patch (tools/mkwebpatch.py) run under Node the way
// the page runs it: the page's own patch core (its first inline script) and its own payload (the text/plain script),
// on the bytes of IMAGE given the file name NAME (the page sees the name the browser gives it), with the player's
// two choices: EDITION main | rebalance, ART pc98 | win. Writes what the page would save to OUT and prints one JSON
// line: {"ok": true, "lines": [...]} or {"ok": false, "refused": true|false, "message": ...} - refused for a
// PatchError, the page's 「没能完成」. tools/webpatch_test.py drives it.
"use strict";
const fs = require("fs");
const vm = require("vm");

const [page, image, name, out, edition, art] = process.argv.slice(2);
const enhancement = art === "enhancement";
if (enhancement ? !["fixes", "rebalance", "art"].includes(edition) :
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
    const made = enhancement ? await WP.enhance(bytes, p, edition, t => lines.push(t)) :
      await WP.patch(name, bytes, p, edition, art === "win", t => lines.push(t));
    fs.writeFileSync(out, made);
    console.log(JSON.stringify({ok: true, lines}));
  } catch (e) {
    console.log(JSON.stringify({ok: false, refused: e instanceof WP.PatchError, message: String(e && e.message || e),
                                lines}));
  }
})();
