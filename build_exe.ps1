$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot

Write-Host "=== PedeJa Prospector - Build EXE ===" -ForegroundColor Cyan

Set-Location $ProjectDir

if (!(Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "Instalando dependencias..." -ForegroundColor Yellow
& ".\.venv\Scripts\pip.exe" install --upgrade pip -q
& ".\.venv\Scripts\pip.exe" install -r requirements.txt -q

Write-Host "Limpando builds anteriores..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist")  { Remove-Item "dist"  -Recurse -Force }

$icon = "assets\logo.ico"
$addData = "assets;assets"   # inclui logo.svg, logo.ico e municipios.json

Write-Host "Gerando executavel..." -ForegroundColor Yellow
& ".\.venv\Scripts\pyinstaller.exe" `
    --noconfirm `
    --onefile `
    --windowed `
    --name "PedeJaProspector" `
    --icon "$icon" `
    --add-data "$addData" `
    --hidden-import PySide6.QtSvg `
    --hidden-import PySide6.QtSvgWidgets `
    main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "EXE gerado em: dist\PedeJaProspector.exe" -ForegroundColor Green
} else {
    Write-Host "Erro no build (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}
