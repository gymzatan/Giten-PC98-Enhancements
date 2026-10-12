# Contributing to Giten Megami Tensei Redux

The source code and authored documentation are MIT licensed. Keep the copyright notice when sharing changes. Game images, original/remake artwork, fonts, music and the separately distributed English translation retain their owners' rights. They are inputs, not part of the MIT grant.

Start with [the modder documentation](docs/modding/README.md) and [the build instructions](docs/modding/BUILD.md). Work on copies of your own game files. Please describe the file, record or executable site you changed, the input it was tested against, the behavior before and after, and the checks you ran.

Use the existing parsers and patch definitions. `buildcore.py` owns the repair sequence; `nativebuild.py` selects the language-preserving inputs; `enhancement_plan.py` describes their outputs for the browser. Do not put a second implementation of a repair in the web installer. Numeric edits use `records.py` and `balance.py`, graphics use `fcimage.py` / `fcencode.py` / `fcfit.py`, and script relocation uses the VM token identities from `ddsvm.py`.

Unknown fields stay unknown until their meaning is supported by program analysis or a reproducible input/output comparison. A free-looking byte range is not sufficient evidence of unused executable space. Record the address kind and original bytes when adding a hook. Refuse an unsupported or ambiguous input rather than overwriting unrelated changes.

Use English for public explanations. Original Japanese labels and stable record IDs are useful lookup anchors. Keep player-facing feature descriptions separate from implementation details. Update the relevant current documentation when an accepted change alters it.

Do not submit complete HDIs, extracted game files, converted artwork, reference editor databases or personal paths. The ignored directories in `.gitignore` are locally generated. Tests that require game data should explain that requirement and accept explicit inputs.
