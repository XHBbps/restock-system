$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$NpmBin = if ($env:NPM_BIN) { $env:NPM_BIN } else { "npm" }

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

function Invoke-CmdStep {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string]$CommandLine
    )

    $proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $CommandLine" -NoNewWindow -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "$Description failed with exit code $($proc.ExitCode)"
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

Push-Location (Join-Path $Root "frontend")
try {
    Invoke-CmdStep "frontend build" "$NpmBin run build"
    Invoke-CmdStep "frontend test" "$NpmBin test"
}
finally {
    Pop-Location
}
