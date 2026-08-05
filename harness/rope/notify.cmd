@echo off
rem rope notify launcher -- double-click me. Toast + digest every 20 minutes.
powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0notify.ps1"
