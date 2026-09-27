#requires -Version 5.1
[CmdletBinding()]
param([switch]$SelfTest,[switch]$OverlayTest)

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

try {
    Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class GuardianTaskbarIdentity {
    [DllImport("shell32.dll", SetLastError = true)]
    public static extern int SetCurrentProcessExplicitAppUserModelID(string appId);
}
'@ -ErrorAction SilentlyContinue
    [void][GuardianTaskbarIdentity]::SetCurrentProcessExplicitAppUserModelID('OlegTools.NetworkVpnGuardian')
} catch {}

$script:GuardianMutex = $null
if (-not $SelfTest -and -not $OverlayTest) {
    $createdNew = $false
    $script:GuardianMutex = [System.Threading.Mutex]::new(
        $true,
        'Local\NetworkVpnGuardian',
        [ref]$createdNew
    )
    if (-not $createdNew) {
        return
    }
}

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$IconPath = Join-Path $AppDir 'assets\guardian-center.ico'
$AppProtectionModule = Join-Path $AppDir 'Guardian.AppProtection.psm1'
Import-Module $AppProtectionModule -Force
$ConfigPath = Join-Path $AppDir 'config.json'
$LogDir = Join-Path $AppDir 'logs'
$LogPath = Join-Path $LogDir ('guardian-{0}.jsonl' -f (Get-Date -Format 'yyyy-MM-dd'))
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Read-GuardianConfig {
    $defaults = [ordered]@{
        checkIntervalSeconds = 5; targetHost = '1.1.1.1'; expectedVpnPublicIp = ''
        failClosed = $false; profile = 'Monitor'; recoveryPolicy = 'Balanced'
        maxReconnectAttempts = 3; maxServiceRestarts = 2; maxApplicationRestarts = 2
        maxAdapterRestarts = 1; maxServerSwitches = 3; recoveryTimeoutSeconds = 120
        cooldownSeconds = @(5,15,30,60); probeTargets = @('1.1.1.1','8.8.8.8')
        vpnInterfacePatterns = @('VPN','TAP','TUN','WireGuard','Wintun','OpenVPN','NordLynx')
        happExecutablePath = 'C:\Program Files\FlyFrogLLC\Happ\Happ.exe'
        psiphonFallbackEnabled = $true
        psiphonExecutablePath = 'C:\Users\HP\Desktop\psiphon3.exe'
        happAdapterPatterns = @('happ-tun'); happLostConfirmationCount = 2
        happRestoreConfirmationCount = 2; happLaunchCooldownSeconds = 30
        blockChatGptOnHappLoss = $true; chatGptExecutablePaths = @(); claudeExecutablePaths = @('C:\Users\HP\AppData\Local\AnthropicClaude\Claude.exe')
        chatGptFirewallGroup = 'Network VPN Guardian - ChatGPT'
    }
    try {
        $loaded = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($key in @($defaults.Keys)) { if ($null -ne $loaded.$key) { $defaults[$key] = $loaded.$key } }
    } catch {}
    [pscustomobject]$defaults
}

function Write-GuardianEvent([string]$Level, [string]$Type, [string]$Message, $Data) {
    $entry = [ordered]@{ time=(Get-Date).ToString('o'); level=$Level; type=$Type; message=$Message; data=$Data }
    ($entry | ConvertTo-Json -Compress -Depth 6) | Add-Content -LiteralPath $LogPath -Encoding UTF8
}

function Get-DefaultRoute {
    try {
        Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
            Sort-Object @{Expression={ [long]$_.RouteMetric + [long]$_.InterfaceMetric }} | Select-Object -First 1
    } catch { $null }
}

function Get-PublicIp {
    try {
        $request = [System.Net.WebRequest]::Create('https://api.ipify.org')
        $request.Timeout = 2500
        # Test the system route, not Psiphon's independently working HTTP proxy.
        $request.Proxy = $null
        $request.ReadWriteTimeout = 2500
        $response = $request.GetResponse()
        $reader = New-Object IO.StreamReader($response.GetResponseStream())
        $value = $reader.ReadToEnd().Trim()
        $reader.Dispose(); $response.Dispose()
        $parsedIp = $null
        if ([System.Net.IPAddress]::TryParse($value, [ref]$parsedIp)) { $value } else { '' }
    } catch { '' }
}

