@echo off
rem log-stdin.cmd <label>: Windows fallback for bin/log-stdin. Appends the raw hook stdin to
rem %USERPROFILE%\.tsl-spike\log\hooks-win.log with the label. Prints nothing; exits 0.
setlocal
set "D=%USERPROFILE%\.tsl-spike\log"
if not exist "%D%" mkdir "%D%"
>>"%D%\hooks-win.log" echo === %~1 %DATE% %TIME%
findstr "^" >>"%D%\hooks-win.log"
>>"%D%\hooks-win.log" echo.
exit /b 0
