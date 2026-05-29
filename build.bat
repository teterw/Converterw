@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo Building Converterw.exe...
pyinstaller --onefile --windowed --name Converterw --collect-data customtkinter main.py

echo.
echo Done! Find your exe at: dist\Converterw.exe
pause
