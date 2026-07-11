@echo off
setlocal
set "ENVFILE=%~dp0.env"
echo.
echo   SYNAPSE - save your Anthropic API key to .env
echo   ============================================
echo.
echo   This writes your key to a gitignored .env beside SYNAPSE, scoped to
echo   this project. It does NOT set a system-wide ANTHROPIC_API_KEY - that
echo   would silently bill every Claude tool on your machine to your API
echo   account. Houdini loads this .env at startup.
echo.
set "KEY=%~1"
if not defined KEY set /p "KEY=  Paste your Anthropic API key (sk-ant-...): "
if not defined KEY goto :nokey
if exist "%ENVFILE%" (
  findstr /b /c:"ANTHROPIC_API_KEY=" "%ENVFILE%" >nul 2>&1 && goto :exists
)
>>"%ENVFILE%" echo ANTHROPIC_API_KEY=%KEY%
echo.
echo   [OK] Wrote ANTHROPIC_API_KEY to "%ENVFILE%".
echo.
echo   NEXT (required): fully quit and reopen Houdini so it loads the .env.
echo                    Already-open apps will not see the change.
echo.
goto :end
:exists
echo.
echo   [i] "%ENVFILE%" already has an ANTHROPIC_API_KEY line - left as-is.
echo       Edit that file directly to change the key.
goto :end
:nokey
echo.
echo   [X] No key entered - nothing changed.
goto :end
:end
echo.
pause
endlocal
