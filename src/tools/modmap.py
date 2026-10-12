"""Export address and event-edit ledgers directly from the patch definitions."""
import csv
import json
from pathlib import Path

import bagexpand, checkfix, exekeys, expgap, expshow, moonfast
import rebalance, skillfix, statfix, storyfix
import ctxfree, exefix, nospace, slotorder, vmswap


def executable_sites():
    for module in (ctxfree, nospace):
        yield module.__name__, module.AT, module.ORIG, module.FIXED
    for site in exefix.SITES:
        yield "exefix", site["at"], bytes.fromhex(site["orig"]), bytes.fromhex(site["fixed"])
    for offset, before, builder in slotorder.SITES:
        yield "slotorder", slotorder.at(offset), before, builder()
    yield "vmswap", vmswap.at(vmswap.START), vmswap.original(), vmswap.fixed()
    for module in (statfix, exekeys, bagexpand):
        sites = module.SITES if module is bagexpand else module.sites()
        for label, offset, before, after in sites:
            yield module.__name__, offset, before, after
    for module in (checkfix, expshow, expgap, moonfast, rebalance, skillfix, storyfix):
        for site in module.EXE_SITES:
            offset, before, after = site[:3]
            yield module.__name__, offset, before, after


def main():
    out = Path(__file__).resolve().parents[2] / "docs" / "modding"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "Executable-Sites.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(("Module", "Executable file offset (hex)", "Length", "Expected bytes", "Patched bytes"))
        for name, at, before, after in executable_sites():
            writer.writerow((name, f"0x{at:X}", len(before), before.hex(), after.hex()))
    events = []
    for module in (storyfix, checkfix):
        for edit in module.FIXES:
            row = dict(module=module.__name__, file=edit.stem, chunk=edit.chunk, record=f"0x{edit.rid:02X}",
                       kind=type(edit).__name__)
            if hasattr(edit, "code"):
                row["opcode"] = f"0x{edit.code:03X}"
            for key in ("tail", "fixed_tail", "fixed_code"):
                if hasattr(edit, key):
                    value = getattr(edit, key)
                    row[key] = value.hex() if isinstance(value, bytes) else value
            events.append(row)
    (out / "Event-Edits.json").write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    (out / "Rebalance-Labels.json").write_text(json.dumps(rebalance.LABELS, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(events)} event definitions and executable patch preconditions.")


if __name__ == "__main__":
    main()
