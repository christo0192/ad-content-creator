# Wrapper the scheduled task invokes for the LIVE monthly LinkedIn run.
# Loads the Apify token (acct #2 `hip_bouncer`) from a local secrets file so the
# token is never hard-coded in the Task Scheduler definition or in git.
#
# Token file (one line, the raw token):
#   C:\Users\Admin\.secrets\apify_acct2.token
# Override with env JOBMKT_APIFY_TOKEN_FILE.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $here

$tokenFile = $env:JOBMKT_APIFY_TOKEN_FILE
if (-not $tokenFile) { $tokenFile = "C:\Users\Admin\.secrets\apify_acct2.token" }
if (-not (Test-Path $tokenFile)) {
    Write-Error "Apify token file not found: $tokenFile. Create it with the acct #2 token (one line)."
    exit 1
}
$env:APIFY_TOKEN = (Get-Content $tokenFile -Raw).Trim()

$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$log = Join-Path $here "logs\live_$stamp.log"
New-Item -ItemType Directory -Force -Path (Join-Path $here "logs") | Out-Null

Write-Output "[$stamp] starting live LinkedIn run -> $log"
python run_monthly.py *>&1 | Tee-Object -FilePath $log
exit $LASTEXITCODE
