<#
.SYNOPSIS
    Registers one morning of the #125 run as a Windows scheduled task, or prints what it would register.

.DESCRIPTION
    Fires scripts/hardware_daily.py at 03:45 UTC, which is 06:45 in Istanbul. Without -Register this
    only prints the task, so it changes nothing on the machine.

    The task is created with:
      - a wake timer, which is not how the run is fired. This laptop's only standby is Modern
        Standby, and the wake tests showed the timer does not wake it from there. So for the 14
        nights the laptop stays awake: on mains, logged in, lid open, never put to sleep (the lead's
        decision of 2026-11-08, docs/implementations/2026-11-05-hardware-test-submission.md). A
        night it sleeps through is a missed morning, never a late job. The timer stays because it
        costs nothing on a machine where it does work;
      - "start as soon as possible" after a missed start, so a morning the laptop was off still scores
        earlier days and records the day as missed. It cannot submit late: the script refuses that;
      - a three hour limit above the per-step limits inside the routine;
      - the current user's interactive logon, which needs no stored password. The user must stay
        logged in. A locked screen is fine; signing out stops the run.

    Without -Daily the task fires once at -At, for the rehearsal. With -Daily it fires every day, and
    the routine itself does nothing outside the run's 15 days.

.EXAMPLE
    # See the rehearsal's task without creating it:
    .\scripts\hardware_schedule.ps1 -Clone C:\t1dfull -Python C:\t\pin125\Scripts\python.exe `
        -TaskLog C:\t\jobs-125-task.log -At '2026-11-07T03:45:00Z' `
        -RoutineArgs @('--first-day','2026-10-20', ...)
#>
param(
    [Parameter(Mandatory)] [string] $Clone,
    [Parameter(Mandatory)] [string] $Python,
    [Parameter(Mandatory)] [string[]] $RoutineArgs,
    # Outside the clone: a file inside it would dirty the tree and the freeze guard would refuse.
    [Parameter(Mandatory)] [string] $TaskLog,
    [string] $At = '',
    [string] $TaskName = 'SuperconducTED-issue-125-morning',
    [switch] $Daily,
    [switch] $Register
)

$ErrorActionPreference = 'Stop'

if ($Daily -and $At) { throw 'Use -At for the one-off rehearsal, or -Daily, not both.' }
if (-not $Daily -and -not $At) { throw 'Give -At for the one-off rehearsal, or -Daily.' }

# 03:45 UTC in this machine's own zone, so the trigger does not depend on the laptop being set to
# Istanbul. Turkey keeps one offset all year, and a machine in a zone with daylight saving would
# need re-registering when the clocks change.
$utcStart = if ($Daily) {
    [datetime]::SpecifyKind([datetime]::UtcNow.Date.AddHours(3).AddMinutes(45), [DateTimeKind]::Utc)
} else {
    ([datetimeoffset]::Parse($At)).UtcDateTime
}
$localStart = $utcStart.ToLocalTime()

# The routine's children inherit PYTHONPATH, and its log gets anything raised before its own begins.
$quoted = ($RoutineArgs | ForEach-Object { '"' + $_ + '"' }) -join ' '
$cloneRoot = (Resolve-Path -LiteralPath $Clone).Path.TrimEnd('\') + '\'
if ([System.IO.Path]::GetFullPath($TaskLog).StartsWith($cloneRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "The task log must be outside the clone: $TaskLog"
}
$command = "/c set `"PYTHONPATH=.;src`" && `"$Python`" scripts\hardware_daily.py $quoted >> `"$TaskLog`" 2>&1"

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $command -WorkingDirectory $Clone
$trigger = if ($Daily) {
    New-ScheduledTaskTrigger -Daily -At $localStart
} else {
    New-ScheduledTaskTrigger -Once -At $localStart
}
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Write-Output "task:     $TaskName"
Write-Output "fires:    $($localStart.ToString('yyyy-MM-dd HH:mm')) local, $($utcStart.ToString('HH:mm')) UTC, $(if ($Daily) { 'every day' } else { 'once' })"
Write-Output "in:       $Clone"
Write-Output "runs:     cmd.exe $command"
Write-Output "wake:     $($settings.WakeToRun)"

if (-not $Register) {
    Write-Output 'not registered: pass -Register to create it'
    exit 0
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal | Out-Null
Write-Output "registered. Remove it with: Unregister-ScheduledTask -TaskName '$TaskName'"
