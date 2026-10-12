"""Package the existing editors after locally preparing their reference data.

python tools/build_editor.py numeric --edition main
python tools/build_editor.py numeric --edition rebalance
python tools/build_editor.py artwork
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("editor", choices=("numeric", "artwork"))
    parser.add_argument("--edition", choices=("main", "rebalance"), default="main")
    args = parser.parse_args()
    name = "Giten-Artwork-Editor" if args.editor == "artwork" else "Giten-Numeric-Editor-" + args.edition
    entry = "fcedit.py" if args.editor == "artwork" else "demoned.py"
    cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole", "--name", name,
           "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / name),
           "--specpath", str(ROOT / "build"), "--paths", str(ROOT / "tools"),
           "--paths", str(ROOT / "run")]
    if args.editor == "numeric":
        for filename in ("gamebase.json", "moon.json", "p2enums.json"):
            source = ROOT / "tools" / filename
            if not source.is_file():
                raise ValueError("Prepare editor data first: " + filename)
            cmd.extend(("--add-data", str(source) + ";."))
        edition = ROOT / "build" / "edition.json"
        edition.parent.mkdir(parents=True, exist_ok=True)
        edition.write_text(json.dumps({"edition": args.edition}), encoding="utf-8")
        cmd.extend(("--add-data", str(edition) + ";."))
    cmd.append(str(ROOT / "tools" / entry))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