function Measure-Link([string]$Target) {
    $times = New-Object Collections.Generic.List[double]
    $ping = New-Object System.Net.NetworkInformation.Ping
    1..4 | ForEach-Object {
        try {
            $reply = $ping.Send($Target, 900)
            if ($reply.Status -eq 'Success') { $times.Add([double]$reply.RoundtripTime) }
        } catch {}
    }
    $ping.Dispose()
    $received = $times.Count
    $loss = [math]::Round((4-$received)/4*100, 1)
    if ($received -eq 0) { return [pscustomobject]@{ Avg=0; Min=0; Max=0; Jitter=0; Loss=$loss } }
    $avg = ($times | Measure-Object -Average).Average
    $jitter = if ($received -gt 1) {
        $diffs = for ($i=1; $i -lt $received; $i++) { [math]::Abs($times[$i]-$times[$i-1]) }
        ($diffs | Measure-Object -Average).Average
    } else { 0 }
    [pscustomobject]@{
        Avg=[math]::Round($avg,1); Min=[math]::Round(($times | Measure-Object -Minimum).Minimum,1)
        Max=[math]::Round(($times | Measure-Object -Maximum).Maximum,1)
        Jitter=[math]::Round($jitter,1); Loss=$loss
    }
}

function Get-GuardianSnapshot($Config) {
    $adapters = @(Get-NetAdapter -ErrorAction SilentlyContinue)
    $up = @($adapters | Where-Object Status -eq 'Up')
    $route = Get-DefaultRoute
    $vpnRegex = (($Config.vpnInterfacePatterns | ForEach-Object {[regex]::Escape($_)}) -join '|')
    $vpn = @($up | Where-Object { $_.Name -match $vpnRegex -or $_.InterfaceDescription -match $vpnRegex })
    $physical = @($up | Where-Object { $_.Name -notmatch $vpnRegex -and $_.HardwareInterface })
    # In PowerShell, an empty array does not expose .Name.  Keep a transient
    # adapter refresh from turning a monitoring sample into a fatal UI error.
    $vpnNames = @($vpn | ForEach-Object { $_.Name })
    $physicalNames = @($physical | ForEach-Object { $_.Name })
    $addresses = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -ne '127.0.0.1' })
    $dns = @(Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {$_.ServerAddresses.Count -gt 0} | ForEach-Object ServerAddresses | Select-Object -Unique)
    $link = Measure-Link $Config.targetHost
    $publicIp = Get-PublicIp
    $internet = if ($publicIp) {'ONLINE'} elseif ($link.Loss -lt 100) {'LIMITED'} else {'UNVERIFIED'}
    $controlPlane = [pscustomobject]@{
        AdapterUp = ($vpn.Count -gt 0)
        RouteViaVpn = [bool]($route -and ($vpnNames -contains $route.InterfaceAlias))
        GatewayPresent = [bool]($route -and $route.NextHop)
    }
    $dataPlane = [pscustomobject]@{
        PublicIpVerified = [bool]$publicIp
        EndpointsReachable = ($link.Loss -lt 100)
        HttpsProbe = [bool]$publicIp
        ExpectedIpConfigured = [bool]$Config.expectedVpnPublicIp
        ExpectedIpMatch = [bool]($Config.expectedVpnPublicIp -and $Config.expectedVpnPublicIp -eq $publicIp)
        DnsConfigured = ($dns.Count -gt 0)
    }
    $vpnState = if ($vpn.Count -gt 0 -and $internet -eq 'ONLINE') {'CONNECTED'} elseif ($vpn.Count -gt 0) {'DEGRADED'} else {'OFF'}
    $leak = [bool]($Config.expectedVpnPublicIp -and $publicIp -and $Config.expectedVpnPublicIp -ne $publicIp)
    $score = 100
    if ($vpnState -eq 'OFF') {$score -= 55}; if ($vpnState -eq 'DEGRADED') {$score -= 35}
    if ($link.Loss -lt 100 -or -not $publicIp) { $score -= [math]::Min(35, $link.Loss) }
    $score -= [math]::Min(15, [math]::Floor($link.Jitter/5))
    if ($link.Avg -gt 150) {$score -= 10}; if ($leak) {$score = [math]::Min($score,20)}
    $score = [math]::Max(0,[math]::Round($score))
    # Deterministic state machine. CONNECTED is deliberately not equivalent to PROTECTED.
    $state = if ($leak) {'LOCKDOWN'}
        elseif ($vpn.Count -eq 0) {'DIRECT'}
        elseif (-not $controlPlane.RouteViaVpn) {'VPN_VERIFICATION'}
        elseif (-not ($dataPlane.PublicIpVerified -and $dataPlane.EndpointsReachable -and $dataPlane.ExpectedIpMatch -and $dataPlane.DnsConfigured)) {'DEGRADED'}
        else {'PROTECTED'}
    $security = $state
    $routeStatus = if($controlPlane.RouteViaVpn){'OK'}elseif($vpn.Count){'DEGRADED'}else{'DIRECT'}
    $leakStatus = if($leak){'LEAK'}elseif($dataPlane.ExpectedIpMatch){'OK'}else{'UNVERIFIED'}
    $dnsStatus = if($dataPlane.DnsConfigured){'OK'}else{'UNVERIFIED'}
    $stability = if ($link.Loss -eq 100) {'N/A'} else { [math]::Max(0,[math]::Round(100 - $link.Loss - [math]::Min(30,$link.Jitter))) }
    [pscustomobject]@{
        Timestamp=Get-Date; Security=$security; Internet=$internet; Vpn=$vpnState; VpnHealth=$score
        PublicIp=if($publicIp){$publicIp}else{'Unavailable'}
        LocalIp=(@($addresses.IPAddress) -join ', '); Gateway=if($route){$route.NextHop}else{'—'}
        Interface=if($route){$route.InterfaceAlias}else{($physicalNames -join ', ')}
        VpnInterface=if($vpnNames.Count){($vpnNames -join ', ')}else{'—'}; Dns=($dns -join ', ')
        Ping=if($link.Loss -eq 100){'N/A'}else{$link.Avg}; Jitter=if($link.Loss -eq 100){'N/A'}else{$link.Jitter}; Loss=if($link.Loss -eq 100){'N/A (ICMP)'}else{$link.Loss}; Leak=$leak; State=$state
        TunnelStatus=if($controlPlane.AdapterUp){'UP'}else{'DOWN'}
        LeakProtection=$leakStatus; DnsStatus=$dnsStatus; RouteStatus=$routeStatus; Stability=$stability
        ControlPlane=$controlPlane; DataPlane=$dataPlane
    }
}

