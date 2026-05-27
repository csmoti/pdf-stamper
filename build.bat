@echo off
title PDF Stamper - Build to EXE
echo =====================================================
echo   PDF Stamper - Build Script
echo =====================================================
echo.

REM ── Verify Python is installed ─────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python לא נמצא.
    echo הורד מ: https://www.python.org/downloads/
    echo וודא שבחרת "Add Python to PATH" בזמן ההתקנה.
    pause
    exit /b 1
)

echo [1/3] מתקין ספריות...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] התקנת ספריות נכשלה.
    pause
    exit /b 1
)

echo.
echo [2/3] מתקין PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] התקנת PyInstaller נכשלה.
    pause
    exit /b 1
)

echo.
echo [3/3] בונה EXE...

python -m PyInstaller ^
    --name "PDF_Stamper" ^
    --windowed ^
    --onefile ^
    --clean ^
    --noconfirm ^
    app.py

if errorlevel 1 (
    echo.
    echo [ERROR] הבנייה נכשלה. בדוק את הפלט למעלה.
    pause
    exit /b 1
)

echo.
echo =====================================================
echo   הבנייה הצליחה!
echo.
echo   EXE נמצא ב:  dist\PDF_Stamper.exe
echo.
echo   !!! חשוב !!!
echo   העתק את תיקיית 'stamps' לאותו מיקום של ה-EXE
echo   (כלומר לתוך תיקיית dist\)
echo =====================================================
echo.
pause
