# run_demo.ps1 — launch the F4D portal and expose it via a Cloudflare quick tunnel.
#
#   Right-click > Run with PowerShell, or from a terminal:  .\run_demo.ps1
#
# Prints a public https://<random>.trycloudflare.com URL anyone can open while
# this window stays running. Press Ctrl+C to stop; the app is shut down too.
#
# Notes:
#   * The URL changes every run (it's a free quick tunnel, no account needed).
#   * Demo data only. Demo login: ttl_demo / demo123
#   * For a stable URL + email login wall, ask about the "named tunnel + Access" upgrade.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    Write-Host "cloudflared not found. Install it with:  winget install --id Cloudflare.cloudflared" -ForegroundColor Red
    exit 1
}

Write-Host "Starting the F4D app on http://localhost:8501 ..." -ForegroundColor Cyan
$app = Start-Process -FilePath ".\venv\Scripts\python.exe" `
    -ArgumentList @(
        "-m","streamlit","run","main.py",
        "--server.headless","true","--server.port","8501",
        "--server.enableCORS","false","--server.enableXsrfProtection","false",
        "--browser.gatherUsageStats","false"
    ) -PassThru -WindowStyle Minimized

try {
    # Wait for the app to report healthy before opening the tunnel.
    $up = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $up = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $up) { throw "App did not become healthy on port 8501 — check that the venv and seed data are set up." }

    Write-Host "App is up. Opening public tunnel (your shareable URL appears below)..." -ForegroundColor Green
    Write-Host "Demo login:  ttl_demo / demo123" -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to stop.`n" -ForegroundColor DarkGray

    # Foreground: cloudflared prints the trycloudflare.com URL in its banner.
    & $cloudflared tunnel --url http://localhost:8501
}
finally {
    Write-Host "`nShutting down the app..." -ForegroundColor Cyan
    if ($app -and -not $app.HasExited) { Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue }
}
