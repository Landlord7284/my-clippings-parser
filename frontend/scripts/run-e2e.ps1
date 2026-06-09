$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$vite = Join-Path $root "node_modules/vite/bin/vite.js"
$server = Start-Process -FilePath "node.exe" `
  -ArgumentList @($vite, "--host", "127.0.0.1", "--port", "5173", "--strictPort") `
  -WorkingDirectory $root `
  -WindowStyle Hidden `
  -PassThru

try {
  $ready = $false
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $response = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 1
      if ($response.StatusCode -eq 200) {
        $ready = $true
        break
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }

  if (-not $ready) {
    throw "Vite dev server did not become ready."
  }

  & npx.cmd playwright test
  exit $LASTEXITCODE
} finally {
  if ($server -and -not $server.HasExited) {
    Stop-Process -Id $server.Id -Force
  }
}
