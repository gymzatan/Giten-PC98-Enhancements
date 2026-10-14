#!/usr/bin/env python3
"""Write an edit table out as two self-contained .bat patches that need nothing installed, optionally with whole
files and sites of DDS98.EXE beside it. The numeric editor (tools/demoned.py, 「生成 bat 补丁」) writes its own
table with it, as 「难度调整」.

    mkpatchbat.py [OUTDIR]      default: patch/ (balance.json alone)

Each .bat carries a Windows PowerShell script in its own tail, past the `exit /b` that ends the part
cmd reads. PowerShell is part of Windows, so the patch has no dependencies at all. The marker that
separates the two halves is spelled in pieces where cmd invokes PowerShell, so that the search for it
cannot land on the invocation itself.

A demon record (P2*): the data file's cipher chains each byte onto the previous ciphertext byte, so
the ciphertext ahead of the first edited byte is untouched by the patch, and the ciphertext ahead of
the name field is the same in the Japanese original and the Chinese build. The stretch ahead of
whichever comes first is what the patch searches for to find the record, and it reads the same in
both builds whether the patch has been applied or not. From there the patch decrypts the record,
makes sure it is the right one by its id, checks every value against the pair the edit names — edits
past the name field included — writes the wanted ones and encrypts it back: the same all-or-nothing
check tools/hdipatch.py makes, with no dependency on what the name field holds.

A record of a table file (ET0004#102): it sits after text the two builds translate differently, so
it is reached the other way, through the image's own FAT (tools/pslib.py TableEdit): the file is
found under DDS98\\ and decrypted, the record looked up by its number in the table's pointer list,
and the stretch from its first to its last edited byte has to hold one of its two forms - the
numbers ahead of a record's name are the same in both builds.

A whole file is found by name under DDS98\\ the same way and has to hold exactly one of its two
contents, as shipped or as changed; writing the other one grows or shrinks it the way DOS would. A
site of DDS98.EXE is found by its file offset and has to hold one of its two forms (ExeEdit).
Everything is checked before anything is written.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balance  # noqa: E402
import p2fields  # noqa: E402
import records as rec  # noqa: E402
from pslib import PS_LIB  # noqa: E402
from tables import chunks_of  # noqa: E402

DEFAULT_IMAGE = r"%~dp0..\Giten_CN.hdi"
MIN_SIG = 8                             # shorter than this is too weak to find a record by

CMD_HEAD = """@echo off
setlocal
chcp 65001 >nul
set "GITEN_ACTION={action}"
set "GITEN_IMAGE=%~1"
if "%GITEN_IMAGE%"=="" set "GITEN_IMAGE={default}"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0',[Text.Encoding]::UTF8);$m='#=P'+'S=#';iex $s.Substring($s.IndexOf($m)+$m.Length)"
echo.
pause
exit /b
#=PS=#
"""

# The PowerShell is in three pieces: what the patch is doing and on which image, the disk, FAT and
# byte machinery the patches share (tools/pslib.py, which reads the image into $bytes), and this
# patch's own run.
PS_HEAD = r"""
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$img = $env:GITEN_IMAGE
$action = $env:GITEN_ACTION
if ($action -eq 'revert') { $doing = '还原'; $done = '原始日文版的' } else { $doing = '打补丁'; $done = '补丁后' }
if (-not (Test-Path -LiteralPath $img)) {
  Write-Host "找不到镜像文件：$img"
  Write-Host "把 Giten.hdi（原始日文版）或 Giten_CN.hdi（汉化版）拖到本文件上即可。"
  exit 1
}
$img = (Resolve-Path -LiteralPath $img).Path
"""

PS_BODY = r"""
function ReadValue($plain, $off, $w) {
  $v = 0
  for ($i = $w - 1; $i -ge 0; $i--) { $v = ($v -shl 8) -bor [int]$plain[$off + $i] }
  return $v
}

