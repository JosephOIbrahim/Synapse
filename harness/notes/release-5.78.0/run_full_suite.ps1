# run_full_suite.ps1 - the CI command, verbatim, detached. Poll pytest-full.log.
Set-Location 'C:\Users\User\SYNAPSE'
python -m pytest tests/ -m "not needs_houdini" -q --tb=short -p no:cacheprovider *> 'harness\notes\release-5.78.0\pytest-full.log'
"EXIT $LASTEXITCODE" | Add-Content 'harness\notes\release-5.78.0\pytest-full.log'
