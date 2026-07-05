# Deploy H3ButtonPlugin do WSZYSTKICH folderow HoMM z _HD3_Data\Packs
$pluginRoot = 'F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin'
$srcTextMap = "$pluginRoot\tools\audio_woj_campaign\text_map_with_filter.txt"

# Zbierz wszystkie istniejace DLL i wybierz NAJNOWSZY (po LastWriteTime)
$dllCandidates = @(
    "$pluginRoot\build\bin\Release\H3ButtonPlugin.dll",
    "$pluginRoot\build\bin\Debug\H3ButtonPlugin.dll",
    "$pluginRoot\cmake-build-release\bin\H3ButtonPlugin.dll",
    "$pluginRoot\cmake-build-debug\bin\H3ButtonPlugin.dll"
)
$srcDll = $null
$srcDllTime = [DateTime]::MinValue
foreach ($c in $dllCandidates) {
    if ((Test-Path -LiteralPath $c) -and (Get-Item $c).Length -gt 0) {
        $t = (Get-Item $c).LastWriteTime
        if ($t -gt $srcDllTime) {
            $srcDll = $c
            $srcDllTime = $t
        }
    }
}
if ($srcDll) {
    Write-Host "Znaleziono DLL: $srcDll ($($srcDllTime.ToString('HH:mm:ss')), $(((Get-Item $srcDll).Length / 1KB).ToString('0.0')) KB)"
}
if (!$srcDll) {
    Write-Host "BLAD: Nie znaleziono zadnego poprawnego H3ButtonPlugin.dll!"
    Write-Host "Zbuduj projekt najpierw (cmake --build)."
    exit 1
}
$srcAudio   = "$pluginRoot\tools\audio_woj_campaign"

# Szukaj wszystkich folderow HoMM w katalogu nadrzednym
$parentDir = 'F:\gry\h3-Chro-Hdmod(modowanie)'
$hommDirs = Get-ChildItem -LiteralPath $parentDir -Directory | Where-Object { $_.Name -like 'HoMM*' }

$deployed = $false
foreach ($d in $hommDirs) {
    $packsDir = Join-Path $d.FullName '_HD3_Data\Packs'
    if (Test-Path -LiteralPath $packsDir) {
        $targetDir = Join-Path $packsDir 'TextDetector'
        if (!(Test-Path -LiteralPath $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir | Out-Null
        }

        # 1. Kopiuj DLL
        $dstDll = Join-Path $targetDir 'H3ButtonPlugin.dll'
        try {
            Copy-Item $srcDll $dstDll -Force -ErrorAction Stop
            Write-Host "OK: DLL -> $dstDll"
            $deployed = $true
        } catch {
            Write-Host "BLAD DLL: $($_.Exception.Message)"
            Write-Host "  -> Zamknij gre i sprobuj ponownie!"
        }

        # 2. Kopiuj text_map.txt (z pliku with_filter)
        if (Test-Path -LiteralPath $srcTextMap) {
            $dstTextMap = Join-Path $targetDir 'text_map.txt'
            Copy-Item $srcTextMap $dstTextMap -Force
            Write-Host "OK: text_map.txt -> $dstTextMap"
        } else {
            Write-Host "UWAGA: Brak $srcTextMap - uruchom generate_text_map_with_filter.py"
        }

        # 3. Kopiuj pliki audio (woj_*.mp3) do podkatalogu audio\
        $audioTargetDir = Join-Path $targetDir 'audio'
        if (!(Test-Path -LiteralPath $audioTargetDir)) {
            New-Item -ItemType Directory -Path $audioTargetDir | Out-Null
        }
        $mp3Files = Get-ChildItem -LiteralPath $srcAudio -Filter 'woj_*.mp3' -ErrorAction SilentlyContinue
        if ($mp3Files) {
            foreach ($mp3 in $mp3Files) {
                Copy-Item $mp3.FullName (Join-Path $audioTargetDir $mp3.Name) -Force
            }
            Write-Host "OK: $($mp3Files.Count) plikow audio -> $audioTargetDir"
        } else {
            Write-Host "UWAGA: Brak plikow woj_*.mp3 w $srcAudio"
        }
    }
}

if (!$deployed) {
    Write-Host "UWAGA: Nie znaleziono zadnego folderu z _HD3_Data\Packs!"
    Write-Host "Foldery HoMM:"
    foreach ($d in $hommDirs) { Write-Host "  $($d.FullName)" }
}
