$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot)
try {
 New-Item -ItemType Directory -Path build -Force | Out-Null
 $clientIdPath = Join-Path (Get-Location) 'build/github-client-id.txt'
 Set-Content -LiteralPath $clientIdPath -Value $env:CODEX_QUOTA_GITHUB_CLIENT_ID -Encoding utf8
 python -m PyInstaller --noconfirm --clean --onefile --windowed --name CodexQuotaResume --icon "$PSScriptRoot/../assets/app-icon.ico" --add-data "$PSScriptRoot/../assets/github-mark.png;." --add-data "$PSScriptRoot/../assets/app-icon.ico;." --add-data "$clientIdPath;." --distpath dist --workpath build --specpath build scripts/app.py
 if ($LASTEXITCODE) { throw 'Application build failed.' }
} finally { Pop-Location }
