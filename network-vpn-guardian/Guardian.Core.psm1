#requires -Version 5.1
Set-StrictMode -Version 2

function Get-CoreDefaultRoute {
    @(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Where-Object State -ne 'Unreachable' | Sort-Object RouteMetric,InterfaceMetric)[0]
}

function Get-CorePublicIp {
    try {
        $request=[Net.WebRequest]::Create('https://api.ipify.org'); $request.Timeout=3000
        $response=$request.GetResponse(); $reader=New-Object IO.StreamReader($response.GetResponseStream())
        $ip=$reader.ReadToEnd().Trim(); $reader.Dispose();$response.Dispose(); $ip
    } catch { '' }
}

function Find-VpnInterface($Config) {
    $patterns=@($Config.vpnInterfacePatterns | ForEach-Object {[regex]::Escape([string]$_)}) -join '|'
    @(Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object {
        $_.Status -eq 'Up' -and ($_.Name -match $patterns -or $_.InterfaceDescription -match $patterns)
    } | Sort-Object InterfaceMetric | Select-Object -First 1)
}

function Test-CoreEndpoints([string[]]$Targets) {
    $passed=0; $results=@()
    foreach($target in @($Targets)) {
        try {$ok=Test-Connection -ComputerName $target -Count 1 -Quiet -ErrorAction Stop}catch{$ok=$false}
        if($ok){$passed++}; $results += [pscustomobject]@{Target=$target;Passed=[bool]$ok}
    }
    [pscustomobject]@{Passed=$passed;Total=@($Targets).Count;Quorum=($passed -ge [math]::Max(1,[math]::Ceiling(@($Targets).Count/2)));Results=$results}
}

function Get-DnsLeakStatus($VpnAdapter,$Config) {
    $all=@(Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {$_.ServerAddresses.Count})
    $vpnDns=@($all | Where-Object InterfaceIndex -eq $VpnAdapter.ifIndex | ForEach-Object ServerAddresses | Select-Object -Unique)
    $otherDns=@($all | Where-Object InterfaceIndex -ne $VpnAdapter.ifIndex | ForEach-Object ServerAddresses | Select-Object -Unique)
    $expected=@($Config.expectedVpnDns)
    $outside=@()
    if($expected.Count){$outside=@($vpnDns | Where-Object {$_ -notin $expected})}
    [pscustomobject]@{
        Status=if(-not $VpnAdapter){'UNVERIFIED'}elseif(-not $vpnDns.Count){'UNVERIFIED'}elseif($outside.Count){'LEAK'}else{'OK'}
        VpnDns=$vpnDns; OtherInterfaceDns=$otherDns; Unexpected=$outside
    }
}

function Read-CoreState([string]$Path) {
    if(Test-Path -LiteralPath $Path){
        try {return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop)}catch{}
    }
    return [pscustomobject]@{LastState='UNKNOWN';DirectPublicIp='';VpnPublicIp='';VpnCandidateIp='';VpnCandidateCount=0;LostCount=0;HungCount=0;ReconnectAttempts=0;CooldownUntil='';LastKnownGood=$null}
}

