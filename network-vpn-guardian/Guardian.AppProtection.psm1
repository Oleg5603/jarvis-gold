#requires -Version 5.1
Set-StrictMode -Version 2

function Test-GuardianAdministrator {
    return ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-HappProtectionState($Config) {
    $patterns = @(@('happ-tun','happ-default-tun') + @($Config.happAdapterPatterns) | Where-Object { $_ } | ForEach-Object { [regex]::Escape([string]$_) }) -join '|'
    $adapters = @(Get-NetAdapter -ErrorAction Stop | Where-Object {
        $_.Status -eq 'Up' -and ($_.Name -match $patterns -or $_.InterfaceDescription -match $patterns)
    })
    $route = @(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
        Where-Object State -ne 'Unreachable' | Sort-Object @{Expression={ [long]$_.RouteMetric + [long]$_.InterfaceMetric }} | Select-Object -First 1)
    # An empty adapter list has no .ifIndex property; keep the monitor alive
    # during the short interval while Happ recreates its virtual adapter.
    $adapterIndexes = @($adapters | ForEach-Object { $_.ifIndex })
    $routeViaHapp = [bool]($route -and ($adapterIndexes -contains $route.InterfaceIndex))
    $process = @(Get-Process -Name 'Happ' -ErrorAction SilentlyContinue)
    [pscustomobject]@{
        AdapterUp = ($adapters.Count -gt 0)
        RouteViaHapp = $routeViaHapp
        Protected = [bool]($adapters.Count -gt 0 -and $routeViaHapp)
        ProcessRunning = ($process.Count -gt 0)
        # A transiently empty adapter list has no .Name property in PowerShell.
        # Keep reconnect monitoring alive while Happ recreates its adapter.
        AdapterNames = @($adapters | ForEach-Object { $_.Name })
        DefaultRoute = if ($route) { $route.InterfaceAlias } else { '' }
    }
}

function Start-HappClient($Config) {
    $path = [Environment]::ExpandEnvironmentVariables([string]$Config.happExecutablePath)
    if (-not (Test-Path -LiteralPath $path)) { throw "Happ не найден: $path" }
    Start-Process -FilePath $path -ArgumentList 'happ://disconnect' -WorkingDirectory (Split-Path -Parent $path) -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
    Start-Process -FilePath $path -ArgumentList 'happ://connect' -WorkingDirectory (Split-Path -Parent $path) -WindowStyle Hidden | Out-Null
    return $true
}

function Start-GuardianPsiphon($Config) {
    $path = [Environment]::ExpandEnvironmentVariables([string]$Config.psiphonExecutablePath)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Psiphon executable not found' }
    if (@(Get-Process -Name psiphon3 -ErrorAction SilentlyContinue).Count -eq 0) {
        Start-Process -FilePath $path -WorkingDirectory (Split-Path -Parent $path) -WindowStyle Hidden | Out-Null
    }
}

function Get-GuardianPsiphonState {
    # A running process is never evidence of a system-wide protected route.
    $result = [pscustomobject]@{ Status='STOPPED'; ProxyHealthy=$false; Protected=$false }
    if (@(Get-Process -Name psiphon3 -ErrorAction SilentlyContinue).Count -eq 0) { return $result }
    $result.Status = 'RUNNING / UNVERIFIED'
    try {
        $settings = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction Stop
        if ($settings.ProxyEnable -ne 1) { return $result }
        $proxyText = [string]$settings.ProxyServer
        $match = [regex]::Match($proxyText, '(?:^|;)(?:https?=)?(127\.0\.0\.1|localhost):(\d+)(?:;|$)')
        if (-not $match.Success) { return $result }
        $port = [int]$match.Groups[2].Value
        $owners = @(Get-Process -Name psiphon3,psiphon-tunnel-core -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop | Where-Object { $_.OwningProcess -in $owners })
        if (-not $listeners.Count) { return $result }
        $request = [System.Net.WebRequest]::Create('https://www.microsoft.com/')
        $request.Proxy = [System.Net.WebProxy]::new(('http://127.0.0.1:' + $port))
        $request.Timeout = 2500
        $request.ReadWriteTimeout = 2500
        $response = $request.GetResponse()
        try { $result.ProxyHealthy = ([int]$response.StatusCode -eq 200) } finally { $response.Close() }
        if ($result.ProxyHealthy) { $result.Status = 'PROXY OK / NOT SYSTEM VPN' }
    } catch { $result.Status = 'PROXY UNVERIFIED' }
    return $result
}

function Resolve-ChatGptExecutablePaths($Config) {
    $paths = New-Object Collections.Generic.List[string]
    foreach ($configured in (@($Config.chatGptExecutablePaths) + @($Config.claudeExecutablePaths))) {
        $expanded = [Environment]::ExpandEnvironmentVariables([string]$configured)
        if ($expanded -and (Test-Path -LiteralPath $expanded)) { $paths.Add($expanded) }
    }
    foreach ($candidate in @('C:\Users\HP\AppData\Local\AnthropicClaude\Claude.exe')) {
        if (Test-Path -LiteralPath $candidate) { $paths.Add($candidate) }
    }
    foreach ($process in @(Get-Process -Name 'ChatGPT','Claude' -ErrorAction SilentlyContinue)) {
        try { if ($process.Path -and (Test-Path -LiteralPath $process.Path)) { $paths.Add($process.Path) } } catch {}
    }
    try {
        $package = Get-AppxPackage -Name 'OpenAI.Codex' -ErrorAction Stop | Select-Object -First 1
        if ($package) {
            $candidate = Join-Path $package.InstallLocation 'app\ChatGPT.exe'
            if (Test-Path -LiteralPath $candidate) { $paths.Add($candidate) }
        }
    } catch {}
    return @($paths | Select-Object -Unique)
}

function Test-ChatGptBlock($Config) {
    $paths = @(Resolve-ChatGptExecutablePaths $Config)
    if (-not $paths.Count) { return $false }
    $rules = @(Get-NetFirewallRule -Group ([string]$Config.chatGptFirewallGroup) -ErrorAction SilentlyContinue |
        Where-Object { $_.Enabled -eq 'True' -and $_.Action -eq 'Block' })
    if (-not $rules.Count) { return $false }
    foreach ($path in $paths) {
        $pathRules = @($rules | Where-Object {
            $filter = $_ | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue
            $filter -and $filter.Program -eq $path
        })
        if (-not ($pathRules.Direction -contains 'Inbound' -and $pathRules.Direction -contains 'Outbound')) {
            return $false
        }
    }
    return $true
}

function Enable-ChatGptBlock {
    [CmdletBinding(SupportsShouldProcess=$true)]
    param($Config)
    $paths = @(Resolve-ChatGptExecutablePaths $Config)
    if (-not $paths.Count) { throw 'Не найдены исполняемые файлы ChatGPT или Claude; защитные правила не созданы.' }
    $group = [string]$Config.chatGptFirewallGroup
    if (-not $PSCmdlet.ShouldProcess(($paths -join ', '), 'Создать блокирующие правила ChatGPT и Claude')) { return $paths }
    if (-not (Test-GuardianAdministrator)) { throw 'Для автоматической блокировки ChatGPT и Claude запустите Guardian от имени администратора.' }
    Get-NetFirewallRule -Group $group -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    try {
        $index = 0
        foreach ($path in $paths) {
            $index++
            New-NetFirewallRule -DisplayName "Guardian - Block AI client outbound $index" -Group $group `
                -Direction Outbound -Action Block -Program $path -Profile Any -Enabled True -ErrorAction Stop | Out-Null
            New-NetFirewallRule -DisplayName "Guardian - Block AI client inbound $index" -Group $group `
                -Direction Inbound -Action Block -Program $path -Profile Any -Enabled True -ErrorAction Stop | Out-Null
        }
    } catch {
        Get-NetFirewallRule -Group $group -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
        throw
    }
    return $paths
}

function Disable-ChatGptBlock {
    [CmdletBinding(SupportsShouldProcess=$true)]
    param($Config)
    if (-not $PSCmdlet.ShouldProcess(([string]$Config.chatGptFirewallGroup), 'Удалить блокирующие правила ChatGPT')) { return $true }
    if (-not (Test-GuardianAdministrator)) { throw 'Для снятия блокировки ChatGPT запустите Guardian от имени администратора.' }
    Get-NetFirewallRule -Group ([string]$Config.chatGptFirewallGroup) -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule -ErrorAction Stop
    return $true
}

Export-ModuleMember -Function Test-GuardianAdministrator,Get-HappProtectionState,Start-HappClient,Start-GuardianPsiphon,Get-GuardianPsiphonState,Resolve-ChatGptExecutablePaths,Test-ChatGptBlock,Enable-ChatGptBlock,Disable-ChatGptBlock
