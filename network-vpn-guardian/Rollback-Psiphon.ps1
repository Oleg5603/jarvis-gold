# Close Guardian before running this rollback. Does not change firewall rules.
$ErrorActionPreference = 'Stop'
$backup = Join-Path $PSScriptRoot 'backups\psiphon-20260917-002759'
foreach ($name in @('Guardian.ps1','Guardian.AppProtection.psm1')) {
    if (-not (Test-Path -LiteralPath (Join-Path $backup $name))) { throw "Missing backup: $name" }
}
foreach ($name in @('Guardian.ps1','Guardian.AppProtection.psm1')) {
    Copy-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $PSScriptRoot $name) -Force
}
Write-Output 'Previous Guardian files restored. Open Guardian again.'