function WriteValue($plain, $off, $w, $v) {
  for ($i = 0; $i -lt $w; $i++) {
    $plain[$off + $i] = [byte](($v -shr (8 * $i)) -band 0xFF)
  }
}

function Decrypt($bytes, $at, $len) {
  $w0 = [int]$bytes[$at] -bor ([int]$bytes[$at + 1] -shl 8)
  $state = ($w0 -band 0xFF) -bxor ($w0 -shr 8)
  $plain = New-Object byte[] ($len - 2)
  for ($k = 2; $k -lt $len; $k++) {
    $c = [int]$bytes[$at + $k]
    $plain[$k - 2] = [byte]($c -bxor $state)
    $state = $c
  }
  ,$plain
}

$enc = [Text.Encoding]::GetEncoding(28591)
$text = $enc.GetString($bytes)

# Find and check every record and file before writing anything: one that does not match stops the whole patch.
$plans = @()
foreach ($r in $RECORDS) {
  $pat = $enc.GetString((FromHex $r.sig))
  $found = @()
  $from = 0
  while ($true) {
    $at = $text.IndexOf($pat, $from, [StringComparison]::Ordinal)
    if ($at -lt 0) { break }
    if ($at + $r.len -le $bytes.Length) {
      $plain = Decrypt $bytes $at $r.len
      if ((ReadValue $plain ID_OFF 2) -eq $r.id) { $found += @{ at = $at; plain = $plain } }
    }
    $from = $at + 1
  }
  if ($found.Count -eq 0) {
    Write-Host "这个镜像里找不到「$($r.name)」的数据，没有做任何改动。"
    exit 1
  }
  if ($found.Count -gt 1) {
    Write-Host "「$($r.name)」的数据在镜像里出现了不止一次，没有做任何改动。"
    exit 1
  }
  $plain = $found[0].plain
  $isOrig = $true
  $isEdited = $true
  foreach ($e in $r.edits) {
    if ($e.a -eq $e.b) { continue }   # says only what the field is to hold, tells no state apart
    $v = ReadValue $plain $e.off $e.w
    if ($v -ne $e.a) { $isOrig = $false }
    if ($v -ne $e.b) { $isEdited = $false }
  }
  if ((-not $isOrig) -and (-not $isEdited)) {
    Write-Host "「$($r.name)」的数值既不是补丁前的也不是补丁后的，这个补丁不是为它写的，没有做任何改动。"
    exit 1
  }
  $plans += @{ r = $r; at = $found[0].at; plain = $plain }
}

$filePlans = @()
$tablePlans = @()
$exePlan = $null
if ($FILES.Count -gt 0 -or $TABLES.Count -gt 0 -or $EXE.sites.Count -gt 0) {
  $dds = FindEntry -1 'DDS98'
  if ($dds -lt 0 -or -not ($bytes[$dds + 11] -band 0x10)) { Refuse "镜像里没有 DDS98 目录。" }
  $ddsDir = U16 $bytes ($dds + 26)
}
foreach ($f in $FILES) {
  $e = FindEntry $ddsDir $f.name
  if ($e -lt 0) { Refuse "镜像里找不到 DDS98\$($f.name)。" }
  $cur = ReadFile $e
  $a = FromHex $f.a
  $b = FromHex $f.b
  $isOrig = ($cur.Length -eq $a.Length) -and (Same $cur 0 $a)
  $isEdited = ($cur.Length -eq $b.Length) -and (Same $cur 0 $b)
  if ((-not $isOrig) -and (-not $isEdited)) {
    Write-Host "「$($f.label)」（DDS98\$($f.name)）既不是补丁前的内容也不是补丁后的内容，这个补丁不是为它写的，没有做任何改动。"
    exit 1
  }
  $filePlans += @{ f = $f; e = $e; a = $a; b = $b; isOrig = $isOrig }
}
foreach ($t in $TABLES) { $tablePlans += @{ t = $t; te = (TableEdit $t $ddsDir '补丁后') } }
if ($EXE.sites.Count -gt 0) { $exePlan = ExeEdit $EXE $ddsDir '补丁后' }

