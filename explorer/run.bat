@echo off
REM One-command launcher for the Explorer app. Double-click, or run from a terminal.
REM Starts the local offline dashboard on http://localhost:8000 and opens your browser.
cd /d "%~dp0.."
py explorer\app.py %*
