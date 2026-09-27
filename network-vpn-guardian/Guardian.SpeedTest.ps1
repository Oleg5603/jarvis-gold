#requires -Version 5.1
[CmdletBinding()]
param([switch]$Probe, [switch]$UiTest)
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Net.Http
Add-Type -Path (Join-Path $PSScriptRoot 'Guardian.SpeedTest.cs') -ReferencedAssemblies System.Net.Http
if ($Probe) {
    $cancel = [Threading.CancellationTokenSource]::new(60000)
    try { [GuardianSpeedTest]::Run($cancel.Token).GetAwaiter().GetResult() | ConvertTo-Json }
    finally { $cancel.Dispose() }
    return
}
$created = $false
$mutex = [Threading.Mutex]::new($true, 'Local\GuardianSpeedTest', [ref]$created)
if (-not $created -and -not $UiTest) { [GuardianSpeedTest]::Activate(); $mutex.Dispose(); return }
[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="Скорость интернета" Width="460" Height="350" ResizeMode="NoResize" WindowStartupLocation="CenterScreen" Background="#0B1220" Foreground="#E5EDF8">
 <StackPanel Margin="22">
  <TextBlock Text="Скорость интернета" FontSize="23" FontWeight="SemiBold"/>
  <UniformGrid Columns="3" Margin="0,22,0,18">
   <StackPanel><TextBlock Name="Down" Text="—" FontSize="27" Foreground="#35D07F"/><TextBlock Text="Приём, Мбит/с"/></StackPanel>
   <StackPanel><TextBlock Name="Up" Text="—" FontSize="27" Foreground="#64B5F6"/><TextBlock Text="Отдача, Мбит/с"/></StackPanel>
   <StackPanel><TextBlock Name="Latency" Text="—" FontSize="27"/><TextBlock Text="Ответ HTTPS, мс" FontSize="11"/></StackPanel>
  </UniformGrid>
  <TextBlock Name="Status" Text="Нажмите «Измерить»" TextWrapping="Wrap" MinHeight="34" Foreground="#B7C7D9"/>
  <StackPanel Orientation="Horizontal" Margin="0,5,0,12"><Button Name="Start" Content="Измерить" Padding="22,7"/><Button Name="Cancel" Content="Отмена" Padding="18,7" Margin="10,0,0,0" IsEnabled="False"/></StackPanel>
  <TextBlock Text="Быстрый замер до Cloudflare · до 60 сек · около 3 МБ.
Оценка текущего соединения с учётом VPN и прокси." FontSize="11" Foreground="#7F91AD"/>
 </StackPanel>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Load([System.Xml.XmlNodeReader]::new($xaml))
$ui = @{}; foreach ($name in @('Down','Up','Latency','Status','Start','Cancel')) { $ui[$name] = $window.FindName($name) }
$script:task = $null; $script:cancel = $null; $script:cancelledByUser = $false
$timer = [Windows.Threading.DispatcherTimer]::new()
$timer.Interval = [TimeSpan]::FromMilliseconds(150)
$ui.Start.Add_Click({
    if ($script:task) { return }
    $ui.Down.Text='—'; $ui.Up.Text='—'; $ui.Latency.Text='—'
    $ui.Start.IsEnabled=$false; $ui.Cancel.IsEnabled=$true
    $ui.Status.Text='Измеряю приём, отдачу и задержку…'
    $script:cancelledByUser=$false
    $script:cancel=[Threading.CancellationTokenSource]::new(60000)
    $script:task=[GuardianSpeedTest]::Run($script:cancel.Token)
    $timer.Start()
})
$ui.Cancel.Add_Click({ $script:cancelledByUser=$true; if ($script:cancel) { $script:cancel.Cancel() } })
$timer.Add_Tick({
    if (-not $script:task -or -not $script:task.IsCompleted) { return }
    $timer.Stop()
    try {
        $result=$script:task.GetAwaiter().GetResult()
        $ui.Down.Text=if ([double]::IsNaN($result.DownloadMbps)) {'—'} else {('{0:N1}' -f $result.DownloadMbps)}
        $ui.Up.Text=if ([double]::IsNaN($result.UploadMbps)) {'—'} else {('{0:N1}' -f $result.UploadMbps)}
        $ui.Latency.Text=if ([double]::IsNaN($result.LatencyMs)) {'—'} else {('{0:N0}' -f $result.LatencyMs)}
        $ui.Status.Text='Замер: ' + (Get-Date -Format 'HH:mm:ss')
        if ($result.DownloadError) { $ui.Status.Text += ' | Приём: ' + $result.DownloadError }
        if ($result.UploadError) { $ui.Status.Text += ' | Отдача: ' + $result.UploadError }
        New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot 'data') | Out-Null
        $result | Select-Object *, @{Name='MeasuredAt';Expression={(Get-Date).ToString('o')}} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'data\last-speedtest.json') -Encoding UTF8
    } catch {
        if ($script:cancelledByUser) { $ui.Status.Text='Замер отменён.' }
        elseif ($script:cancel.IsCancellationRequested) { $ui.Status.Text='Время замера истекло (60 сек). Повторите позже.' }
        else { $ui.Status.Text='Сервер замера недоступен. Проверьте соединение и повторите.' }
    } finally {
        $script:task=$null; $script:cancel.Dispose(); $script:cancel=$null
        $ui.Start.IsEnabled=$true; $ui.Cancel.IsEnabled=$false
    }
})
$window.Add_Closed({ $timer.Stop(); if ($script:cancel) { $script:cancel.Cancel() } })
if (-not $UiTest) { $window.Add_ContentRendered({ $ui.Start.RaiseEvent([Windows.RoutedEventArgs]::new([Windows.Controls.Button]::ClickEvent)) }) }
try {
    if ($UiTest) { $window.Show(); $window.UpdateLayout(); if ($ui.Start.ActualWidth -lt 1) { throw 'UI layout failed' }; $window.Close(); 'PASS: speed window layout' }
    else { [void]$window.ShowDialog() }
} finally { if ($created) { $mutex.ReleaseMutex() }; $mutex.Dispose() }
