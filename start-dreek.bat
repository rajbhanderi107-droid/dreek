@echo off
setlocal
cd /d "%~dp0"

rem Prefer Edge: its online neural voices are far better than the bundled ones.
set "BROWSER="
for %%B in (
  "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
  "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
  "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
  "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) do if exist %%B set "BROWSER=%%B"

if defined BROWSER (
  start "" %BROWSER% --app=http://localhost:4173 --window-size=1600,900
) else (
  start "" http://localhost:4173
)

node server.mjs
