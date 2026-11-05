# Deploy H3ButtonPlugin do WSZYSTKICH folderow HoMM z _HD3_Data\Packs
#
# Domyslnie (bez -Campaign) dziala DOKLADNIE jak dawniej: deployuje Woj do
# Packs\TextDetector\ (pojedynczy, historyczny slot - zachowany dla wstecznej
# zgodnosci z istniejacymi instalacjami).
#
# Z -Campaign <kod> buduje odzielna, samowystarczalna paczke dla danej kampanii
# Heroes Chronicles do Packs\TextDetector - <Nazwa>\. DLL NIE jest przemianowywany
# (zawsze H3ButtonPlugin.dll) - testy 2026-08-03 pokazaly, ze przemianowanie DLL-a
# psuje dzialanie wtyczki (Start() przestaje konczyc sie poprawnie, przyczyna
# nieustalona). Model "jedna aktywna paczka naraz" i tak nie wymaga unikalnej
# nazwy DLL-a - tylko jedna paczka jest kiedykolwiek zaladowana jednoczesnie.
#
# Wybor zrodlowego DLL-a PREFERUJE Release nad Debug niezaleznie od czasu modyfikacji
# pliku (nie samo LastWriteTime jak dawniej) - build Debug linkuje sie z debugowym
# CRT/MSVC runtime, ktorego zwykle nie ma poza srodowiskiem deweloperskim, wiec
# w realnej grze w ogole sie nie laduje. Wczesniejsza logika "najnowszy wygrywa"
# potrafila po cichu podmienic dzialajacy Release na taki niedzialajacy Debug,
# gdy ktos (np. IDE budujace w tle) odswiezyl folder cmake-build-debug/build\bin\Debug
# pozniej niz ostatni Release - objaw: "plugin przestal dzialac" bez zadnego bledu
# budowania. Debug jest teraz uzywany TYLKO gdy jawnie podasz -AllowDebug.
#
# Uzycie:
#   .\deploy.ps1                  # historyczny tryb: Woj -> Packs\TextDetector\
#   .\deploy.ps1 -Campaign Pod    # nowa paczka: Pod -> Packs\TextDetector - Podboj Podziemi\
#   .\deploy.ps1 -Campaign All    # wszystkie 8 kampanii, kazda we wlasnej paczce
#   .\deploy.ps1 -AllowDebug      # zezwol na wdrozenie Debug, gdy nie ma zadnego Release (do debugowania)

param(
    [string]$Campaign = "Woj",
    [switch]$AllowDebug
)

# Zwraca najnowszy istniejacy, niepusty DLL z podanej listy kandydatow (lub $null).
function Find-NewestDll {
    param([string[]]$Candidates)
    $best = $null
    $bestTime = [DateTime]::MinValue
    foreach ($c in $Candidates) {
        if ((Test-Path -LiteralPath $c) -and (Get-Item $c).Length -gt 0) {
            $t = (Get-Item $c).LastWriteTime
            if ($t -gt $bestTime) {
                $best = $c
                $bestTime = $t
            }
        }
    }
    if ($best) { return @{ Path = $best; Time = $bestTime } }
    return $null
}

$CampaignNames = @{
    'Bun' = 'Bunt Wladcow Bestii'
    'Drz' = 'Drzewo Zycia'
    'Mie' = 'Miecz Mrozu'
    'Ogn' = 'Ognisty Ksiezyc'
    'Pod' = 'Podboj Podziemi'
    'Sza' = 'Szarza Smokow'
    'Wla' = 'Wladcy Zywiolow'
    'Woj' = 'Wojownicy Pustkowi'
}

