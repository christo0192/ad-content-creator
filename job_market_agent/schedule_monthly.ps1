# Registers a Windows Scheduled Task that runs the LinkedIn job-market agent
# once a month (default: 2nd of each month, 09:00 local).
#
#   powershell -ExecutionPolicy Bypass -File schedule_monthly.ps1            # register
#   powershell -ExecutionPolicy Bypass -File schedule_monthly.ps1 -Remove    # unregister
#
# The task runs run_live.ps1, which loads the Apify token from the secrets file.

param(
    [int]$DayOfMonth = 2,
    [string]$At = "09:00",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$taskName = "IK-JobMarketDemand-LinkedIn-Monthly"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$wrapper = Join-Path $here "run_live.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "Removed scheduled task: $taskName"
    exit 0
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapper`""
# Monthly trigger (CIM): every month on $DayOfMonth at $At.
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$trigger.Repetition = $null
# Constrain to one day-of-month via a CIM monthly trigger:
$cim = Get-CimClass -Namespace Root/Microsoft/Windows/TaskScheduler -ClassName MSFT_TaskMonthlyTrigger -ErrorAction SilentlyContinue
if ($cim) {
    $t = New-CimInstance -CimClass $cim -ClientOnly
    $t.DaysOfMonth = $DayOfMonth
    $hm = $At.Split(":")
    $start = (Get-Date -Hour $hm[0] -Minute $hm[1] -Second 0)
    $t.StartBoundary = $start.ToString("yyyy-MM-ddTHH:mm:ss")
    $t.Enabled = $true
    $trigger = $t
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Monthly LinkedIn AI/ML job-market demand scrape -> BigQuery" -Force | Out-Null

Write-Output "Registered '$taskName' — day $DayOfMonth of each month at $At."
Write-Output "Test now:  Start-ScheduledTask -TaskName '$taskName'"
