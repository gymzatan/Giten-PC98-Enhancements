"""Convenience entry points that call the existing Redux engines.

Run from src/. See ../docs/modding/BUILD.md for the full build.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Extract an owned image into the existing files layout")
    extract.add_argument("image", type=Path)
    extract.add_argument("output", type=Path)
    build = commands.add_parser("build-files", help="Build a language-preserving native file payload")
    build.add_argument("--src", required=True)
    build.add_argument("--holds", required=True)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--english", action="store_true")
    build.add_argument("--rebalance", action="store_true")
    scripts = commands.add_parser("inspect-script", help="Show existing VM token identities and branches")
    scripts.add_argument("file", type=Path)
    scripts.add_argument("--chunk", type=int, default=0)
    scripts.add_argument("--record", type=lambda value: int(value, 0), required=True)
    args = parser.parse_args()
    if args.command == "extract":
        subprocess.run([sys.executable, str(ROOT / "tools/extract.py"), str(args.image), str(args.output)], check=True)
    elif args.command == "build-files":
        import nativebuild
        built = nativebuild.build(src=args.src, english=args.english, rebalance_on=args.rebalance, hold_path=args.holds)
        args.output.mkdir(parents=True, exist_ok=True)
        for name, blob in {**built["files"], **built["added"]}.items():
            (args.output / name).write_bytes(blob)
        print(f"Built {len(built['files']) + len(built['added'])} files in {args.output}")
    else:
        import ddsfile, ddsvm
        records = [r for r in ddsfile.parse(args.file.read_bytes())[args.chunk] if r.rid == args.record]
        if len(records) != 1:
            raise ValueError("The requested record is absent or ambiguous")
        record = records[0]
        print("condition:", record.cond)
        for token in ddsvm.tokenize(record.payload):
            print(f"{token.start:04X}-{token.end:04X} {token.kind} {token.code} rel={token.rel}",
                  record.payload[token.start:token.end].hex(" "))


if __name__ == "__main__":
    main()
