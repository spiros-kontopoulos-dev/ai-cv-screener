# Small Windows entry point for local setup.
# The real implementation lives in backend/setup.ps1 so it can be tested.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ImplementationPath = Join-Path $ProjectRoot "backend/setup.ps1"

if (-not (Test-Path $ImplementationPath)) {
    throw "Setup implementation was not found at $ImplementationPath"
}

& $ImplementationPath -ProjectRoot $ProjectRoot
