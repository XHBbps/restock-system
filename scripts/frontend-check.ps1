$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"
$DockerBin = if ($env:DOCKER_BIN) { $env:DOCKER_BIN } else { "docker" }

function Get-LocalNodeVersion {
    try {
        $version = (& cmd.exe /c "node -v" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $version) {
            return ($version | Select-Object -First 1).Trim()
        }
    }
    catch {
        return $null
    }

    return $null
}

if (-not (Get-Command $DockerBin -ErrorAction SilentlyContinue)) {
    throw "Docker is required for frontend checks. Please install and start Docker."
}

& $DockerBin info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running or this session cannot access the Docker engine."
}

$localNodeVersion = Get-LocalNodeVersion
if ($localNodeVersion) {
    Write-Host "Detected local Node $localNodeVersion. Frontend checks will run in Docker Node 20."
}
else {
    Write-Host "No local Node detected. Frontend checks will run in Docker Node 20."
}

$frontendPath = (Resolve-Path $FrontendDir).Path

& $DockerBin run --rm `
    -e CI=1 `
    -v "${frontendPath}:/app" `
    -v "restock-frontend-check-node-modules:/app/node_modules" `
    -v "restock-frontend-check-npm-cache:/root/.npm" `
    -w /app `
    node:20-alpine `
    sh -lc "npm ci && npm run build && npm run test:coverage"

if ($LASTEXITCODE -ne 0) {
    throw "Frontend container checks failed with exit code $LASTEXITCODE"
}
