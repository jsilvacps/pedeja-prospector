$ErrorActionPreference = "Stop"

Write-Host "=== PedeJa Prospector - Build Setup ===" -ForegroundColor Cyan

powershell -ExecutionPolicy Bypass -File .\build_exe.ps1

$InnoCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$ISCC = $null
foreach ($candidate in $InnoCandidates) {
    if (Test-Path $candidate) { $ISCC = $candidate; break }
}

if ($null -eq $ISCC) {
    Write-Host "Inno Setup nao encontrado." -ForegroundColor Red
    Write-Host "Instale em: https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
    Write-Host "Mesmo assim, seu EXE ja esta pronto em: dist\PedeJaProspector.exe" -ForegroundColor Green
    exit 0
}

Write-Host "Gerando instalador..." -ForegroundColor Yellow
& $ISCC ".\installer.iss"

Write-Host "Setup gerado na pasta installer_output" -ForegroundColor Green
