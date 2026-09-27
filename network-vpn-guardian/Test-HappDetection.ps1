param([string]$Root = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $Root 'Guardian.AppProtection.psm1') -Force
$module = Get-Module Guardian.AppProtection
& $module {
    function Get-NetAdapter { [pscustomobject]@{Name='happ-default-tun';InterfaceDescription='Tunnel';Status='Up';ifIndex=7} }
    function Get-NetRoute {
        [pscustomobject]@{State='Alive';RouteMetric=1;InterfaceMetric=90;InterfaceIndex=2;InterfaceAlias='Ethernet'}
        [pscustomobject]@{State='Alive';RouteMetric=2;InterfaceMetric=5;InterfaceIndex=7;InterfaceAlias='happ-default-tun'}
    }
    function Get-Process { [pscustomobject]@{Id=1} }
    $config = [pscustomobject]@{happAdapterPatterns=@('happ-tun')}
    if (-not (Get-HappProtectionState $config).Protected) { throw 'FAIL: current Happ interface and combined metric' }
    function Get-NetAdapter { @() }
    if ((Get-HappProtectionState $config).Protected) { throw 'FAIL: missing adapter' }
    function Get-NetAdapter { throw 'Access denied' }
    $denied = $false
    try { Get-HappProtectionState $config | Out-Null } catch { $denied=$true }
    if (-not $denied) { throw 'FAIL: denied query must not masquerade as disconnected' }
}
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $Root 'Guardian.ps1'),[ref]$tokens,[ref]$errors)
if (@($errors).Count) { throw 'Guardian parse failed' }
foreach ($name in @('Get-GuardianSnapshot')) {
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    Invoke-Expression $node.Extent.Text
}
function Get-NetAdapter { [pscustomobject]@{Name='happ-default-tun';InterfaceDescription='Tunnel';Status='Up';HardwareInterface=$false} }
function Get-DefaultRoute { [pscustomobject]@{InterfaceAlias='happ-default-tun';NextHop='10.0.0.1'} }
function Get-NetIPAddress { [pscustomobject]@{IPAddress='10.0.0.2'} }
function Get-DnsClientServerAddress { [pscustomobject]@{ServerAddresses=@('1.1.1.1')} }
function Measure-Link { [pscustomobject]@{Loss=100;Avg=0;Jitter=0} }
function Get-PublicIp { '203.0.113.1' }
$config=[pscustomobject]@{vpnInterfacePatterns=@('tun');targetHost='1.1.1.1';expectedVpnPublicIp=''}
$snapshot=Get-GuardianSnapshot $config
if ($snapshot.Internet -ne 'ONLINE' -or $snapshot.Loss -ne 'N/A (ICMP)') { throw 'FAIL: HTTPS with blocked ICMP' }
function Get-PublicIp { '' }
if ((Get-GuardianSnapshot $config).Internet -ne 'UNVERIFIED') { throw 'FAIL: uncertain probes' }
'PASS: 5 regression scenarios; Guardian syntax valid'