$changed = @()
foreach ($p in $plans) {
  $r = $p.r
  $plain = $p.plain
  $dirty = $false
  foreach ($e in $r.edits) {
    if ($action -eq 'revert') { $t = $e.a } else { $t = $e.b }
    if ((ReadValue $plain $e.off $e.w) -ne $t) {
      WriteValue $plain $e.off $e.w $t
      $dirty = $true
    }
  }
  if (-not $dirty) {
    Write-Host "  「$($r.name)」：已经是${done}数值"
    continue
  }
  $at = $p.at
  $w0 = [int]$bytes[$at] -bor ([int]$bytes[$at + 1] -shl 8)
  $state = ($w0 -band 0xFF) -bxor ($w0 -shr 8)
  for ($k = 0; $k -lt $plain.Length; $k++) {
    $c = [int]$plain[$k] -bxor $state
    $bytes[$at + 2 + $k] = [byte]$c
    $state = $c
  }
  $changed += $r.name
}
foreach ($p in $filePlans) {
  $wantOrig = $action -eq 'revert'
  if ($p.isOrig -eq $wantOrig) {
    Write-Host "  「$($p.f.label)」：已经是${done}内容"
    continue
  }
  if ($wantOrig) { WriteFile $p.e $p.a } else { WriteFile $p.e $p.b }
  $changed += $p.f.label
}
foreach ($p in $tablePlans) {
  if ($null -eq $p.te) {
    Write-Host "  「$($p.t.label)」：已经是${done}数值"
    continue
  }
  WriteFile $p.te.e $p.te.data
  $changed += $p.te.names
}
if ($EXE.sites.Count -gt 0) {
  if ($null -eq $exePlan) { Write-Host "  「$($EXE.label)」：已经是${done}内容" }
  else {
    WriteFile $exePlan.e $exePlan.data
    $changed += $EXE.label
  }
}

if ($changed.Count -eq 0) {
  Write-Host "${img}：无需改动"
  exit 0
}
$bak = "$img.bak"
if (-not (Test-Path -LiteralPath $bak)) {
  Copy-Item -LiteralPath $img -Destination $bak
  Write-Host "  已把原镜像另存为 $(Split-Path $bak -Leaf)"
}
$tmp = "$img.tmp"
[IO.File]::WriteAllBytes($tmp, $bytes)
Move-Item -LiteralPath $tmp -Destination $img -Force
Write-Host "${img}：${doing}完成 — $($changed -join '、')"
"""


def from_dir(path):
    """Read the data files out of a directory of extracted ones."""
    return lambda stem: open(os.path.join(path, stem + ".BIN"), "rb").read()


def records(data, blob_of, bound=()):
    """The demon records: [(stem, name, length, id, signature hex, [(offset, width, original, edited)])].

    The signature is the ciphertext ahead of the first edited byte or the name field, whichever comes
    first: the patch leaves it alone, so the record is found by it in either state, and the two
    builds differ only from the name field on, so it reads the same in both. That is also why the
    data may come from a disk image that already carries the edits — nothing ahead of the first
    edited byte moves. It only holds for a demon file, whose whole chunk is one record; a record
    inside an ET table sits after text that the two builds translate differently, and goes through
    table_entries() instead. bound: the other edit tables whose patches may be in the image too - a
    byte one of them edits ends the signature as well (the cipher chains every byte to the one before,
    so an edit changes all the ciphertext after it): 难度调整 and 再平衡 both edit 但他林 II's record."""
    out = []
    for target, entry in data["edits"].items():
        stem, index = rec.parse(target)
        if index is not None:
            continue
        blob = blob_of(stem)
        (plain,) = chunks_of(blob)
        edits = balance.edits(entry, target)
        first = min([off for off, _w, _a, _b in edits]
                    + [off for t in bound if target in t["edits"]
                       for off, _w, _a, _b in balance.edits(t["edits"][target], target)])
        sig_len = 2 + min(first, p2fields.NAME_AT)
        if sig_len < MIN_SIG:
            raise SystemExit(f"{stem}: 第一处改动在 0x{first:02X}，前面只剩 {sig_len} 字节，"
                             "不足以在镜像里认出这条记录")
        ident = struct.unpack_from("<H", plain, p2fields.ID_AT)[0]
        out.append((stem, entry.get("name", target), len(blob), ident, blob[:sig_len].hex(), edits))
    return out