function Set-GuardianKillSwitch([bool]$Enable) {
    $group = 'Network VPN Guardian'
    if ($Enable) {
        if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Для Kill Switch запустите приложение от имени администратора.'
        }
        # Block rules are deliberately explicit and reversible. LAN/DHCP/DNS exceptions must be
        # configured for a production VPN integration before automatic fail-closed activation.
        New-NetFirewallRule -DisplayName 'Guardian - Block outbound while unsafe' -Group $group `
            -Direction Outbound -Action Block -Profile Any -Enabled True -ErrorAction Stop | Out-Null
        Write-GuardianEvent 'CRITICAL' 'kill_switch' 'Kill Switch enabled by user' @{}
    } else {
        Get-NetFirewallRule -Group $group -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction Stop
        Write-GuardianEvent 'INFO' 'kill_switch' 'Kill Switch disabled by user' @{}
    }
}

if ($SelfTest) {
    $testConfig = Read-GuardianConfig
    $snapshot = Get-GuardianSnapshot $testConfig
    if (-not $snapshot -or -not $snapshot.Timestamp) { throw 'Snapshot was not created.' }
    $missingAppProtectionFunctions = @(
        'Get-HappProtectionState','Start-HappClient','Resolve-ChatGptExecutablePaths',
        'Test-ChatGptBlock','Enable-ChatGptBlock','Disable-ChatGptBlock'
    ) | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }
    $checks = [ordered]@{
        ConfigReadable = [bool]$testConfig
        Monitoring = [bool]$snapshot.Timestamp
        StateMachine = @('UNKNOWN','DIRECT','VPN_CONNECTING','VPN_CONNECTED','VPN_VERIFICATION','PROTECTED','DEGRADED','RECOVERING','LOCKDOWN') -contains $snapshot.State
        FirewallCmdlets = @('Get-NetFirewallRule','Get-NetFirewallApplicationFilter','New-NetFirewallRule','Remove-NetFirewallRule') |
            Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) } |
            Measure-Object | Select-Object -ExpandProperty Count
        EmergencyRecovery = Test-Path -LiteralPath (Join-Path $AppDir 'Emergency-Recovery.ps1')
        AppProtectionModule = Test-Path -LiteralPath $AppProtectionModule
        AppProtectionFunctions = ($missingAppProtectionFunctions.Count -eq 0)
        HappLaunchCooldown = ([int]$testConfig.happLaunchCooldownSeconds -gt 0)
        HappExecutable = Test-Path -LiteralPath ([Environment]::ExpandEnvironmentVariables([string]$testConfig.happExecutablePath))
        ChatGptExecutable = (@(Resolve-ChatGptExecutablePaths $testConfig).Count -gt 0)
        ProtectionRulePresent = [bool](Get-NetFirewallRule -Group 'Network VPN Guardian' -ErrorAction SilentlyContinue)
        ChatGptRulePresent = [bool](Get-NetFirewallRule -Group ([string]$testConfig.chatGptFirewallGroup) -ErrorAction SilentlyContinue)
    }
    $checks.FirewallCmdlets = ($checks.FirewallCmdlets -eq 0)
    $required = $checks.ConfigReadable -and $checks.Monitoring -and $checks.StateMachine -and $checks.FirewallCmdlets -and $checks.EmergencyRecovery -and $checks.AppProtectionModule -and $checks.AppProtectionFunctions -and $checks.HappLaunchCooldown -and $checks.HappExecutable -and $checks.ChatGptExecutable
    [pscustomobject]@{ Result=if($required){'PASSED'}else{'FAILED'}; Checks=$checks; Snapshot=$snapshot } | ConvertTo-Json -Depth 7
    return
}

$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="Network &amp; VPN Guardian" Width="1000" Height="720" MinWidth="850" MinHeight="620" Background="#0B1220" Foreground="#E5EDF8" WindowStartupLocation="CenterScreen">
 <Grid Margin="22"><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
  <DockPanel Grid.Row="0" Margin="0,0,0,16"><StackPanel><TextBlock Text="NETWORK &amp; VPN GUARDIAN" FontSize="14" Foreground="#7F91AD"/><TextBlock Text="Локальный центр сетевой безопасности" FontSize="25" FontWeight="SemiBold"/></StackPanel><StackPanel DockPanel.Dock="Right" HorizontalAlignment="Right"><TextBlock Name="LastCheck" Text="Ожидание проверки" Foreground="#7F91AD" HorizontalAlignment="Right"/><TextBlock Name="ProfileText" Text="Профиль: Monitor" FontSize="15" HorizontalAlignment="Right"/></StackPanel></DockPanel>
  <Border Grid.Row="1" Name="StatusCard" Background="#123D33" CornerRadius="12" Padding="22" Margin="0,0,0,16"><StackPanel Orientation="Horizontal"><Ellipse Name="StatusDot" Width="20" Height="20" Fill="#35D07F" Margin="0,0,14,0"/><TextBlock Name="SecurityText" Text="ПРОВЕРКА…" FontSize="25" FontWeight="Bold"/><TextBlock Name="HealthText" Text="" Margin="20,5,0,0" FontSize="16" Foreground="#B7C7D9"/></StackPanel></Border>
  <Grid Grid.Row="2"><Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
   <Border Grid.Column="0" Background="#121D2E" CornerRadius="10" Padding="18" Margin="0,0,8,0"><Grid><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="*"/></Grid.RowDefinitions><TextBlock Text="СОСТОЯНИЕ" Foreground="#7F91AD" FontWeight="Bold"/><Grid Grid.Row="1" Margin="0,12,0,0"><Grid.ColumnDefinitions><ColumnDefinition Width="145"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions><Grid.RowDefinitions><RowDefinition/><RowDefinition/><RowDefinition/><RowDefinition/><RowDefinition/><RowDefinition/><RowDefinition/><RowDefinition/></Grid.RowDefinitions>
    <TextBlock Text="Интернет"/><TextBlock Grid.Column="1" Name="InternetText"/><TextBlock Grid.Row="1" Text="VPN"/><TextBlock Grid.Row="1" Grid.Column="1" Name="VpnText"/><TextBlock Grid.Row="2" Text="Public IP"/><TextBlock Grid.Row="2" Grid.Column="1" Name="PublicIpText"/><TextBlock Grid.Row="3" Text="Local IP"/><TextBlock Grid.Row="3" Grid.Column="1" Name="LocalIpText" TextWrapping="Wrap"/><TextBlock Grid.Row="4" Text="Интерфейс"/><TextBlock Grid.Row="4" Grid.Column="1" Name="InterfaceText"/><TextBlock Grid.Row="5" Text="VPN-интерфейс"/><TextBlock Grid.Row="5" Grid.Column="1" Name="VpnInterfaceText"/><TextBlock Grid.Row="6" Text="Шлюз"/><TextBlock Grid.Row="6" Grid.Column="1" Name="GatewayText"/><TextBlock Grid.Row="7" Text="DNS"/><TextBlock Grid.Row="7" Grid.Column="1" Name="DnsText" TextWrapping="Wrap"/>
   </Grid></Grid></Border>
   <Border Grid.Column="1" Background="#121D2E" CornerRadius="10" Padding="18" Margin="8,0,0,0"><Grid><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="*"/></Grid.RowDefinitions><DockPanel><TextBlock Text="КАЧЕСТВО КАНАЛА" Foreground="#7F91AD" FontWeight="Bold" VerticalAlignment="Center"/><Button Name="SpeedButton" Content="Скорость интернета" HorizontalAlignment="Right" Padding="10,5"/></DockPanel><UniformGrid Grid.Row="1" Columns="3" Margin="0,18"><StackPanel><TextBlock Name="PingText" Text="—" FontSize="28" HorizontalAlignment="Center"/><TextBlock Text="ПИНГ, МС" Foreground="#7F91AD" HorizontalAlignment="Center"/></StackPanel><StackPanel><TextBlock Name="JitterText" Text="—" FontSize="28" HorizontalAlignment="Center"/><TextBlock Text="КОЛЕБАНИЯ ЗАДЕРЖКИ, МС" Foreground="#7F91AD" HorizontalAlignment="Center"/></StackPanel><StackPanel><TextBlock Name="LossText" Text="—" FontSize="28" HorizontalAlignment="Center"/><TextBlock Text="ПОТЕРИ, %" Foreground="#7F91AD" HorizontalAlignment="Center"/></StackPanel></UniformGrid><StackPanel Grid.Row="2"><TextBlock Text="СОБЫТИЯ" Foreground="#7F91AD" FontWeight="Bold" Margin="0,0,0,8"/><ListBox Name="EventList" Background="#0D1726" Foreground="#D9E5F2" BorderThickness="0" Padding="8"/></StackPanel></Grid></Border>
  </Grid>
  <DockPanel Grid.Row="3" Margin="0,16,0,0"><StackPanel Orientation="Horizontal"><TextBlock Text="Проверка:" VerticalAlignment="Center"/><ComboBox Name="IntervalBox" Width="80" Margin="8,0" SelectedIndex="2"><ComboBoxItem Content="1 сек" Tag="1"/><ComboBoxItem Content="2 сек" Tag="2"/><ComboBoxItem Content="5 сек" Tag="5"/><ComboBoxItem Content="10 сек" Tag="10"/><ComboBoxItem Content="30 сек" Tag="30"/><ComboBoxItem Content="60 сек" Tag="60"/></ComboBox><Button Name="CheckButton" Content="Проверить сейчас" Padding="16,7" Margin="8,0"/><Button Name="LogButton" Content="Открыть журнал" Padding="16,7" Margin="8,0"/></StackPanel><Button Name="KillButton" DockPanel.Dock="Right" Content="Включить Kill Switch…" Padding="16,7" Background="#792F3D" Foreground="White"/></DockPanel>
 </Grid>
</Window>
'@

$reader = New-Object System.Xml.XmlNodeReader ([xml]$xaml)
$window = [Windows.Markup.XamlReader]::Load($reader)
if (Test-Path -LiteralPath $IconPath) {
    try {
        $window.Icon = [System.Windows.Media.Imaging.BitmapFrame]::Create([System.Uri]::new($IconPath))
    } catch {
        Write-GuardianEvent 'WARN' 'ui_icon' 'Не удалось загрузить значок окна' @{ path=$IconPath; error=$_.Exception.Message }
    }
}
$alertXaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Width="74" Height="74" WindowStyle="None" AllowsTransparency="True"
        Background="Transparent" Topmost="True" ShowInTaskbar="False"
        ShowActivated="False" ResizeMode="NoResize" Focusable="False">
  <Grid IsHitTestVisible="False">
    <Ellipse Width="58" Height="58" Fill="#F5222D" Stroke="#7A0008" StrokeThickness="4">
      <Ellipse.Effect><DropShadowEffect Color="#CC0000" BlurRadius="18" ShadowDepth="0" Opacity="0.95"/></Ellipse.Effect>
    </Ellipse>
  </Grid>
</Window>
'@
$alertReader = New-Object System.Xml.XmlNodeReader ([xml]$alertXaml)
$alertWindow = [Windows.Markup.XamlReader]::Load($alertReader)
$alertWindow.Left = [System.Windows.SystemParameters]::WorkArea.Right - $alertWindow.Width - 18
$alertWindow.Top = [System.Windows.SystemParameters]::WorkArea.Top + 18
if ($OverlayTest) {
    $testWindow = $alertWindow
    $overlayTimer = New-Object Windows.Threading.DispatcherTimer
    $overlayTimer.Interval = [TimeSpan]::FromSeconds(3)
    $closeOverlay = {
        $overlayTimer.Stop()
        $testWindow.Close()
    }.GetNewClosure()
    $overlayTimer.Add_Tick($closeOverlay)
    $overlayTimer.Start()
    [void]$alertWindow.ShowDialog()
    return
}
$names = @('LastCheck','ProfileText','StatusCard','StatusDot','SecurityText','HealthText','InternetText','VpnText','PublicIpText','LocalIpText','InterfaceText','VpnInterfaceText','GatewayText','DnsText','PingText','JitterText','LossText','EventList','IntervalBox','CheckButton','LogButton','KillButton','SpeedButton')
$ui = @{}; foreach($name in $names){$ui[$name]=$window.FindName($name)}
$config = Read-GuardianConfig
$ui.ProfileText.Text = "Профиль: $($config.profile)"
$script:lastSecurity = ''
$script:killEnabled = $false
$script:busy = $false
$script:happLostCount = 0
$script:psiphonRequested = $false
$script:happReconnectAttempts = 0
$script:happRestoreCount = 0
$script:happLaunchAttemptedForIncident = $false
$script:lastHappLaunchAttempt = [datetime]::MinValue
$script:chatGptBlocked = Test-ChatGptBlock $config

function Add-UiEvent([string]$Text) {
    $ui.EventList.Items.Insert(0, ('{0}  {1}' -f (Get-Date -Format 'HH:mm:ss'), $Text))
    while($ui.EventList.Items.Count -gt 100){$ui.EventList.Items.RemoveAt(100)}
}

function Convert-GuardianStatusToRussian([string]$Status) {
    $labels = @{
        'DIRECT' = 'Прямое подключение'; 'DEGRADED' = 'Снижение качества'
        'LEAK' = 'Утечка'; 'UNVERIFIED' = 'Не подтверждено'
        'OK' = 'В норме'; 'UP' = 'Работает'; 'DOWN' = 'Не работает'; 'LOST' = 'Потеряно'
    }
    if ($labels.ContainsKey($Status)) { return $labels[$Status] }
    return $Status
}

$script:probeWorker = $null
$script:probeHandle = $null
function Update-Dashboard {
    if($script:busy){return}; $script:busy=$true
    try {
        # Network timeouts must not block the WPF dispatcher. Only one worker runs.
        if ($null -eq $script:probeHandle) {
            $definitions = foreach ($name in @('Get-DefaultRoute','Get-PublicIp','Measure-Link','Get-GuardianSnapshot')) {
                'function ' + $name + ' {' + (Get-Command $name).Definition + '}'
            }
            if ($null -eq $script:probeWorker) { $script:probeWorker = [PowerShell]::Create() }
            $script:probeWorker.Commands.Clear()
            $script:probeWorker.Streams.Error.Clear()
            [void]$script:probeWorker.AddScript({
                param($modulePath,$functions,$settings)
                $ErrorActionPreference='Stop'
                Import-Module $modulePath
                Invoke-Expression $functions
                $happ = Get-HappProtectionState $settings
                [pscustomobject]@{ Snapshot=(Get-GuardianSnapshot $settings); Happ=$happ; Psiphon=(Get-GuardianPsiphonState) }
            }).AddArgument($AppProtectionModule).AddArgument(($definitions -join "`n")).AddArgument($config)
            $script:probeHandle = $script:probeWorker.BeginInvoke()
            $ui.LastCheck.Text = 'Проверка в фоне…'
            return
        }
        if (-not $script:probeHandle.IsCompleted) { return }
        try {
            $batch = @($script:probeWorker.EndInvoke($script:probeHandle))
            if ($script:probeWorker.HadErrors -or $batch.Count -ne 1) { throw 'Не удалось получить сетевые данные. Проверьте права доступа; состояние не подтверждено.' }
            $snapshot=$batch[0].Snapshot; $happState=$batch[0].Happ; $psiphonState=$batch[0].Psiphon
        } finally {
            $script:probeHandle=$null
        }
        $ui.LastCheck.Text = 'Проверено: ' + $snapshot.Timestamp.ToString('HH:mm:ss')
        $ui.SecurityText.Text=Convert-GuardianStatusToRussian $snapshot.Security; $ui.HealthText.Text="Состояние VPN: $($snapshot.VpnHealth)/100  |  Стабильность: $($snapshot.Stability)%  |  Утечка: $(Convert-GuardianStatusToRussian $snapshot.LeakProtection)"
        $ui.InternetText.Text=$snapshot.Internet; $ui.VpnText.Text="$(Convert-GuardianStatusToRussian $snapshot.Vpn) / Туннель: $(Convert-GuardianStatusToRussian $snapshot.TunnelStatus)"
        $ui.PublicIpText.Text=$snapshot.PublicIp; $ui.LocalIpText.Text=$snapshot.LocalIp
        $ui.InterfaceText.Text=$snapshot.Interface; $ui.VpnInterfaceText.Text="$($snapshot.VpnInterface) / Happ $(if($happState.Protected){'OK'}else{'LOST'})"
        if (-not $happState.Protected) { $ui.VpnInterfaceText.Text = "Happ LOST / Psiphon: $($psiphonState.Status)" }
        $ui.GatewayText.Text="$($snapshot.Gateway) / Маршрут: $(Convert-GuardianStatusToRussian $snapshot.RouteStatus)"; $ui.DnsText.Text="$($snapshot.Dns) [$(Convert-GuardianStatusToRussian $snapshot.DnsStatus)]"
        $ui.PingText.Text=$snapshot.Ping; $ui.JitterText.Text=$snapshot.Jitter; $ui.LossText.Text=$snapshot.Loss
        $connectionHealthy = $happState.Protected -and $snapshot.Internet -eq 'ONLINE' -and -not $snapshot.Leak -and $snapshot.DnsStatus -eq 'OK'
        if ($connectionHealthy) {
            $ui.StatusCard.Background='#123D33'; $ui.StatusDot.Fill='#35D07F'
            $ui.SecurityText.Text='СОЕДИНЕНИЕ В НОРМЕ'
        } else {
            $ui.StatusCard.Background='#542431'; $ui.StatusDot.Fill='#FF4D6D'
            $ui.SecurityText.Text='ПРОБЛЕМА СОЕДИНЕНИЯ'
        }
        if($script:lastSecurity -ne $snapshot.Security){
            Add-UiEvent "Состояние: $($snapshot.Security)"
            Write-GuardianEvent $(if($snapshot.Leak){'CRITICAL'}else{'INFO'}) 'state_change' "Security state: $($snapshot.Security)" $snapshot
            $script:lastSecurity=$snapshot.Security
        }

        if ($connectionHealthy) {
            $script:happLostCount = 0
            $script:happRestoreCount++
            if ($script:happRestoreCount -ge [int]$config.happRestoreConfirmationCount) {
                if ($alertWindow.IsVisible) { $alertWindow.Hide() }
                $script:happLaunchAttemptedForIncident = $false
                $script:happReconnectAttempts = 0
                $script:psiphonRequested = $false
                $script:lastHappLaunchAttempt = [datetime]::MinValue
                if ($script:chatGptBlocked) {
                    try {
                        Disable-ChatGptBlock $config | Out-Null
                        $script:chatGptBlocked = $false
                    Add-UiEvent 'Happ восстановлен — доступ ChatGPT и Claude разблокирован'
                    Write-GuardianEvent 'INFO' 'chatgpt_unblocked' 'Happ protection restored; ChatGPT and Claude firewall rules removed' $happState
                    } catch {
                        Add-UiEvent "Не удалось снять блокировку ChatGPT и Claude: $($_.Exception.Message)"
                        Write-GuardianEvent 'ERROR' 'chatgpt_unblock_failed' $_.Exception.Message $happState
                    }
                }
            }
        } else {
            $script:happRestoreCount = 0
            $script:happLostCount++
            if ($script:happLostCount -ge [int]$config.happLostConfirmationCount) {
                if ($config.psiphonFallbackEnabled -and -not $script:psiphonRequested) {
                    $script:psiphonRequested = $true
                    try {
                        Start-GuardianPsiphon $config
                        Add-UiEvent 'Happ недоступен: резерв Psiphon запрошен автоматически.'
                        Write-GuardianEvent 'WARNING' 'psiphon_fallback_requested' 'Fallback requested after confirmed Happ loss; connection not yet verified' @{}
                    } catch {
                        Add-UiEvent "Не удалось запустить резерв Psiphon: $($_.Exception.Message)"
                        Write-GuardianEvent 'ERROR' 'psiphon_fallback_failed' $_.Exception.Message @{}
                    }
                }
                if (-not $alertWindow.IsVisible) {
                    $alertWindow.Show()
                    Add-UiEvent 'ВНИМАНИЕ: защищённый маршрут Happ потерян'
                    Write-GuardianEvent 'CRITICAL' 'happ_route_lost' 'Happ adapter/default route protection lost' $happState
                }
                $now = Get-Date
                $cooldownSeconds = [math]::Max(1, [int]$config.happLaunchCooldownSeconds)
                $launchDue = (-not $script:happLaunchAttemptedForIncident) -or (($now - $script:lastHappLaunchAttempt).TotalSeconds -ge $cooldownSeconds)
                if (-not $happState.Protected -and $launchDue -and $script:happReconnectAttempts -lt [math]::Min(3, [int]$config.maxReconnectAttempts)) {
                    $script:happReconnectAttempts++
                    $script:happLaunchAttemptedForIncident = $true
                    $script:lastHappLaunchAttempt = $now
                    try {
                        Start-HappClient $config | Out-Null
                        Add-UiEvent "Happ: запрос переподключения $script:happReconnectAttempts; проверка результата, пауза $cooldownSeconds сек."
                        Write-GuardianEvent 'WARNING' 'happ_reconnect_requested' 'Happ disconnect/connect requested; awaiting healthy probes' @{State=$happState;Attempt=$script:happReconnectAttempts;CooldownSeconds=$cooldownSeconds}
                    } catch {
                        Add-UiEvent "Не удалось запустить Happ: $($_.Exception.Message)"
                        Write-GuardianEvent 'ERROR' 'happ_autostart_failed' $_.Exception.Message @{State=$happState;RetryAfterSeconds=$cooldownSeconds}
                    }
                }
                if ($launchDue -and (($now - $script:lastHappLaunchAttempt).TotalSeconds -ge $cooldownSeconds) -and $script:happReconnectAttempts -eq [math]::Min(3, [int]$config.maxReconnectAttempts)) {
                    if ($config.psiphonFallbackEnabled) {
                        try {
                            Start-GuardianPsiphon $config
                            Add-UiEvent 'Резерв Psiphon запрошен. Проверяем прокси; защита всего ПК не подтверждена.'
                            Write-GuardianEvent 'WARNING' 'psiphon_fallback_requested' 'Psiphon requested; firewall protection retained' @{}
                        } catch {
                            Add-UiEvent "Psiphon: $($_.Exception.Message)"
                            Write-GuardianEvent 'ERROR' 'psiphon_fallback_failed' $_.Exception.Message @{}
                        }
                    }
                    Add-UiEvent 'Попытки Happ исчерпаны. Резервный прокси не снимает защитную блокировку приложений.'
                    Write-GuardianEvent 'ERROR' 'happ_reconnect_limit' 'Reconnect limit reached; manual check required if connection remains down' @{}
                    $script:happReconnectAttempts++
                }
                if ([bool]$config.blockChatGptOnHappLoss -and -not $script:chatGptBlocked) {
                    try {
                        $blockedPaths = @(Enable-ChatGptBlock $config)
                        $script:chatGptBlocked = $true
                        Add-UiEvent 'ChatGPT и Claude заблокированы до восстановления Happ'
                        Write-GuardianEvent 'CRITICAL' 'chatgpt_blocked' 'Inbound and outbound ChatGPT and Claude traffic blocked' @{Paths=$blockedPaths}
                    } catch {
                        Add-UiEvent "Не удалось заблокировать ChatGPT и Claude: $($_.Exception.Message)"
                        Write-GuardianEvent 'ERROR' 'chatgpt_block_failed' $_.Exception.Message $happState
                    }
                }
            }
        }
    } catch {
        $ui.StatusCard.Background='#542431'; $ui.StatusDot.Fill='#FF4D6D'
        $ui.SecurityText.Text='ОШИБКА ПРОВЕРКИ'
        Add-UiEvent "Ошибка проверки: $($_.Exception.Message)"
        Write-GuardianEvent 'WARNING' 'monitor_error' $_.Exception.Message @{}
    } finally {$script:busy=$false}
}

