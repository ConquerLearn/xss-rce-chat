@echo off
rem Wrapper: runs the QQ XSS payload sender with execution policy bypass.
rem Pre-req: log into 小号, open the 小号<->主号 chat, focus the input box.
rem After you type "yes", click into the QQ input within 6 seconds.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0send_qq_xss.ps1"
pause
