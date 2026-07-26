<#
.SYNOPSIS
Configures the local AI CV Screener answer provider.

.DESCRIPTION
Runs the interactive setup assistant for Windows. It creates or updates the
repository-root .env file, lets you choose Gemini, OpenAI, or deterministic
no-key mode, clears unused provider keys, and never prints the entered secret.

.PARAMETER Help
Prints the command guide without reading or changing any files.

.EXAMPLE
.\setup.ps1

Starts the interactive provider setup.

.EXAMPLE
.\setup.ps1 -Help

Prints the supported command combinations and side effects.
#>

# Small Windows entry point for local setup.
# The real implementation lives in backend/setup.ps1 so it can be tested.
[CmdletBinding()]
param(
    [switch]$Help
)

if ($Help) {
    Write-Host @'
AI CV Screener local setup

Usage:
  .\setup.ps1
  .\setup.ps1 -Help

Valid command combinations:
  No arguments     Start the interactive provider configuration.
  -Help            Print this guide and exit without changing anything.

Interactive choices:
  1                Configure Gemini and save GEMINI_API_KEY locally.
  2                Configure OpenAI and save OPENAI_API_KEY locally.
  3                Configure deterministic no-key answer mode.

What the command changes:
  Creates .env from .env.example when .env does not exist.
  Updates only provider-related values in the existing .env file.
  Clears provider keys that are not used by the selected mode.
  Never prints the entered API key. The local .env file is ignored by Git.

Examples:
  .\setup.ps1
  .\setup.ps1 -Help
'@
    return
}

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ImplementationPath = Join-Path $ProjectRoot "backend/setup.ps1"

if (-not (Test-Path $ImplementationPath)) {
    throw "Setup implementation was not found at $ImplementationPath"
}

& $ImplementationPath -ProjectRoot $ProjectRoot
