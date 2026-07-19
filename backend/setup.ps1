[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
$ExamplePath = Join-Path $ProjectRoot ".env.example"
$EnvironmentPath = Join-Path $ProjectRoot ".env"

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

$choice = Read-Host "Enter 1, 2, or 3"
Set-EnvironmentValue -Name "GEMINI_API_KEY" -Value ""
Set-EnvironmentValue -Name "GOOGLE_API_KEY" -Value ""
Set-EnvironmentValue -Name "OPENAI_API_KEY" -Value ""

switch ($choice) {
    "1" {
        $key = Read-SecretValue "Paste the Gemini API key"
        if ([string]::IsNullOrWhiteSpace($key)) {
            throw "A Gemini API key is required for option 1."
        }
        Set-EnvironmentValue -Name "CV_GROUNDED_ANSWER_PROVIDER" -Value "gemini"
        Set-EnvironmentValue -Name "GEMINI_API_KEY" -Value $key.Trim()
        $mode = "Gemini"
    }
    "2" {
        $key = Read-SecretValue "Paste the OpenAI API key"
        if ([string]::IsNullOrWhiteSpace($key)) {
            throw "An OpenAI API key is required for option 2."
        }
        Set-EnvironmentValue -Name "CV_GROUNDED_ANSWER_PROVIDER" -Value "openai"
        Set-EnvironmentValue -Name "OPENAI_API_KEY" -Value $key.Trim()
        $mode = "OpenAI"
    }
    "3" {
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
