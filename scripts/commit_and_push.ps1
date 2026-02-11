# Commit and push changes (run ruff + black first)
# Usage: .\scripts\commit_and_push.ps1 [-Message "commit message"] [-NoPush]

param(
    [string]$Message = "Update classifier, UI defaults, docs; run ruff and black",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"
$root = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $root

Write-Host "Running ruff check . --fix ..."
ruff check . --fix
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running black . ..."
black .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Verifying ruff check . (no fix)..."
ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Verifying black --check . ..."
black --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running pytest -q ..."
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Staging all changes..."
git add -A
$status = git status --short
if (-not $status) {
    Write-Host "No changes to commit."
    exit 0
}

Write-Host "Committing with message: $Message"
git commit -m $Message
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $NoPush) {
    Write-Host "Pushing to remote..."
    git push
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Done. Committed and pushed."
} else {
    Write-Host "Done. Committed (no push; use -NoPush to skip push next time)."
}
