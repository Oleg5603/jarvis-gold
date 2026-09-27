#requires -Version 5.1
[CmdletBinding()]
param()

$guardian = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'Guardian.ps1'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    $arguments = '-NoProfile -ExecutionPolicy Bypass -STA -File "{0}"' -f $guardian
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments -WindowStyle Hidden
    return
}

& $guardian
