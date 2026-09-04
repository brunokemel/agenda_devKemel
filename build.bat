@echo off
pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean agenda.spec
echo.
echo Executavel gerado em dist\AgendaOneNote.exe
pause
