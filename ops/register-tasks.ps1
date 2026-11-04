# Registers the live arm's scheduled tasks and the Windows Update setting (runbook sections 0.3
# and 0.5). Tyler runs it in an admin PowerShell on a new or replacement machine, after
# C:\Users\tjnew\git\laf-detector.ps1 and laf-backup.ps1 are in place (restored from the backup:
# runbook section 7). It asks for his Windows password in the console (a Get-Credential dialog
# can open off-screen); password logon lets the tasks read Git Credential Manager. Only one
# detector may run at a time: start laf-detector only when no other detector runs.
$user = "$env:USERDOMAIN\$env:USERNAME"
$pw = Read-Host "Windows password for $user" -AsSecureString
$plain = [PSCredential]::new($user, $pw).GetNetworkCredential().Password
$run = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\tjnew\git\{0}"'

Register-ScheduledTask -TaskName laf-detector -User $user -Password $plain -RunLevel Limited `
    -Action (New-ScheduledTaskAction -Execute powershell.exe -Argument ($run -f 'laf-detector.ps1')) `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Settings (New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 5) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries)

Register-ScheduledTask -TaskName laf-backup -User $user -Password $plain -RunLevel Limited `
    -Action (New-ScheduledTaskAction -Execute powershell.exe -Argument ($run -f 'laf-backup.ps1')) `
    -Trigger (New-ScheduledTaskTrigger -Daily -At 11:30PM) `
    -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries)
Remove-Variable pw, plain

# Windows Update: notify before a restart; active hours 06:00 to 24:00.
$k = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
Set-ItemProperty $k RestartNotificationsAllowed2 1 -Type DWord
Set-ItemProperty $k SmartActiveHoursState 0 -Type DWord
Set-ItemProperty $k ActiveHoursStart 6 -Type DWord
Set-ItemProperty $k ActiveHoursEnd 0 -Type DWord

Get-ScheduledTask laf-detector, laf-backup | Select-Object TaskName, State
