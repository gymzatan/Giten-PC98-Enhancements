"""Shared Shift-JIS/JIS code conversion and character classification."""
import unicodedata

def jis_to_sjis(jis):
    ku, ten = (jis >> 8) - 0x20, (jis & 0xFF) - 0x20
    lead = (ku + 1) // 2 + (0x80 if ku <= 62 else 0xC0)
    trail = ten + (0x3F if ten <= 63 else 0x40) if ku % 2 else ten + 0x9E
    return bytes([lead, trail])


def sjis_to_jis(sj):
    lead, trail = sj[0], sj[1]
    ku = (lead - (0x80 if lead <= 0x9F else 0xC0)) * 2 - 1
    if trail >= 0x9F:
        ku, ten = ku + 1, trail - 0x9E
    else:
        ten = trail - (0x3F if trail <= 0x7E else 0x40)
    return (ku + 0x20) << 8 | (ten + 0x20)


def is_hanzi(ch):
    return unicodedata.name(ch, "").startswith("CJK UNIFIED IDEOGRAPH")