function Deploy-OneCampaign {
    param([string]$Code)

    $pluginRoot = 'F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin'
    $codeLower  = $Code.ToLower()
    $isLegacy   = ($Code -eq 'Woj') -and ($Campaign -eq 'Woj')  # wywolanie bez -Campaign = stary tryb

    $srcAudio    = "$pluginRoot\tools\chronicles_voiceover\audio_${codeLower}_campaign"
    $srcTextMap  = "$srcAudio\text_map_with_filter.txt"
    if (!(Test-Path -LiteralPath $srcTextMap)) {
        $srcTextMap = "$srcAudio\text_map.txt"   # fallback: brak filtra mapy (patrz build_text_map.py)
    }

    if (!(Test-Path -LiteralPath $srcAudio)) {
        Write-Host "POMINIETO ${Code}: brak folderu audio $srcAudio"
        return
    }

    # Wybierz DLL: NAJNOWSZY z grupy Release, jesli taki istnieje. Debug tylko jako
    # jawny fallback (-AllowDebug) - nigdy nie wygrywa z Release samym timestampem.
    $releaseCandidates = @(
        "$pluginRoot\build\bin\Release\H3ButtonPlugin.dll",
        "$pluginRoot\cmake-build-release\bin\H3ButtonPlugin.dll"
    )
    $debugCandidates = @(
        "$pluginRoot\build\bin\Debug\H3ButtonPlugin.dll",
        "$pluginRoot\cmake-build-debug\bin\H3ButtonPlugin.dll"
    )

    $srcDll = $null
    $srcDllTime = $null
    $srcKind = $null
    $releasePick = Find-NewestDll -Candidates $releaseCandidates
    if ($releasePick) {
        $srcDll = $releasePick.Path
        $srcDllTime = $releasePick.Time
        $srcKind = 'Release'
    } else {
        $debugPick = Find-NewestDll -Candidates $debugCandidates
        if ($debugPick -and $AllowDebug) {
            $srcDll = $debugPick.Path
            $srcDllTime = $debugPick.Time
            $srcKind = 'Debug'
            Write-Host "OSTRZEZENIE: brak jakiegokolwiek builda Release - wdrazam Debug ($srcDll) bo podano -AllowDebug." -ForegroundColor Yellow
            Write-Host "OSTRZEZENIE: build Debug zwykle NIE laduje sie w realnej grze (brak debugowego CRT poza srodowiskiem dev)." -ForegroundColor Yellow
        } elseif ($debugPick) {
            Write-Host "BLAD: Nie znaleziono zadnego builda Release, a jest dostepny tylko Debug ($($debugPick.Path))." -ForegroundColor Red
            Write-Host "Build Debug zwykle NIE laduje sie w realnej grze (brak debugowego CRT). Zbuduj Release (cmake --build --config Release)," -ForegroundColor Red
            Write-Host "albo swiadomie uzyj '.\deploy.ps1 -AllowDebug' zeby mimo to wdrozyc Debug (np. do debugowania z dolaczonym debuggerem)." -ForegroundColor Red
            return
        }
    }

    if (!$srcDll) {
        Write-Host "BLAD: Nie znaleziono zadnego poprawnego H3ButtonPlugin.dll (ani Release, ani Debug)!"
        Write-Host "Zbuduj projekt najpierw (cmake --build)."
        return
    }

    $dstDllName  = 'H3ButtonPlugin.dll'
    $folderName  = if ($isLegacy) { 'TextDetector' } else { "TextDetector - $($CampaignNames[$Code])" }
    $mp3Filter   = "${codeLower}_*.mp3"

    Write-Host "=== ${Code}: $folderName (DLL: $dstDllName) ==="
    Write-Host "Zrodlo DLL [$srcKind]: $srcDll ($($srcDllTime.ToString('HH:mm:ss')))"

    $parentDir = 'F:\gry\h3-Chro-Hdmod(modowanie)'
    $hommDirs = Get-ChildItem -LiteralPath $parentDir -Directory | Where-Object { $_.Name -like 'HoMM*' }

    $deployed = $false
    foreach ($d in $hommDirs) {
        $packsDir = Join-Path $d.FullName '_HD3_Data\Packs'
        if (!(Test-Path -LiteralPath $packsDir)) { continue }

        $targetDir = Join-Path $packsDir $folderName
        $legacyDir = Join-Path $packsDir 'TextDetector'
        if (!(Test-Path -LiteralPath $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir | Out-Null
        }

        # 0. Usun przemianowane DLL-e po starej wersji tego skryptu (H3ButtonPlugin_<kod>.dll) -
        #    obok H3ButtonPlugin.dll HD zaladowalby oba naraz, a sama przemianowana kopia
        #    i tak psuje wtyczke (patrz naglowek).
        Get-ChildItem -LiteralPath $targetDir -Filter 'H3ButtonPlugin_*.dll' -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
                Write-Host "  OK: usunieto stary przemianowany DLL $($_.Name)"
            } catch {
                Write-Host "  BLAD: nie udalo sie usunac $($_.Name): $($_.Exception.Message) (zamknij gre i sprobuj ponownie)"
            }
        }

        # 1. Kopiuj DLL (zawsze jako H3ButtonPlugin.dll)
        $dstDll = Join-Path $targetDir $dstDllName
        try {
            Copy-Item $srcDll $dstDll -Force -ErrorAction Stop
            Write-Host "  OK: DLL -> $dstDll"
            $deployed = $true
        } catch {
            Write-Host "  BLAD DLL: $($_.Exception.Message) (zamknij gre i sprobuj ponownie)"
        }

        # 2. Zasoby statyczne (TD.lod, H3.LodTable.dll) - nie ma ich w repo, kopiujemy
        #    z juz istniejacego legacy folderu TextDetector\ jako zrodla referencyjnego
        foreach ($asset in @('TD.lod', 'H3.LodTable.dll')) {
            $dstAsset = Join-Path $targetDir $asset
            if (!(Test-Path -LiteralPath $dstAsset)) {
                $legacyAsset = Join-Path $legacyDir $asset
                if (Test-Path -LiteralPath $legacyAsset) {
                    Copy-Item $legacyAsset $dstAsset -Force
                    Write-Host "  OK: $asset -> $dstAsset (skopiowano z $legacyDir)"
                } else {
                    Write-Host "  UWAGA: brak $asset - ani w $targetDir, ani w $legacyDir. Wtyczka moze nie dzialac bez tego pliku."
                }
            }
        }

        # 3. Kopiuj text_map.txt
        if (Test-Path -LiteralPath $srcTextMap) {
            $dstTextMap = Join-Path $targetDir 'text_map.txt'
            Copy-Item $srcTextMap $dstTextMap -Force
            Write-Host "  OK: text_map.txt -> $dstTextMap (zrodlo: $(Split-Path $srcTextMap -Leaf))"
        } else {
            Write-Host "  UWAGA: Brak $srcTextMap"
        }

        # 4. Kopiuj pliki audio do podkatalogu audio\
        $audioTargetDir = Join-Path $targetDir 'audio'
        if (!(Test-Path -LiteralPath $audioTargetDir)) {
            New-Item -ItemType Directory -Path $audioTargetDir | Out-Null
        }
        $mp3Files = Get-ChildItem -LiteralPath $srcAudio -Filter $mp3Filter -ErrorAction SilentlyContinue
        if ($mp3Files) {
            foreach ($mp3 in $mp3Files) {
                Copy-Item $mp3.FullName (Join-Path $audioTargetDir $mp3.Name) -Force
            }
            Write-Host "  OK: $($mp3Files.Count) plikow audio -> $audioTargetDir"
        } else {
            Write-Host "  UWAGA: Brak plikow $mp3Filter w $srcAudio"
        }
    }

    if (!$deployed) {
        Write-Host "UWAGA: Nie znaleziono zadnego folderu z _HD3_Data\Packs!"
    }
}

if ($Campaign -eq 'All') {
    foreach ($code in $CampaignNames.Keys) {
        Deploy-OneCampaign -Code $code
    }
} else {
    if (!$CampaignNames.ContainsKey($Campaign)) {
        Write-Host "Nieznany kod kampanii: $Campaign. Oczekiwano jednego z: $($CampaignNames.Keys -join ', ') lub All"
        exit 1
    }
    Deploy-OneCampaign -Code $Campaign
}
