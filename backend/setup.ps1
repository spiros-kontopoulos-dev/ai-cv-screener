<#
.SYNOPSIS
Internal cross-platform setup implementation for Windows.

.DESCRIPTION
Creates or updates the repository-root .env file for Gemini, OpenAI, or
deterministic no-key mode. The root setup.ps1 wrapper normally supplies the
required project path.

.PARAMETER ProjectRoot
Absolute or relative path to the repository root containing .env.example.

.PARAMETER Help
Prints this internal command contract without reading or changing files.

.EXAMPLE
.\backend\setup.ps1 -ProjectRoot C:\projects\ai-cv-screener

.EXAMPLE
.\backend\setup.ps1 -Help
#>

# Configure the local answer provider without printing or committing API keys.
# This script creates or updates the repository-root .env file.
[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [switch]$Help
)

if ($Help) {
    Write-Host @'
AI CV Screener setup implementation

Usage:
  .\backend\setup.ps1 -ProjectRoot PATH
  .\backend\setup.ps1 -Help

Valid command combinations:
  -ProjectRoot PATH   Run interactive setup for that repository root.
  -Help               Print this guide and exit without changing anything.

What the command changes:
  Reads PATH\.env.example and creates or updates PATH\.env.
  Stores only the selected provider mode and local provider key.
  Clears keys for providers that are not selected.
  Never prints the entered secret.

Examples:
  .\backend\setup.ps1 -ProjectRoot C:\projects\ai-cv-screener
  .\backend\setup.ps1 -Help
'@
    return
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    throw "-ProjectRoot is required. Run .\backend\setup.ps1 -Help for usage."
}

$ErrorActionPreference = "Stop"
$ExamplePath = Join-Path $ProjectRoot ".env.example"
$EnvironmentPath = Join-Path $ProjectRoot ".env"

# Replace one NAME=value line in .env, or add it when it is missing.
function Set-EnvironmentValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
    )

    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($line in [System.IO.File]::ReadAllLines($EnvironmentPath)) {
        $lines.Add($line)
    }

    $replacement = "$Name=$Value"
    $found = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^$([regex]::Escape($Name))=") {
            $lines[$index] = $replacement
            $found = $true
            break
        }
    }
    if (-not $found) {
        $lines.Add($replacement)
    }

    [System.IO.File]::WriteAllLines(
        $EnvironmentPath,
        $lines,
        [System.Text.UTF8Encoding]::new($false)
    )
}

# Read a key without showing the typed value, then convert it only long enough
# to write it into the local .env file.
function Read-SecretValue {
    param([Parameter(Mandatory = $true)][string]$Prompt)

    $secureValue = Read-Host -Prompt $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

if (-not (Test-Path $ExamplePath)) {
    throw ".env.example was not found at $ExamplePath"
}

if (-not (Test-Path $EnvironmentPath)) {
    Copy-Item -Path $ExamplePath -Destination $EnvironmentPath
    Write-Host "Created .env from .env.example."
}
else {
    Write-Host "Updating the existing local .env file."
}

Write-Host ""
Write-Host "Choose grounded-answer mode:"
Write-Host "  1. Gemini (free-tier option; requires a Google AI Studio key)"
Write-Host "  2. OpenAI (requires an OpenAI API key and available credits)"
Write-Host "  3. Deterministic no-key mode"

# Keep only the selected provider key. This prevents an old key from changing
# provider selection later.
function Clear-ProviderKeys {
    Set-EnvironmentValue -Name "GEMINI_API_KEY" -Value ""
    Set-EnvironmentValue -Name "GOOGLE_API_KEY" -Value ""
    Set-EnvironmentValue -Name "OPENAI_API_KEY" -Value ""
}

$choice = Read-Host "Enter 1, 2, or 3"

switch ($choice) {
    "1" {
        $key = Read-SecretValue "Paste the Gemini API key"
        if ([string]::IsNullOrWhiteSpace($key)) {
            throw "A Gemini API key is required for option 1."
        }
        Clear-ProviderKeys
        Set-EnvironmentValue -Name "CV_GROUNDED_ANSWER_PROVIDER" -Value "gemini"
        Set-EnvironmentValue -Name "GEMINI_API_KEY" -Value $key.Trim()
        $mode = "Gemini"
    }
    "2" {
        $key = Read-SecretValue "Paste the OpenAI API key"
        if ([string]::IsNullOrWhiteSpace($key)) {
            throw "An OpenAI API key is required for option 2."
        }
        Clear-ProviderKeys
        Set-EnvironmentValue -Name "CV_GROUNDED_ANSWER_PROVIDER" -Value "openai"
        Set-EnvironmentValue -Name "OPENAI_API_KEY" -Value $key.Trim()
        $mode = "OpenAI"
    }
    "3" {
        Clear-ProviderKeys
        Set-EnvironmentValue -Name "CV_GROUNDED_ANSWER_PROVIDER" -Value "deterministic"
        $mode = "deterministic no-key"
    }
    default {
        throw "Invalid selection. Run .\setup.ps1 again and choose 1, 2, or 3."
    }
}

Write-Host ""
Write-Host "Local configuration saved for $mode mode."
Write-Host "The .env file is ignored by Git and must never be committed."
Write-Host ""
Write-Host "Next command:"
Write-Host "  docker compose up --build"
