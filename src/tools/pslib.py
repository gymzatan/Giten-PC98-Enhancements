#!/usr/bin/env python3
"""The PowerShell of the numeric editor's .bat patches (tools/mkpatchbat.py): the disk (HDI header, PC-98 partition table, BPB), the FAT and its files (find by name, read, write
growing or shrinking the cluster chain), the script cipher and records, table entries by number and
sites of DDS98.EXE, and the byte helpers. It reads the image named by $img into $bytes, and Refuse
ends the patch with nothing written; Hold does the same for a toggle another one is built on (a site in
the form that one leaves it in), naming the one to take out first."""

PS_LIB = r"""
function Refuse([string]$why) {
  Write-Host $why
  Write-Host "这个补丁认得原始日文版和本包的汉化版镜像，没有做任何改动。"
  exit 1
}

function Hold([string]$by) {
  Write-Host "镜像里打着「$by」，它建立在这一项之上：要先运行「关闭 $by.bat」，再关这一项。"
  Write-Host "没有做任何改动。"
  exit 1
}

function FromHex([string]$h) {
  $n = $h.Length / 2
  $b = New-Object byte[] $n
  for ($i = 0; $i -lt $n; $i++) { $b[$i] = [Convert]::ToByte($h.Substring(2 * $i, 2), 16) }
  ,$b
}

function U16($b, [int]$o) { [int]$b[$o] -bor ([int]$b[$o + 1] -shl 8) }
function U32($b, [int]$o) { [long](U16 $b $o) -bor ([long](U16 $b ($o + 2)) -shl 16) }
function SetU16($b, [int]$o, [int]$v) {
  $b[$o] = [byte]($v -band 0xFF)
  $b[$o + 1] = [byte](($v -shr 8) -band 0xFF)
}

$sha1 = [Security.Cryptography.SHA1]::Create()
function Sha([byte[]]$b) { ($sha1.ComputeHash($b) | ForEach-Object { $_.ToString('x2') }) -join '' }

function Same([byte[]]$b, [int]$o, [byte[]]$want) {
  if ($o + $want.Length -gt $b.Length) { return $false }
  for ($i = 0; $i -lt $want.Length; $i++) { if ($b[$o + $i] -ne $want[$i]) { return $false } }
  return $true
}

$bytes = [IO.File]::ReadAllBytes($img)

# ---- the disk: HDI header, the PC-98 partition table in sector 1, the boot sector's BPB ----
$hdr = [int](U32 $bytes 8)
$sect = [int](U32 $bytes 16)
$spt = [int](U32 $bytes 20)
$heads = [int](U32 $bytes 24)
$pt = $hdr + $sect
$lba = ((U16 $bytes ($pt + 10)) * $heads + [int]$bytes[$pt + 9]) * $spt + [int]$bytes[$pt + 8]
$part = $hdr + $lba * $sect
$bps = U16 $bytes ($part + 11)
$spc = [int]$bytes[$part + 13]
$res = U16 $bytes ($part + 14)
$nfat = [int]$bytes[$part + 16]
$rootN = U16 $bytes ($part + 17)
$total = [long](U16 $bytes ($part + 19))
if ($total -eq 0) { $total = U32 $bytes ($part + 32) }
$spf = U16 $bytes ($part + 22)
if ($bps -le 0 -or $spc -le 0 -or $nfat -le 0 -or $spf -le 0) { Refuse "读不懂这个镜像的文件系统。" }
$rootSec = [int][Math]::Ceiling($rootN * 32 / $bps)
$fatOff = $part + $res * $bps
$rootOff = $part + ($res + $nfat * $spf) * $bps
$dataOff = $rootOff + $rootSec * $bps
$cs = $bps * $spc
$nclus = [int][Math]::Floor(($total - ($res + $nfat * $spf + $rootSec)) / $spc)
$fat16 = $nclus -ge 4085
if ($fat16) { $eoc = 0xFFFF } else { $eoc = 0xFFF }
$maxClus = 1 + $nclus

function GetFat([int]$c) {
  if ($fat16) { return U16 $bytes ($fatOff + 2 * $c) }
  $v = U16 $bytes ($fatOff + $c + ($c -shr 1))
  if ($c -band 1) { return $v -shr 4 }
  return $v -band 0xFFF
}

function SetFat([int]$c, [int]$v) {
  for ($i = 0; $i -lt $nfat; $i++) {
    $base = $fatOff + $i * $spf * $bps
    if ($fat16) { SetU16 $bytes ($base + 2 * $c) $v; continue }
    $o = $base + $c + ($c -shr 1)
    $cur = U16 $bytes $o
    if ($c -band 1) { $cur = ($cur -band 0x000F) -bor (($v -band 0xFFF) -shl 4) }
    else { $cur = ($cur -band 0xF000) -bor ($v -band 0xFFF) }
    SetU16 $bytes $o $cur
  }
}

function Chain([int]$c) {
  $out = New-Object 'System.Collections.Generic.List[int]'
  while ($c -ge 2 -and $c -lt ($eoc - 0xF)) {
    if ($out.Contains($c)) { Refuse "镜像的 FAT 里有循环的簇链。" }
    $out.Add($c)
    $c = GetFat $c
  }
  ,$out
}

function ClusterOff([int]$c) { $dataOff + ($c - 2) * $cs }

# the offset in the image of a directory entry, by 8.3 name; $dir -1 is the root directory
function FindEntry([int]$dir, [string]$name) {
  $parts = $name.ToUpper().Split('.')
  $want = [Text.Encoding]::ASCII.GetBytes($parts[0].PadRight(8) + $(if ($parts.Count -gt 1) { $parts[1] } else { '' }).PadRight(3))
  $slots = New-Object 'System.Collections.Generic.List[long]'
  if ($dir -lt 0) { for ($i = 0; $i -lt $rootN; $i++) { $slots.Add($rootOff + 32 * $i) } }
  else { foreach ($c in (Chain $dir)) { for ($i = 0; $i -lt $cs / 32; $i++) { $slots.Add((ClusterOff $c) + 32 * $i) } } }
  foreach ($o in $slots) {
    $first = $bytes[$o]
    if ($first -eq 0) { break }
    if ($first -eq 0xE5 -or ($bytes[$o + 11] -band 0x0F) -eq 0x0F) { continue }
    if (Same $bytes $o $want) { return [int]$o }
  }
  return -1
}

function ReadFile([int]$e) {
  $size = [int](U32 $bytes ($e + 28))
  $data = New-Object byte[] $size
  $at = 0
  foreach ($c in (Chain (U16 $bytes ($e + 26)))) {
    $n = [Math]::Min($cs, $size - $at)
    if ($n -le 0) { break }
    [Array]::Copy($bytes, (ClusterOff $c), $data, $at, $n)
    $at += $n
  }
  if ($at -ne $size) { Refuse "镜像里的文件比它的簇链长。" }
  ,$data
}

# write a file's new content, growing or shrinking its chain at the end the way DOS would
function WriteFile([int]$e, [byte[]]$data) {
  $ch = Chain (U16 $bytes ($e + 26))
  $need = [Math]::Max(1, [int][Math]::Ceiling($data.Length / $cs))
  $next = 2
  while ($ch.Count -lt $need) {
    while ($next -le $maxClus -and ((GetFat $next) -ne 0 -or $ch.Contains($next))) { $next++ }
    if ($next -gt $maxClus) { Refuse "镜像里没有空余的簇了。" }
    SetFat $ch[$ch.Count - 1] $next
    SetFat $next $eoc
    $ch.Add($next)
  }
  if ($ch.Count -gt $need) {
    SetFat $ch[$need - 1] $eoc
    for ($i = $need; $i -lt $ch.Count; $i++) { SetFat $ch[$i] 0 }
  }
  $at = 0
  for ($i = 0; $i -lt $need; $i++) {
    $n = [Math]::Min($cs, $data.Length - $at)
    [Array]::Copy($data, $at, $bytes, (ClusterOff $ch[$i]), $n)
    $at += $n
  }
  $size = $data.Length
  SetU16 $bytes ($e + 28) ($size -band 0xFFFF)
  SetU16 $bytes ($e + 30) (($size -shr 16) -band 0xFFFF)
}

# ---- script files: chunks of [length][bytes chained on the ciphertext], records inside ----
function Chunks([byte[]]$f) {
  $out = @()
  $at = 0
  while ($at -lt $f.Length) {
    $w = U16 $f $at
    if ($at + 2 + $w -gt $f.Length) { Refuse "文件的块长度不对。" }
    $state = ($w -band 0xFF) -bxor ($w -shr 8)
    $plain = New-Object byte[] $w
    for ($k = 0; $k -lt $w; $k++) {
      $c = [int]$f[$at + 2 + $k]
      $plain[$k] = [byte]($c -bxor $state)
      $state = $c
    }
    $out += ,$plain
    $at += 2 + $w
  }
  ,$out
}

function Encrypt([byte[]]$plain) {
  $w = $plain.Length
  $out = New-Object byte[] ($w + 2)
  SetU16 $out 0 $w
  $state = ($w -band 0xFF) -bxor ($w -shr 8)
  for ($k = 0; $k -lt $w; $k++) {
    $c = [int]$plain[$k] -bxor $state
    $out[2 + $k] = [byte]$c
    $state = $c
  }
  ,$out
}

function FindRecord([byte[]]$plain, [int]$id) {
  $n = U16 $plain 0
  $p = 2
  for ($i = 0; $i -lt $n; $i++) {
    if ($p + 3 -gt $plain.Length) { return $null }
    if ((U16 $plain ($p + 1)) -eq 0xFFFF) { $hl = 7; $len = U16 $plain ($p + 5) } else { $hl = 3; $len = U16 $plain ($p + 1) }
    if ([int]$plain[$p] -eq $id) { return @{ head = $p; hl = $hl; at = $p + $hl; len = $len } }
    $p += $hl + $len
  }
  return $null
}

function Slice([byte[]]$b, [int]$o, [int]$n) { $out = New-Object byte[] $n; [Array]::Copy($b, $o, $out, 0, $n); ,$out }

# 'orig', 'fixed' or $null for one listed record
function RecState([byte[]]$payload, $r) {
  $tail = FromHex $r.tail
  if ($payload.Length -eq $r.len) {
    $orig = $true
    foreach ($s in $r.sites) { if (-not (Same $payload $s.o (FromHex $s.a))) { $orig = $false } }
    if ($orig) {
      if ((Sha $payload) -eq $r.sha) { return 'orig' }
      return $null
    }
    if ($tail.Length -gt 0) { return $null }
  }
  if ($payload.Length -ne $r.len + $tail.Length) { return $null }
  if (-not (Same $payload $r.len $tail)) { return $null }
  $orig = Slice $payload 0 $r.len
  foreach ($s in $r.sites) {
    if (-not (Same $payload $s.o (FromHex $s.b))) { return $null }
    $a = FromHex $s.a
    [Array]::Copy($a, 0, $orig, $s.o, $a.Length)
  }
  if ((Sha $orig) -eq $r.sha) { return 'fixed' }
  return $null
}

function Target([byte[]]$payload, $r, [string]$state) {
  $want = 'fixed'
  if ($action -eq 'revert') { $want = 'orig' }
  if ($state -eq $want) { return $null }
  $out = Slice $payload 0 $r.len
  foreach ($s in $r.sites) {
    $v = FromHex $s.a
    if ($want -eq 'fixed') { $v = FromHex $s.b }
    [Array]::Copy($v, 0, $out, $s.o, $v.Length)
  }
  if ($want -eq 'fixed') { $out = [byte[]]($out + (FromHex $r.tail)) }
  ,$out
}

# ---- a table file: chunks as above, holding [count][offsets][entries]; a stretch of an entry by its
# number, which has to be of the listed kind (byte 4) and hold one of its two forms. Sets every listed
# stretch to the form $action asks for and gives the file's new content with the count and the names of
# the entries it changed, or $null when the file already holds that form. $newWord names the second form.
function TableEdit($t, [int]$dir, [string]$newWord) {
  $e = FindEntry $dir $t.name
  if ($e -lt 0) { Refuse "镜像里找不到 DDS98\$($t.name)。" }
  $chunks = Chunks (ReadFile $e)
  $n = 0
  $names = @()
  foreach ($x in $t.entries) {
    if ($x.ci -ge $chunks.Count) { Refuse "DDS98\$($t.name) 的块数不对。" }
    $plain = $chunks[$x.ci]
    $cnt = U16 $plain 0
    if ($x.i -ge $cnt) { Refuse "DDS98\$($t.name) 没有第 $($x.i) 条。" }
    $at = U16 $plain (2 + 2 * $x.i)
    $end = $plain.Length
    if ($x.i + 1 -lt $cnt) { $end = U16 $plain (4 + 2 * $x.i) }
    $a = FromHex $x.a
    $b = FromHex $x.b
    $o = $at + $x.o
    if ($end -gt $plain.Length -or $o + $a.Length -gt $end -or [int]$plain[$at + 4] -ne $x.kind) {
      Refuse "DDS98\$($t.name) 第 $($x.i) 条不是这个补丁认得的数据。"
    }
    if (-not (Same $plain $o $a) -and -not (Same $plain $o $b)) { Refuse "DDS98\$($t.name) 第 $($x.i) 条既不是改动前的内容也不是${newWord}的内容。" }
    $want = $b
    if ($action -eq 'revert') { $want = $a }
    if (-not (Same $plain $o $want)) {
      [Array]::Copy($want, 0, $plain, $o, $want.Length)
      $n++
      if ($x.name) { $names += $x.name }
    }
  }
  if ($n -eq 0) { return $null }
  $file = New-Object byte[] 0
  foreach ($c in $chunks) { $file = [byte[]]($file + (Encrypt $c)) }
  @{ e = $e; data = $file; n = $n; names = $names }
}

# ---- DDS98.EXE: sites by file offset, each in one of its two forms. Sets every site to the form $action
# asks for and gives the program's new content, or $null when it already holds that form. A site whose
# first form is another patch's fixed one names that patch in need.
# (PowerShell names do not tell case apart: the program's bytes must not be called $exe)
function ExeEdit($x, [int]$dir, [string]$newWord) {
  $e = FindEntry $dir $x.name
  if ($e -lt 0) { Refuse "镜像里找不到 DDS98\$($x.name)。" }
  $prog = ReadFile $e
  $dirty = $false
  $missing = @()
  foreach ($s in $x.sites) {
    $a = FromHex $s.a
    $b = FromHex $s.b
    # held: the form a toggle built on this one leaves the site in - this one is in, and stays while that one is
    if ($s.held -and (Same $prog $s.o (FromHex $s.held))) {
      if ($action -eq 'revert') { Hold $s.by }
      continue
    }
    if (-not (Same $prog $s.o $a) -and -not (Same $prog $s.o $b)) {
      if (-not $s.need) { Refuse "DDS98\$($x.name) 既不是改动前的内容也不是${newWord}的内容。" }
      if ($missing -notcontains $s.need) { $missing += $s.need }
      continue
    }
    $want = $b
    if ($action -eq 'revert') { $want = $a }
    if (-not (Same $prog $s.o $want)) { [Array]::Copy($want, 0, $prog, $s.o, $want.Length); $dirty = $true }
  }
  if ($missing.Count -gt 0) {
    $bats = ($missing | ForEach-Object { "「启用 $_.bat」" }) -join '和'
    Refuse "DDS98\$($x.name) 里没有打上$($missing -join '和')：要先运行$bats。"
  }
  if (-not $dirty) { return $null }
  @{ e = $e; data = $prog }
}
"""
