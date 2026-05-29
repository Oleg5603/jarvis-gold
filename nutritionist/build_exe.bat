@echo off
REM Сборка суфлёра в .exe для Windows
REM Запускать на Windows-компьютере после установки: pip install -r requirements.txt pyinstaller

pyinstaller --onefile --windowed --name "Суфлёр Нутрициолог" ^
  --add-data "knowledge_base.py;." ^
  main.py

echo.
echo Готово! Файл в папке dist\
pause
