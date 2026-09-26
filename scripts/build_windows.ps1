$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot)
try {
 python -m PyInstaller --noconfirm --clean --onefile --windowed --name CodexQuotaResume --icon "$PSScriptRoot/../assets/app-icon.ico" --add-data "$PSScriptRoot/../assets/app-icon.ico;." --distpath dist --workpath build --specpath build scripts/app.py
 if ($LASTEXITCODE) { throw 'Application build failed.' }
} finally { Pop-Location }