function Save-CoreState($State,[string]$Path) {
    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Get-GuardianCoreSnapshot($Config,$State) {
    $vpn=Find-VpnInterface $Config
    $route=Get-CoreDefaultRoute
    $publicIp=Get-CorePublicIp
    $probes=Test-CoreEndpoints @($Config.probeTargets)
    $routeViaVpn=[bool]($vpn -and $route -and $route.InterfaceIndex -eq $vpn.ifIndex)
    $dns=if($vpn){Get-DnsLeakStatus $vpn $Config}else{[pscustomobject]@{Status='UNVERIFIED';VpnDns=@();OtherInterfaceDns=@();Unexpected=@()}}
    $expectedVpnIp=if($Config.expectedVpnPublicIp){[string]$Config.expectedVpnPublicIp}elseif($State.VpnPublicIp){[string]$State.VpnPublicIp}else{''}
    $ipOk=[bool]($expectedVpnIp -and $publicIp -eq $expectedVpnIp)
    $leak=[bool]($expectedVpnIp -and $publicIp -and $publicIp -ne $expectedVpnIp)
    $controlOk=[bool]($vpn -and $routeViaVpn)
    $dataOk=[bool]($publicIp -and $probes.Quorum -and $ipOk -and $dns.Status -eq 'OK')
    $lost=[bool](($State.LastState -eq 'PROTECTED' -or [int]$State.LostCount -gt 0) -and (-not $vpn -or -not $routeViaVpn))
    $hung=[bool]($vpn -and (-not $routeViaVpn -or -not $probes.Quorum -or -not $publicIp))
    $state=if($leak){'LOCKDOWN'}elseif(-not $vpn){'DIRECT'}elseif($controlOk -and $dataOk){'PROTECTED'}elseif($hung){'DEGRADED'}else{'VPN_VERIFICATION'}
    [pscustomobject]@{
        Time=Get-Date;State=$state;VpnLost=$lost;VpnHung=$hung;VpnInterface=if($vpn){$vpn.Name}else{''}
        DefaultRouteInterface=if($route){$route.InterfaceAlias}else{''};Gateway=if($route){$route.NextHop}else{''}
        PublicIp=$publicIp;ExpectedVpnIp=$expectedVpnIp;IpVerified=$ipOk;IpLeak=$leak
        Dns=$dns;Probes=$probes;ControlPlaneOk=$controlOk;DataPlaneOk=$dataOk
    }
}

function Get-IncidentClassification($Snapshot,$State,$Config) {
    $reason='';$severity='';$confirmed=$false
    if($Snapshot.IpLeak){$reason='PUBLIC_IP_CHANGED';$severity='CRITICAL';$confirmed=$true}
    elseif($Snapshot.VpnLost){$reason='VPN_ROUTE_LOST';$severity='CRITICAL';$confirmed=([int]$State.LostCount -ge [int]$Config.lostConfirmationCount)}
    elseif($Snapshot.VpnHung){$reason='VPN_HUNG';$severity='CRITICAL';$confirmed=([int]$State.HungCount -ge [int]$Config.hungConfirmationCount)}
    [pscustomobject]@{Reason=$reason;Severity=$severity;Confirmed=$confirmed;RequiresProtection=($severity -eq 'CRITICAL' -and $confirmed)}
}

function Invoke-VpnReconnect($Config) {
    if($Config.vpnReconnectCommand) {
        & powershell.exe -NoProfile -Command ([string]$Config.vpnReconnectCommand)
        return ($LASTEXITCODE -eq 0)
    }
    if($Config.vpnConnectionName) {
        & rasdial.exe ([string]$Config.vpnConnectionName) /disconnect | Out-Null
        & rasdial.exe ([string]$Config.vpnConnectionName) | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    return $false
}

function Write-CoreEvent([string]$Path,[string]$Type,[string]$Severity,[string]$Message,$Data) {
    [ordered]@{Time=(Get-Date).ToString('o');Type=$Type;Severity=$Severity;Message=$Message;Data=$Data} |
        ConvertTo-Json -Compress -Depth 8 | Add-Content -LiteralPath $Path -Encoding UTF8
}

function Enable-CoreKillSwitch($Config,[string]$ProtectionStatePath) {
    if(-not @($Config.vpnServerIps).Count){throw 'vpnServerIps is empty; recovery whitelist cannot be created safely.'}
    $vpn=Find-VpnInterface $Config
    $routes=@(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
        Where-Object {-not $vpn -or $_.InterfaceIndex -ne $vpn.ifIndex})
    if(-not $routes.Count){return $false}
    $saved=@($routes | Select-Object InterfaceIndex,NextHop,RouteMetric,InterfaceMetric)
    [pscustomobject]@{EnabledAt=(Get-Date).ToString('o');DefaultRoutes=$saved;Whitelist=@($Config.vpnServerIps)} |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ProtectionStatePath -Encoding UTF8
    foreach($route in $routes){
        foreach($server in @($Config.vpnServerIps)){
            New-NetRoute -DestinationPrefix "$server/32" -InterfaceIndex $route.InterfaceIndex -NextHop $route.NextHop -RouteMetric 1 -PolicyStore ActiveStore -ErrorAction SilentlyContinue | Out-Null
        }
        Remove-NetRoute -DestinationPrefix '0.0.0.0/0' -InterfaceIndex $route.InterfaceIndex -NextHop $route.NextHop -Confirm:$false -ErrorAction Stop
    }
    return $true
}

function Disable-CoreKillSwitch([string]$ProtectionStatePath) {
    if(-not (Test-Path -LiteralPath $ProtectionStatePath)){return $false}
    $saved=Get-Content -LiteralPath $ProtectionStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach($route in @($saved.DefaultRoutes)){
        if(-not (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue)){
            New-NetRoute -DestinationPrefix '0.0.0.0/0' -InterfaceIndex $route.InterfaceIndex -NextHop $route.NextHop -RouteMetric $route.RouteMetric -PolicyStore ActiveStore -ErrorAction Stop | Out-Null
        }
    }
    foreach($server in @($saved.Whitelist)){Get-NetRoute -DestinationPrefix "$server/32" -ErrorAction SilentlyContinue | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue}
    Remove-Item -LiteralPath $ProtectionStatePath -Force
    return $true
}

Export-ModuleMember -Function Get-GuardianCoreSnapshot,Get-IncidentClassification,Invoke-VpnReconnect,Read-CoreState,Save-CoreState,Write-CoreEvent,Enable-CoreKillSwitch,Disable-CoreKillSwitch
