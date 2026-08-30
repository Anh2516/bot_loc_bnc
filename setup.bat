@echo off
REM ===================================================================
REM  CAI DAT BOT LOC COIN SHORT F1-F6 TREN MAY MOI
REM  Double-click file nay la xong. Chi can co Python >= 3.10.
REM ===================================================================
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo ==================================================
echo  CAI DAT BOT LOC COIN SHORT F1-F6
echo ==================================================
echo.

REM --- Buoc 1: kiem tra Python ---
echo [1/5] Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [LOI] Khong tim thay Python!
    echo.
    echo  Hay tai va cai Python 3.10 tro len tai:
    echo    https://www.python.org/downloads/
    echo.
    echo  QUAN TRONG: khi cai, tick vao o "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
python --version
echo.

REM --- Buoc 2: nang cap pip ---
echo [2/5] Nang cap pip...
python -m pip install --upgrade pip --quiet
echo      Xong.
echo.

REM --- Buoc 3: cai thu vien ---
echo [3/5] Cai thu vien tu requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [LOI] Cai thu vien that bai. Kiem tra ket noi mang roi thu lai.
    pause
    exit /b 1
)
echo.

REM --- Buoc 4: kiem tra lai ---
echo [4/5] Kiem tra import thu vien...
python -c "import requests, pypdf; print('   requests', requests.__version__); print('   pypdf   ', pypdf.__version__)"
if errorlevel 1 (
    echo  [LOI] Thu vien chua import duoc.
    pause
    exit /b 1
)
echo.

REM --- Buoc 5: kiem tra moi truong tong the ---
echo [5/5] Kiem tra moi truong va ket noi...
echo.
python check_env.py
echo.
echo ==================================================
echo  CAI DAT XONG!
echo ==================================================
echo.
echo  Buoc tiep theo:
echo.
echo   1. Mo config.py, dien TELEGRAM_BOT_TOKEN cua ban
echo      (lay tu @BotFather tren Telegram)
echo.
echo   2. Chay thu 1 vong quet:
echo        python main.py --once --quality
echo.
echo   3. Chay bot that (quet moi 5 phut):
echo        run_bot.bat
echo.
echo   4. Mo Telegram, tim bot cua ban, bam Start
echo      de nhan canh bao tu dong.
echo.
echo  Chay test de chac chan moi thu OK:
echo        python test_scoring.py
echo        python test_commands.py
echo.
pause
