"""Common browser payload format and checked Windows-artwork manifest."""
import base64, hashlib, json, os, struct, zlib
import nospace, slotorder, winpatch
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
ART_PAYLOAD = os.path.join(WORK, 'build', 'winpatch.zip')
CORE = os.path.join(HERE, 'webpatch.js')
CSS = '\n:root{\n  --ground:#f3f1ec; --surface:#fffdf8; --ink:#1f1d1a; --muted:#6b665d; --line:#ddd6c9;\n  --accent:#7a2e1e; --accent-ink:#fffaf2; --ok:#2f6b3a; --bad:#a3271b; --drop:#efe9dd;\n  --sans:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC",system-ui,sans-serif;\n  --mono:ui-monospace,"SF Mono",Consolas,"Noto Sans Mono CJK SC",monospace;\n}\n@media (prefers-color-scheme: dark){\n  :root:not([data-theme="light"]){\n    --ground:#171513; --surface:#211e1b; --ink:#ece6dc; --muted:#a59d90; --line:#3a352f;\n    --accent:#d9805f; --accent-ink:#1b1210; --ok:#7fbf86; --bad:#ef8a7c; --drop:#2a2622;\n  }\n}\n*{box-sizing:border-box}\nhtml{background:var(--ground)}\nbody{margin:0;background:var(--ground);color:var(--ink);font:16px/1.7 var(--sans);padding:32px 16px 48px}\nmain{max-width:680px;margin:0 auto;display:flex;flex-direction:column;gap:20px}\nheader h1{margin:0;font-size:24px;line-height:1.35;letter-spacing:.02em;text-wrap:balance}\nheader .ver{display:inline-block;margin-top:8px;padding:2px 10px;border:1px solid var(--accent);color:var(--accent);\n  border-radius:999px;font-size:14px;letter-spacing:.06em}\n.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:20px}\n.card h2{margin:0 0 8px;font-size:17px}\n.card p{margin:0 0 8px}\n.card p:last-child{margin-bottom:0}\n.drop{display:flex;flex-direction:column;align-items:center;gap:10px;padding:28px 16px;border:2px dashed var(--line);\n  border-radius:10px;background:var(--drop);text-align:center}\n.drop.over{border-color:var(--accent)}\n.btn{display:inline-block;border:0;border-radius:8px;padding:10px 22px;font:inherit;font-weight:600;cursor:pointer;\n  background:var(--accent);color:var(--accent-ink);text-decoration:none}\n.btn:focus-visible,.drop input:focus-visible+label{outline:3px solid var(--accent);outline-offset:3px}\n.drop input{position:absolute;width:1px;height:1px;opacity:0}\n.sub{color:var(--muted);font-size:14px}\n#log{margin:0;padding:0;list-style:none;font-size:14px;color:var(--muted)}\n#log li{padding:2px 0}\n#log li.bad{color:var(--bad)}\n#done{display:none}\n#done.on{display:block}\n#done .btn{margin:6px 0 10px}\n.okline{color:var(--ok);font-weight:600}\ndetails summary{cursor:pointer;font-weight:600}\ndetails p{font-size:14px;color:var(--ink)}\ndetails h3{margin:14px 0 4px;font-size:15px}\nfieldset{border:0;margin:0 0 14px;padding:0;min-width:0}\nlegend{font-weight:600;margin-bottom:6px;padding:0}\n.opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}\n.opt{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--line);border-radius:8px;padding:10px 12px;\n  cursor:pointer;background:var(--surface)}\n.opt input{margin:4px 0 0;accent-color:var(--accent)}\n.opt span{display:flex;flex-direction:column}\n.opt small{color:var(--muted);font-size:13px}\n.opt:has(input:checked){border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}\n.opt:has(input:focus-visible){outline:3px solid var(--accent);outline-offset:2px}\n.drop.off{opacity:.45}\n.drop.off .btn{cursor:not-allowed}\n@media (prefers-reduced-motion:no-preference){.drop{transition:border-color .15s,opacity .15s}}\n'

def art_part():
    """winpatch.payload and the DDS98.EXE sites winpatch.exe_state / apply_to check and write."""
    files, marks = winpatch.payload(ART_PAYLOAD)
    exe = {"nospace": [{"at": nospace.AT, "orig": nospace.ORIG.hex(), "fixed": nospace.FIXED.hex()}],
           "slotorder": [{"at": slotorder.at(off), "orig": orig.hex(), "fixed": fixed().hex()}
                         for off, orig, fixed in slotorder.SITES]}
    for sites in exe.values():
        for s in sites:
            if len(s["orig"]) != len(s["fixed"]):
                raise SystemExit(f"DDS98.EXE +{s['at']:#x}: the fixed form is not as long as the original")
    return files, marks, exe


def packed(manifest, blobs):
    """base64 of raw deflate over [u32 manifest length][manifest JSON][the blobs in manifest order]."""
    m = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    raw = struct.pack("<I", len(m)) + m + b"".join(blobs)
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(c.compress(raw) + c.flush()).decode("ascii"), len(raw)

