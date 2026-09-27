#requires -Version 5.1
[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw 'Запустите Emergency-Recovery.ps1 от имени администратора.' }

$groups = @('Network VPN Guardian', 'Network VPN Guardian - ChatGPT')
$rules = @($groups | ForEach-Object { Get-NetFirewallRule -Group $_ -ErrorAction SilentlyContinue })
$appDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$protectionState=Join-Path $appDir 'data\protection-state.json'
if ($rules.Count -eq 0 -and -not (Test-Path -LiteralPath $protectionState)) { Write-Host 'Активная защита Network VPN Guardian не найдена. Сеть не изменялась.'; return }

$approved = $Force -or $PSCmdlet.ShouldProcess("$($rules.Count) firewall rule(s)", 'Remove Guardian emergency blocks')
if ($approved) {
    $rules | Remove-NetFirewallRule
    if(Test-Path -LiteralPath $protectionState){
        Import-Module (Join-Path $appDir 'Guardian.Core.psm1') -Force
        Disable-CoreKillSwitch $protectionState | Out-Null
    }
    Clear-DnsClientCache -ErrorAction SilentlyContinue
    Write-Host 'Маршруты и блокировки Guardian восстановлены. DNS-кэш очищен.' -ForegroundColor Green
}
