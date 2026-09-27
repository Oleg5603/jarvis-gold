#requires -Version 5.1
[CmdletBinding()]
param([switch]$Once,[switch]$NoRecovery)

$dir=Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module (Join-Path $dir 'Guardian.Core.psm1') -Force
$config=Get-Content -LiteralPath (Join-Path $dir 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$dataDir=Join-Path $dir 'data';New-Item -ItemType Directory -Path $dataDir -Force|Out-Null
$statePath=Join-Path $dataDir 'core-state.json';$eventPath=Join-Path $dataDir 'core-events.jsonl'
$incidentPath=Join-Path $dataDir 'incidents.jsonl';$protectionPath=Join-Path $dataDir 'protection-state.json'
$state=Read-CoreState $statePath
foreach($field in @{VpnCandidateIp='';VpnCandidateCount=0}.GetEnumerator()){
    if($null -eq $state.PSObject.Properties[$field.Key]){$state|Add-Member -NotePropertyName $field.Key -NotePropertyValue $field.Value}
}

do {
    $snapshot=Get-GuardianCoreSnapshot $config $state
    if($snapshot.VpnLost){$state.LostCount=[int]$state.LostCount+1}else{$state.LostCount=0}
    if($snapshot.VpnHung){$state.HungCount=[int]$state.HungCount+1}else{$state.HungCount=0}
    $incident=Get-IncidentClassification $snapshot $state $config
    Write-CoreEvent $eventPath 'CORE_SNAPSHOT' 'INFO' $snapshot.State $snapshot

    if($snapshot.State -eq 'DIRECT' -and $snapshot.PublicIp -and -not $state.DirectPublicIp){$state.DirectPublicIp=$snapshot.PublicIp}
    # Learn a VPN public IP only after three consistent, routed, healthy observations.
    if(-not $state.VpnPublicIp -and $snapshot.ControlPlaneOk -and $snapshot.Probes.Quorum -and $snapshot.PublicIp -and $snapshot.PublicIp -ne $state.DirectPublicIp -and $snapshot.Dns.Status -eq 'OK'){
        if($state.VpnCandidateIp -eq $snapshot.PublicIp){$state.VpnCandidateCount=[int]$state.VpnCandidateCount+1}else{$state.VpnCandidateIp=$snapshot.PublicIp;$state.VpnCandidateCount=1}
        if([int]$state.VpnCandidateCount -ge 3){$state.VpnPublicIp=$state.VpnCandidateIp;Write-CoreEvent $eventPath 'VPN_IP_LEARNED' 'INFO' 'VPN public IP baseline confirmed' @{PublicIp=$state.VpnPublicIp;Observations=$state.VpnCandidateCount}}
    }
    if($snapshot.State -eq 'PROTECTED'){
        $state.VpnPublicIp=$snapshot.PublicIp;$state.ReconnectAttempts=0
        $state.LastKnownGood=[pscustomobject]@{Time=(Get-Date).ToString('o');PublicIp=$snapshot.PublicIp;Gateway=$snapshot.Gateway;Interface=$snapshot.VpnInterface;Dns=$snapshot.Dns.VpnDns}
    }

    if($incident.RequiresProtection){
        $incidentId='INC-'+(Get-Date -Format 'yyyyMMdd-HHmmss')
        $record=[ordered]@{Id=$incidentId;Started=(Get-Date).ToString('o');Severity=$incident.Severity;Reason=$incident.Reason;Mode=$config.failClosedMode;Protection='';Recovery=@();FinalState='';Ended=''}
        if($config.failClosedMode -eq 'Shadow'){
            $record.Protection='FAIL-CLOSED WOULD ACTIVATE'
            Write-CoreEvent $eventPath 'SHADOW_FAIL_CLOSED' 'CRITICAL' "FAIL-CLOSED WOULD ACTIVATE: $($incident.Reason)" @{ExpectedAction='BLOCK';VpnRecoveryPossible=[bool]($config.vpnConnectionName -or $config.vpnReconnectCommand)}
        } elseif($config.failClosedMode -eq 'Automatic') {
            try{Enable-CoreKillSwitch $config $protectionPath|Out-Null;$record.Protection='BLOCKED'}catch{$record.Protection='BLOCK_FAILED';$record.Recovery+=@{Action='PROTECT';Result='FAILED';Error=$_.Exception.Message}}
        } else {$record.Protection='MANUAL_REQUIRED'}

        if(-not $NoRecovery -and [int]$state.ReconnectAttempts -lt [int]$config.maxReconnectAttempts){
            $cooldowns=@($config.cooldownSeconds);$index=[math]::Min([int]$state.ReconnectAttempts,$cooldowns.Count-1)
            if([int]$state.ReconnectAttempts -gt 0){Start-Sleep -Seconds ([int]$cooldowns[$index])}
            $state.ReconnectAttempts=[int]$state.ReconnectAttempts+1
            $ok=Invoke-VpnReconnect $config;$record.Recovery+=@{Action='VPN_RECONNECT';Attempt=$state.ReconnectAttempts;Result=if($ok){'COMMAND_OK'}else{'NOT_AVAILABLE_OR_FAILED'}}
            if($ok){Start-Sleep -Seconds 5;$verified=Get-GuardianCoreSnapshot $config $state;$record.Recovery+=@{Action='POST_RECOVERY_VALIDATION';Result=$verified.State};if($verified.State -eq 'PROTECTED'){$snapshot=$verified;if($config.failClosedMode -eq 'Automatic'){Disable-CoreKillSwitch $protectionPath|Out-Null}}}
        }
        $record.FinalState=$snapshot.State;if([int]$state.ReconnectAttempts -ge [int]$config.maxReconnectAttempts -and $snapshot.State -ne 'PROTECTED'){$record.FinalState='LOCKDOWN'}
        $record.Ended=(Get-Date).ToString('o');($record|ConvertTo-Json -Compress -Depth 8)|Add-Content -LiteralPath $incidentPath -Encoding UTF8
    }
    $state.LastState=$snapshot.State;Save-CoreState $state $statePath
    if(-not $Once){Start-Sleep -Seconds ([int]$config.checkIntervalSeconds)}
} while(-not $Once)
