# run_remaining_campaigns.ps1
#
# Generuje audio dla pozostalych 6 kampanii Chronicles (Drz, Ogn, Mie, Bun, Wla,
# Sza - w kolejnosci od najmniejszej), pomijajac Woj i Pod (juz gotowe).
# generate_campaign_audio.py sam pomija pojedyncze pliki, ktore juz istnieja.
#
# Zaprojektowany do odpalenia jako ODLACZONY proces w tle (patrz komenda
# startowa Start-Process, ktora go uruchamia pod nazwa/PID "chronicles-gen") -
# dziala dalej po zamknieciu okna PowerShell, z ktorego zostal wystartowany.
# Wymaga wczesniej ustawionej zmiennej ELEVENLABS_API_KEY w tej samej sesji,
# z ktorej wywolywany jest Start-Process (proces potomny dziedziczy srodowisko).

$ErrorActionPreference = 'Continue'
$statusFile = Join-Path $PSScriptRoot 'chronicles-gen.status'
$scriptPath = Join-Path $PSScriptRoot 'generate_campaign_audio.py'
$campaigns = @('Drz', 'Ogn', 'Mie', 'Bun', 'Wla', 'Sza')

"START: $(Get-Date -Format o)" | Out-File -FilePath $statusFile -Encoding utf8

foreach ($c in $campaigns) {
    "=== $c START $(Get-Date -Format o) ===" | Add-Content -Path $statusFile -Encoding utf8
    $logFile = Join-Path $PSScriptRoot "$($c.ToLower())_generation.log"
    & py -3 $scriptPath $c *> $logFile
    "=== $c DONE (exit $LASTEXITCODE) $(Get-Date -Format o) ===" | Add-Content -Path $statusFile -Encoding utf8
}

"ALL DONE: $(Get-Date -Format o)" | Add-Content -Path $statusFile -Encoding utf8
