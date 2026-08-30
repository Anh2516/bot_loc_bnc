@echo off
REM Chay bot loc coin SHORT F1-F6 (Binance Futures)
REM - Quet moi 5 phut, bao console/CSV khi score >= 50/100
REM - Day Telegram moi coin co >= 2/6 tieu chi F1-F6 PASS
REM - Tu khoi dong lai neu bot bi crash
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo ==================================================
echo  BOT LOC COIN SHORT F1-F6 (Binance Futures)
echo  Chu ky quet : 5 phut
echo  Console/CSV : score ^>= 50/100
echo  Telegram    : ^>= 2/6 tieu chi PASS
echo  Lenh tele   : /search /top /status /start /stop
echo  Nhan Ctrl+C 2 lan de dung han
echo ==================================================
echo.

:loop
python main.py --quality %*
echo.
echo [%date% %time%] Bot da dung. Khoi dong lai sau 10 giay...
echo (Nhan Ctrl+C bay gio de thoat han)
timeout /t 10 /nobreak >nul
goto loop
