#!/usr/bin/env python3
"""The add-ons the patch page offers (the user, 2026-10-13: 「作为一个附加补丁」, a box to tick on the Chinese patch
page, and an English patch of its own): each can go into an image or come out of it again, and nothing else of the
image changes.

  target  选择对象时暂停 (tools/targetprompt.py): DDS98.EXE's six sites and DDS98\\MS00D9.BIN, the question
  pad     手柄操作 (tools/gamepad.py): DDS98\\DDS98.COM, the launcher with the gamepad control

What an add-on needs from the build is its files: MS00D9.BIN in the build's character map (or the Japanese game's
or the English translation's encoding), DDS98.COM. The order is fixed (ORDER), so the Python reference
(tools/cnpatch.py, tools/cnretouch.py) and the web patch (tools/webpatch.js) write an image's clusters alike.

    addons.py IMAGE                     which add-ons an image has
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamepad  # noqa: E402
import targetprompt  # noqa: E402

ORDER = ("target", "pad")
LABELS = {"target": targetprompt.NAME, "pad": gamepad.NAME}
FILES = {"target": targetprompt.MSG_FILE, "pad": gamepad.COM}


class AddonError(ValueError):
    pass


def files(charmap=None, english=False):
    """{add-on: its file's bytes}: the question for the build's charmap (None: the game's own encoding, the English
    with english) and the launcher."""
    com, _labels = gamepad.build()
    return {"target": targetprompt.message_file(charmap, english), "pad": com}


def state(fs, payload):
    """{add-on: whether the image has it}; an add-on half in, or a DDS98.COM of someone else's, is AddonError."""
    try:
        return {"target": targetprompt.installed(fs), "pad": gamepad.installed(fs, payload["pad"])}
    except (targetprompt.TargetPromptError, gamepad.GamepadError) as e:
        raise AddonError(str(e)) from None


def shortfall(fs, payload, want):
    """How many clusters the image lacks for apply(fs, payload, want): the changes taken in ORDER, a removal freeing
    its file's clusters before the next add-on, an addition taking its file's (DDS98.EXE is rewritten at its own
    size); 0 when it fits."""
    have = state(fs, payload)
    cs = fs.bpb.cluster_size
    free = low = len(fs.free_clusters())
    for name in ORDER:
        if name not in want or want[name] == have[name]:
            continue
        if want[name]:
            free -= -(-len(payload[name]) // cs)
        else:
            free += -(-fs.find(f"{targetprompt.DIR}/{FILES[name]}")["size"] // cs)
        low = min(low, free)
    return max(0, -low)


def apply(fs, payload, want, say=print):
    """Each add-on into the image or out of it as want ({add-on: bool}) says; one the image already has as wanted is
    left alone. -> the names of the add-ons changed."""
    have = state(fs, payload)
    changed = []
    for name in ORDER:
        if name not in want or want[name] == have[name]:
            continue
        try:
            if name == "target":
                (targetprompt.install(fs, payload["target"]) if want[name] else targetprompt.remove(fs))
            else:
                (gamepad.install(fs, payload["pad"]) if want[name] else gamepad.remove(fs, payload["pad"]))
        except (targetprompt.TargetPromptError, gamepad.GamepadError) as e:
            raise AddonError(str(e)) from None
        say(f"  {LABELS[name]}：{'加上' if want[name] else '去掉'}")
        changed.append(name)
    return changed


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    from fat12 import open_hdi
    from fat12w import Fat12W
    _raw, _hdr, disk, part = open_hdi(argv[0])
    print({LABELS[k]: v for k, v in state(Fat12W(disk, part), files()).items()})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