KIND_AT = 4                             # the byte TableEdit checks a table record by
TABLE_LABELS = {"ET0001": "物品数据", "ET0004": "技能数据"}


def table_entries(data, blob_of):
    """The table records: {file name: [{ci, i, kind, o, a, b, name}]} - each record's stretch from its
    first to its last edited byte in both forms (the bytes between edits as the file holds them), by
    the record's number, with the byte at KIND_AT that TableEdit checks it by. That byte is a number
    ahead of the name, the same in both builds, and it must not be one the edits change."""
    out = {}
    for target, entry in data["edits"].items():
        stem, index = rec.parse(target)
        if index is None:
            continue
        plain = rec.plain_of(blob_of(stem))
        base = rec.base_of(plain, target)
        edits = balance.edits(entry, target)
        lo = min(off for off, _w, _a, _b in edits)
        hi = max(off + w for off, w, _a, _b in edits)
        if any(off <= KIND_AT < off + w for off, w, _a, _b in edits):
            raise SystemExit(f"{target}：改了第 {KIND_AT} 字节，bat 补丁就认不出这条记录了")
        a, b = bytearray(plain[base + lo:base + hi]), bytearray(plain[base + lo:base + hi])
        for off, w, orig, new in edits:
            a[off - lo:off - lo + w] = orig.to_bytes(w, "little")
            b[off - lo:off - lo + w] = new.to_bytes(w, "little")
        out.setdefault(stem + ".BIN", []).append(
            {"ci": 0, "i": index, "kind": plain[base + KIND_AT], "o": lo, "a": a.hex(), "b": b.hex(),
             "name": entry.get("name", target)})
    return out


def ps_tables(tables):
    lines = ["$TABLES = @("]
    for name, entries in tables.items():
        label = TABLE_LABELS.get(name[:-4], name)
        lines.append(f"  @{{ name = '{name}'; label = '{label}'; entries = @(")
        lines += [f"    @{{ ci = {x['ci']}; i = {x['i']}; kind = {x['kind']}; o = {x['o']}; a = '{x['a']}'; "
                  f"b = '{x['b']}'; name = '{x['name']}' }}," for x in entries]
        lines[-1] = lines[-1].rstrip(",")
        lines.append("  ) },")
    if tables:
        lines[-1] = lines[-1].rstrip(",")
    lines.append(")")
    return "\n".join(lines)


def held_forms(sites, by, dependents, need):
    """{file offset: (form, by)}: each of a toggle's sites [(offset, as shipped, as changed, ...)] that sites of the
    toggle `by` lie on - those of `dependents` [(offset, as shipped, as changed, need)] that name this toggle as their
    need - as it reads with that toggle in: its changed form with theirs written over."""
    out = {}
    for o, _a, b, *_rest in sites:
        form = bytearray(b)
        for t in dependents:
            lo, hi = max(o, t[0]), min(o + len(b), t[0] + len(t[2]))
            if t[3] == need and lo < hi:
                form[lo - o:hi - o] = t[2][lo - t[0]:hi - t[0]]
                out[o] = (bytes(form), by)
    return out


