$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

Push-Location (Join-Path $Root "backend")
try {
    Invoke-NativeStep "backend pytest" { & $PythonBin -m pytest -p no:cacheprovider }
    Invoke-NativeStep "backend ruff" { & $PythonBin -m ruff check . }
}
finally {
    Pop-Location
}

Invoke-NativeStep "frontend container checks" { & (Join-Path $PSScriptRoot "frontend-check.ps1") }
