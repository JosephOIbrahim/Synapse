@echo off
rem rope watch launcher -- double-click me. %~dp0 = this file's own folder,
rem so the path is always right and no quoting can ever mangle it.
powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0watch.ps1"