$timer = New-Object Windows.Threading.DispatcherTimer
$timer.Interval=[TimeSpan]::FromSeconds([double]$config.checkIntervalSeconds)
$timer.Add_Tick({Update-Dashboard})
foreach ($item in $ui.IntervalBox.Items) {
    if ([int]$item.Tag -eq [int]$config.checkIntervalSeconds) { $ui.IntervalBox.SelectedItem = $item; break }
}
$ui.IntervalBox.Add_SelectionChanged({
    $seconds=[int]$ui.IntervalBox.SelectedItem.Tag; $timer.Interval=[TimeSpan]::FromSeconds($seconds)
    try {
        $saved = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $saved.checkIntervalSeconds = $seconds
        $saved | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
        $config.checkIntervalSeconds = $seconds
    } catch { Add-UiEvent 'Не удалось сохранить интервал проверки' }
})
$ui.CheckButton.Add_Click({Update-Dashboard})
$ui.SpeedButton.Add_Click({
    $speedScript = Join-Path $AppDir 'Guardian.SpeedTest.ps1'
    Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -STA -File "{0}"' -f $speedScript)
})
$ui.LogButton.Add_Click({Start-Process explorer.exe -ArgumentList $LogDir})
$ui.KillButton.Add_Click({
    try {
        if(-not $script:killEnabled){
            $answer=[Windows.MessageBox]::Show('Это заблокирует весь исходящий интернет-трафик. Продолжить?','Kill Switch',[Windows.MessageBoxButton]::YesNo,[Windows.MessageBoxImage]::Warning)
            if($answer -ne 'Yes'){return}; Set-GuardianKillSwitch $true; $script:killEnabled=$true; $ui.KillButton.Content='Отключить Kill Switch'; Add-UiEvent 'Kill Switch включён'
        } else {Set-GuardianKillSwitch $false; $script:killEnabled=$false; $ui.KillButton.Content='Включить Kill Switch…'; Add-UiEvent 'Kill Switch отключён'}
    } catch {[Windows.MessageBox]::Show($_.Exception.Message,'Guardian',[Windows.MessageBoxButton]::OK,[Windows.MessageBoxImage]::Error)|Out-Null}
})
$window.Add_Closed({
    $timer.Stop()
    if ($script:probeWorker) { $script:probeWorker.Stop(); $script:probeWorker.Dispose(); $script:probeWorker=$null }
    if($alertWindow.IsVisible){$alertWindow.Close()}
})
Write-GuardianEvent 'INFO' 'startup' 'Guardian UI started' @{version='0.3.2';happProtection=$true;chatGptFailClosed=[bool]$config.blockChatGptOnHappLoss}
Update-Dashboard; $timer.Start(); [void]$window.ShowDialog()