def ps_exe(exe):
    """exe: {name, label, sites: [(file offset, as shipped, as changed[, need])][, held: {offset: (form, by)}]} or
    None. A site whose shipped form is another patch's changed one names that patch as its need (None: as shipped),
    and the .bat says to enable it first; a site another patch builds on carries the form that patch leaves it in,
    and the .bat says to take that patch out first (pslib ExeEdit)."""
    if not exe:
        return "$EXE = @{ name = ''; label = ''; sites = @() }"
    held = exe.get("held", {})
    # hash tables, not pairs: PowerShell unrolls an array holding a single array
    sites = ", ".join(f"@{{o={s[0]};a='{s[1].hex()}';b='{s[2].hex()}'"
                      + (f";need='{s[3]}'" if len(s) > 3 and s[3] else "")
                      + (f";held='{held[s[0]][0].hex()}';by='{held[s[0]][1]}'" if s[0] in held else "") + "}"
                      for s in exe["sites"])
    return f"$EXE = @{{ name = '{exe['name']}'; label = '{exe['label']}'; sites = @({sites}) }}"


def ps_records(recs):
    lines = ["$RECORDS = @("]
    for _stem, name, length, ident, sig, edits in recs:
        items = ", ".join(f"@{{off={off}; w={w}; a={a}; b={b}}}" for off, w, a, b in edits)
        lines.append(f"  @{{ name = '{name}'; len = {length}; id = {ident}; sig = '{sig}';")
        lines.append(f"     edits = @({items}) }}")
    lines.append(")")
    return "\n".join(lines)


def ps_files(files):
    """files: [(name under DDS98\\, label, content as shipped, content as changed)]."""
    lines = ["$FILES = @("]
    for name, label, a, b in files:
        lines.append(f"  @{{ name = '{name}'; label = '{label}'; a = '{a.hex()}'; b = '{b.hex()}' }}")
    lines.append(")")
    return "\n".join(lines)


def build(action, recs, files=(), tables=None, exe=None):
    head = CMD_HEAD.format(action=action, default=DEFAULT_IMAGE).replace("\n", "\r\n")
    body = (ps_records(recs) + "\n" + ps_files(files) + "\n" + ps_tables(tables or {}) + "\n" + ps_exe(exe)
            + "\n" + PS_HEAD + PS_LIB + PS_BODY.replace("ID_OFF", str(p2fields.ID_AT)))
    return head + body.replace("\n", "\r\n")


def main(outdir, data, blob_of, files=(), exe=None, name="难度调整", bound=()):
    """files: whole files the patch also carries - [(name under DDS98\\, label, as shipped, as changed)];
    exe: sites of DDS98.EXE - {name, label, sites: [(file offset, as shipped, as changed[, need or None])][, held:
    held_forms()]}; name: the pair is 「启用 / 关闭 <name>.bat」 (the editor's own tables keep 难度调整); bound: the
    other edit tables that may be patched into the same image (records())."""
    recs = records(data, blob_of, bound)
    tables = table_entries(data, blob_of)
    os.makedirs(outdir, exist_ok=True)
    written = []
    for action, filename in (("apply", f"启用 {name}.bat"), ("revert", f"关闭 {name}.bat")):
        path = os.path.join(outdir, filename)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(build(action, recs, files, tables, exe))
        written.append(path)
    for path in written:
        print(f"{path}  {os.path.getsize(path)} 字节")
    for _stem, name, _len, _id, _sig, edits in recs:
        print(f"  「{name}」 {len(edits)} 处改动")
    for name, entries in tables.items():
        print(f"  DDS98\\{name}：" + "、".join(f"「{x['name']}」" for x in entries))
    for name, label, a, b in files:
        print(f"  「{label}」 DDS98\\{name} {len(a)} → {len(b)} 字节")
    if exe:
        print(f"  「{exe['label']}」 DDS98\\{exe['name']} {len(exe['sites'])} 处")
    return written


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "patch", balance.load(), from_dir(balance.SRC))
