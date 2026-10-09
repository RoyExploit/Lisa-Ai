Write-Host "Building Lisa AI Application..." -ForegroundColor Cyan
.\.venv\Scripts\pyinstaller.exe installer\LisaAI.spec --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build main application!" -ForegroundColor Red
    exit 1
}

Write-Host "Main Application built successfully. Now building Setup Wizard..." -ForegroundColor Cyan
.\.venv\Scripts\pyinstaller.exe installer\LisaAI_Setup.spec --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build setup wizard!" -ForegroundColor Red
    exit 1
}

Write-Host "Build complete! Setup is located in dist\LisaAI_Setup.exe" -ForegroundColor Green
