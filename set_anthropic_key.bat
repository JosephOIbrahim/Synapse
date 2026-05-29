@echo off
setlocal
echo.
echo   SYNAPSE - persist your Anthropic API key
echo   ========================================
echo.
echo   Houdini launches as its own process and only inherits PERSISTENT
echo   (User) environment variables, so a plain "set" in a terminal never
echo   reaches it. This saves your key with setx so a freshly-launched
echo   Houdini can see it. Your key is NOT stored in this file.
echo.
set "KEY=%~1"
if not defined KEY set /p "KEY=  Paste your Anthropic API key (sk-ant-...): "
if not defined KEY goto :nokey
setx ANTHROPIC_API_KEY "%KEY%" >nul 2>&1
if errorlevel 1 goto :failed
echo.
echo   [OK] Saved ANTHROPIC_API_KEY to your User environment.
echo.
echo   NEXT (required): fully quit and reopen Houdini so it picks up the key.
echo                    Already-open apps will not see the change.
echo.
echo   Verify in Houdini's Python Shell:
echo       import os; print(bool(os.environ.get("ANTHROPIC_API_KEY")))
echo       -- should print True
echo.
goto :end
:nokey
echo.
echo   [X] No key entered - nothing changed.
goto :end
:failed
echo.
echo   [X] setx failed - open a normal Command Prompt and run it again.
:end
echo.
pause
endlocal
