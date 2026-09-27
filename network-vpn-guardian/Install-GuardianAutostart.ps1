$ErrorActionPreference='Stop'
$guardian='C:\Users\HP\Desktop\NetworkVpnGuardian-MVP-0.3-package\Guardian.ps1'
$account=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "{0}"' -f $guardian)
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $account
$principal=New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([timespan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName 'Network VPN Guardian Center' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Network security dashboard and bounded Happ reconnect' -Force | Out-Null
Start-ScheduledTask -TaskName 'Network VPN Guardian Center'
