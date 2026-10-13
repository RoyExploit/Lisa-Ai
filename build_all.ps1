Write-Host "Building Lisa AI Application..." -ForegroundColor Cyan
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean installer\LisaAI.spec 2> build_stage1.err.log

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build main application! See build_stage1.err.log" -ForegroundColor Red
    exit 1
}

Write-Host "Main Application built successfully. Now building Setup Wizard..." -ForegroundColor Cyan
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean installer\LisaAI_Setup.spec 2> build_stage2.err.log

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build setup wizard!" -ForegroundColor Red
    exit 1
}

Write-Host "Build complete! Setup is located in dist\LisaAI_Setup.exe" -ForegroundColor Green
