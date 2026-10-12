#!/usr/bin/env python3
"""Write the battle message holds out as two self-contained .bat patches that need nothing installed.

The build puts a hold after each kind of battle message (tools/holds.py). A hold is the game's own
command 210 in mode 2, five bytes, `1E 10 01 02 <frames>`, and the last of them is the only thing
that tells a long hold from one that is over before it is seen: the wait counts the number down once
a frame and ends on the frame the count reaches 1, so 2 frames is over on the first frame and no hold
at all. That is what these patches write — the count, never the command — so the file keeps its
length and the patch is a handful of bytes either way, in the same shape as the other three.

    原始日文版的节奏  every hold the translation added counts 2 frames: messages follow one another
    汉化节奏  every one counts what text/holds.json asks for

The game's own holds are not touched. Four of them the translation took out altogether, because the
hold it adds for that message sits in the same place; those four cannot come back this way, so
原始日文版的节奏 is the original pace minus them.

The count sits inside a file whose bytes are chained through the cipher, so the patch decrypts the
file, writes the counts and encrypts it again — the same cipher tools/mkpatchbat.py uses. It finds
the file by the stretch of ciphertext ahead of the first count, which no edit of either state moves.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ddsfile  # noqa: E402
import tables  # noqa: E402
from mkpatchbat import CMD_HEAD, DEFAULT_IMAGE  # noqa: E402

HOLD = b"\x1e\x10\x01\x02"
OFF = 2                                 # frames: the wait is over on the frame it starts
SIG = 16                                # bytes of the file the patch finds it by

PS_BODY = r"""
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$img = $env:GITEN_IMAGE
$action = $env:GITEN_ACTION
if ($action -eq 'revert') { $doing = '原始日文版的节奏' } else { $doing = '汉化节奏' }
if (-not (Test-Path -LiteralPath $img)) {
  Write-Host "找不到镜像文件：$img"
  Write-Host "把汉化版 Giten_CN.hdi 拖到本文件上即可。"
  exit 1
}
$img = (Resolve-Path -LiteralPath $img).Path

function FromHex([string]$h) {
  $n = $h.Length / 2
  $b = New-Object byte[] $n
  for ($i = 0; $i -lt $n; $i++) { $b[$i] = [Convert]::ToByte($h.Substring(2 * $i, 2), 16) }
  ,$b
}

$bytes = [IO.File]::ReadAllBytes($img)
$enc = [Text.Encoding]::GetEncoding(28591)
$text = $enc.GetString($bytes)

# Find and check every file before writing anything: one that does not read as either pace stops all.
$plans = @()
foreach ($f in $FILES) {
  $pat = $enc.GetString((FromHex $f.sig))
  $found = @()
  $from = 0
  while ($true) {
    $at = $text.IndexOf($pat, $from, [StringComparison]::Ordinal)
    if ($at -lt 0) { break }
    $found += $at
    $from = $at + 1
  }
  if ($found.Count -ne 1) {
    Write-Host "这个镜像里的 $($f.name) 找到 $($found.Count) 处，没有做任何改动。"
    Write-Host "这个补丁是为本包的汉化版镜像写的。"
    exit 1
  }
  $at = $found[0]
  $len = [int]$bytes[$at] -bor ([int]$bytes[$at + 1] -shl 8)
  if ($at + 2 + $len -gt $bytes.Length) {
    Write-Host "$($f.name) 的长度不对，没有做任何改动。"
    exit 1
  }
  $state = ([int]$bytes[$at] -bxor [int]$bytes[$at + 1]) -band 0xFF
  $plain = New-Object byte[] $len
  for ($k = 0; $k -lt $len; $k++) {
    $c = [int]$bytes[$at + 2 + $k]
    $plain[$k] = [byte]($c -bxor $state)
    $state = $c
  }
  foreach ($h in $f.holds) {
    $o = $h.o
    if ($plain[$o - 4] -ne 0x1E -or $plain[$o - 3] -ne 0x10 -or $plain[$o - 2] -ne 0x01 -or
        $plain[$o - 1] -ne 0x02) {
      Write-Host "$($f.name) 的第 $o 个字节不是一处停顿，没有做任何改动。"
      Write-Host "这个补丁是为本包的汉化版镜像写的。"
      exit 1
    }
    if ($plain[$o] -ne $h.f -and $plain[$o] -ne OFF_FRAMES) {
      Write-Host "$($f.name) 里有一处停顿是 $($plain[$o]) 帧，既不是原始日文版的节奏也不是汉化的节奏，没有做任何改动。"
      exit 1
    }
  }
  $plans += @{ f = $f; at = $at; len = $len; plain = $plain }
}

