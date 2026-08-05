@echo off
REM Moneta CI Deploy Key Setup — run from repo root
REM Usage: moneta_setup_ci_key.bat
REM Requires: gh CLI authenticated as JosephOIbrahim

echo === Moneta CI Deploy Key Setup ===
echo.

REM 1. Generate keypair
echo [1/4] Generating SSH keypair...
ssh-keygen -t ed25519 -f "%TEMP%\moneta_ci" -N "" -C "moneta-ci@synapse" 2>nul
if %ERRORLEVEL% neq 0 (
    echo FAILED: ssh-keygen
    exit /b 1
)
echo   OK: keypair at %%TEMP%%\moneta_ci

REM 2. Add deploy key to Moneta repo
echo [2/4] Adding deploy key to JosephOIbrahim/Moneta...
set /p PUBKEY=<"%TEMP%\moneta_ci.pub"
gh api --method POST repos/JosephOIbrahim/Moneta/keys ^
    --field title="moneta-ci" ^
    --field key="%PUBKEY%" ^
    --field read_only=true >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo FAILED: gh deploy key
    exit /b 1
)
echo   OK: deploy key added

REM 3. Add secret to Synapse repo
echo [3/4] Adding MONETA_DEPLOY_KEY secret to JosephOIbrahim/Synapse...
gh secret set MONETA_DEPLOY_KEY -R JosephOIbrahim/Synapse < "%TEMP%\moneta_ci" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo FAILED: gh secret
    exit /b 1
)
echo   OK: secret added

REM 4. Clean up
echo [4/4] Cleaning up local keypair...
del "%TEMP%\moneta_ci" "%TEMP%\moneta_ci.pub" 2>nul
echo   OK: cleaned up

echo.
echo === DONE ===
echo Next CI run will install Moneta and run ~70 tests.
echo Verify at: https://github.com/JosephOIbrahim/Synapse/actions
