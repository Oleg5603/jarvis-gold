@echo off
chcp 65001 >nul
title Суфлёр Нутрициолога - Установка и Сборка

echo.
echo  ============================================
echo    Суфлёр Нутрициолога - Автосборка
echo  ============================================
echo.

REM --- Проверяем Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ОШИБКА] Python не найден на этом компьютере!
    echo.
    echo  Скачай Python 3.11 или новее:
    echo  https://www.python.org/downloads/
    echo.
    echo  При установке ОБЯЗАТЕЛЬНО поставь галочку:
    echo  "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do (
    echo  [OK] %%i найден
)

echo.
echo  Устанавливаем библиотеки...
echo  (может занять несколько минут при первом запуске)
echo.

echo  [1/5] Обновляем pip...
python -m pip install --upgrade pip --quiet --no-warn-script-location

echo  [2/5] PyQt6 (интерфейс)...
python -m pip install "PyQt6>=6.6.0" --quiet --no-warn-script-location
if errorlevel 1 (
    echo  [ОШИБКА] Не удалось установить PyQt6
    pause
    exit /b 1
)

echo  [3/5] SpeechRecognition (распознавание речи)...
python -m pip install "SpeechRecognition>=3.10.0" "requests" --quiet --no-warn-script-location

echo  [4/5] PyAudio (микрофон)...
python -m pip install pyaudio --quiet --no-warn-script-location 2>nul
if errorlevel 1 (
    echo  Пробуем альтернативный способ установки PyAudio...
    python -m pip install pipwin --quiet --no-warn-script-location
    python -m pipwin install pyaudio
    if errorlevel 1 (
        echo  [ОШИБКА] Не удалось установить PyAudio (микрофон)
        echo  Попробуй: pip install pyaudio --find-links=https://www.lfd.uci.edu/~gohlke/pythonlibs/
        pause
        exit /b 1
    )
)

echo  [5/5] PyInstaller (сборщик)...
python -m pip install "pyinstaller>=6.0.0" --quiet --no-warn-script-location

echo.
echo  ============================================
echo   Собираем .exe файл...
echo   Это займёт 3-7 минут, подожди.
echo  ============================================
echo.

REM Удаляем старую сборку если есть
if exist "dist\Sufler" rmdir /s /q "dist\Sufler"
if exist "build" rmdir /s /q "build"
if exist "Sufler.spec" del "Sufler.spec"

python -m PyInstaller ^
  --noconfirm ^
  --onedir ^
  --windowed ^
  --name "Sufler" ^
  --collect-all PyQt6 ^
  --hidden-import PyQt6.sip ^
  --hidden-import PyQt6.QtCore ^
  --hidden-import PyQt6.QtWidgets ^
  --hidden-import PyQt6.QtGui ^
  --hidden-import speech_recognition ^
  --hidden-import pyaudio ^
  --hidden-import wave ^
  --hidden-import json ^
  main.py

if errorlevel 1 (
    echo.
    echo  [ОШИБКА] Сборка не удалась!
    echo  Смотри сообщения об ошибках выше.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   ГОТОВО!
echo  ============================================
echo.
echo   Приложение находится в папке:
echo   dist\Sufler\
echo.
echo   Запускай файл:
echo   dist\Sufler\Sufler.exe
echo.
echo   Можешь скопировать папку dist\Sufler
echo   куда угодно на компьютере — она работает
echo   полностью автономно.
echo.
echo  ============================================
pause
