$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$NpmBin = if ($env:NPM_BIN) { $env:NPM_BIN } else { "npm" }

Push-Location (Join-Path $Root "backend")
& $PythonBin -m pytest -p no:cacheprovider
& $PythonBin -m ruff check .
Pop-Location

Push-Location (Join-Path $Root "frontend")
& $NpmBin run build
& $NpmBin test
Pop-Location
