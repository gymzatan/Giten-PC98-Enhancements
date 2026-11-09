"""The translations the English enhancement pages (tools/mkenhancements.py) take besides the Japanese game.

Each is the set of game files someone else's patch makes from the Japanese game. The build reads one reference
image of each, checked by its SHA-256, puts right what the translation's patch broke (tools/english_enhancements.py)
and runs the same fixes over it as over the Japanese game. Where a fix writes in the game's own words, its module
holds those words per translation, under the keys here: tools/expshow.py, expgap.py, moonfast.py, targetprompt.py,
text/talkgaps.json (the key `talk`) and run/mk_holds.py (the connectors).

  sneikkimies    Sneikkimies' English translation, the one tested since the first release: its giten.bps
                 (romhacking.net translation 7343) on PepsimanGB's pre-made Japanese HDI. Its scripts are rewritten:
                 lengths and branch offsets change.
  delacannon-en  delacannon's English (github.com/delacannon/giten-megami-tensei-tokyo-mokushiroku-i18n, version
                 2026.11.03): its page patcher on the Japanese reference HDI. Every record keeps its Japanese byte
                 layout, the text padded with 1F57 (tools/layoutrepair.py).
  delacannon-es  the same project's Spanish. Its accented letters take half-width katakana codes, redrawn in
                 the game's font: SPANISH below.
"""
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
STAGE = WORK / "build" / "enhancements"

TRANSLATIONS = {
    "sneikkimies": dict(lang="en", talk="en", name="Sneikkimies' English translation",
                        reference=STAGE / "english-translation-test" / "English.hdi",
                        stage=STAGE / "english-adaptation"),
    "delacannon-en": dict(lang="en", talk="en", name="delacannon's English translation",
                          reference=STAGE / "delacannon" / "Delacannon_EN.hdi",
                          stage=STAGE / "delacannon-en"),
    "delacannon-es": dict(lang="es", talk="es", name="delacannon's Spanish translation",
                          reference=STAGE / "delacannon" / "Delacannon_ES.hdi",
                          stage=STAGE / "delacannon-es"),
}

# delacannon's Spanish: the letters ASCII lacks, on the codes its font redraws (read off its own scripts)
SPANISH = {"á": 0xC1, "é": 0xC9, "í": 0xCD, "ó": 0xD3, "ú": 0xDA, "ü": 0xDC, "ñ": 0xD1, "¿": 0xBF, "¡": 0xBA,
           "Á": 0xB6, "É": 0xB7, "Í": 0xB8, "Ó": 0xB9, "Ú": 0xBB}


def encode_char(key, ch):
    """One character in the translation's encoding: printable ASCII, the Spanish letters of SPANISH for
    delacannon-es, else ValueError."""
    if key == "delacannon-es" and ch in SPANISH:
        return bytes([SPANISH[ch]])
    if ch == "\n" or " " <= ch <= "~":
        return ch.encode("ascii")
    raise ValueError(f"{ch!r} has no code in {key}")


def encode(key, text):
    return b"".join(encode_char(key, ch) for ch in text)


class Text:
    """The text encoder tools/textbuild.encode_unit takes (like buildcore.JapaneseText), for a translation."""

    def __init__(self, key):
        if key not in TRANSLATIONS:
            raise ValueError(f"unknown translation {key!r}")
        self.key = key

    def encode_char(self, ch):
        return encode_char(self.key, ch)
