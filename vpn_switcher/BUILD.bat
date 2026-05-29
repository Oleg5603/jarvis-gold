@echo off
echo ===================================
echo  VPN Switcher — сборка .exe
echo ===================================

:: Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден!
    pause
    exit /b 1
)

:: Установка зависимостей
echo.
echo Устанавливаю зависимости...
pip install PyQt6 pyinstaller

:: Сборка
echo.
echo Собираю VpnSwitcher.exe...
pyinstaller --onedir --noconsole --name VpnSwitcher --clean ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtWidgets ^
    --hidden-import PyQt6.QtGui ^
    main.py

if errorlevel 1 (
    echo.
    echo ОШИБКА сборки!
    pause
    exit /b 1
)

echo.
echo ===================================
echo  Готово! Папка: dist\VpnSwitcher\
echo  Запускать: VpnSwitcher.exe
echo.
echo  ВАЖНО: Запускать от Администратора
echo  (нужно для OpenVPN)
echo ===================================
pause