$changed = 0
foreach ($p in $plans) {
  $plain = $p.plain
  $dirty = $false
  foreach ($h in $p.f.holds) {
    if ($action -eq 'revert') { $want = OFF_FRAMES } else { $want = $h.f }
    if ($plain[$h.o] -ne $want) { $plain[$h.o] = [byte]$want; $dirty = $true }
  }
  if (-not $dirty) { continue }
  $at = $p.at
  $state = ([int]$bytes[$at] -bxor [int]$bytes[$at + 1]) -band 0xFF
  for ($k = 0; $k -lt $p.len; $k++) {
    $c = [int]$plain[$k] -bxor $state
    $bytes[$at + 2 + $k] = [byte]$c
    $state = $c
  }
  $changed += $p.f.holds.Count
}

if ($changed -eq 0) {
  Write-Host "${img}：已经是${doing}，无需改动"
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
Write-Host "${img}：改成${doing}完成 — $changed 处停顿"
"""


class HoldBatError(ValueError):
    pass


def in_file(parsed, added):
    """[(offset of the count in the decrypted file, frames)] from {(chunk, record): [offset in the
    record]}, which is what the build knows.

    A record sits where the records before it end: a chunk opens with how many it holds, and each
    record with its id and its length. Only a one-chunk file can be patched, because the patch finds
    the file by the start of that chunk."""
    if len(parsed) != 1:
        raise HoldBatError(f"{len(parsed)} 个块，这个补丁只会改单块文件")
    out, at = [], 2                       # past the record count
    for pos, r in enumerate(parsed[0]):
        at += 3 if r.cond is None else 7  # [id][len] or [id][FFFF][a][b][len]
        for off in added.get((0, pos), ()):
            if r.payload[off - 4:off] != HOLD:
                raise HoldBatError(f"记录 {pos:02X} 第 {off} 字节不是一处停顿")
            out.append((at + off, r.payload[off]))
        at += len(r.payload)
    if out and 2 + out[0][0] < SIG:       # the stored file opens with the chunk's length word
        raise HoldBatError(f"第一处停顿在第 {out[0][0]} 字节，用来认文件的 {SIG} 字节会被改动")
    return out


def check(built, sites_of):
    """Every place a patch would write really holds the game's mode-2 command and the frame count
    the build put there — read back out of the file as it will be stored."""
    for name, places in sorted(sites_of.items()):
        chunks = tables.chunks_of(built[name])
        if len(chunks) != 1:
            raise HoldBatError(f"{name}: {len(chunks)} 个块，这个补丁只会改单块文件")
        plain = chunks[0]
        for off, frames in places:
            if plain[off - 4:off] != HOLD or plain[off] != frames:
                raise HoldBatError(f"{name}: 第 {off} 字节不是 {frames} 帧的停顿")
    return sum(len(p) for p in sites_of.values())


def ps_files(found, built):
    lines = ["$FILES = @("]
    for name, holds in sorted(found.items()):
        # hash tables, not pairs: PowerShell unrolls an array that holds a single array, and a file
        # with one hold would then arrive as two numbers instead of one place
        pairs = ", ".join(f"@{{o={o};f={v}}}" for o, v in holds)
        lines.append(f"  @{{ name = '{name}'; sig = '{built[name][:SIG].hex()}';")
        lines.append(f"     holds = @({pairs}) }}")
    lines.append(")")
    return "\n".join(lines)


def build(action, found, built):
    head = CMD_HEAD.format(action=action, default=DEFAULT_IMAGE).replace("\n", "\r\n")
    body = (ps_files(found, built) + "\n" + PS_BODY).replace("OFF_FRAMES", str(OFF))
    return head + body.replace("\n", "\r\n")


def main(outdir, found, built):
    os.makedirs(outdir, exist_ok=True)
    check(built, found)
    written = []
    for action, filename in (("apply", "启用 汉化节奏.bat"), ("revert", "关闭 汉化节奏.bat")):
        path = os.path.join(outdir, filename)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(build(action, found, built))
        written.append(path)
        print(f"{path}  {os.path.getsize(path)} 字节")
    print(f"  {sum(len(h) for h in found.values())} 处停顿，"
          + "、".join(f"{n} {len(h)} 处" for n, h in sorted(found.items())))
    return written
