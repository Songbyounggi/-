@echo off
chcp 65001 > nul
REM 정일건설 안전관리 도우미 - Windows 실행파일(.exe) 만들기
REM Python 3.10 이상 설치 필요 (설치 시 "Add python.exe to PATH" 체크)
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || goto :err
python -m unittest discover -s tests || goto :err
python -m PyInstaller --noconfirm --onefile --windowed --name JungilSafety app.py || goto :err
echo.
echo 완료: %~dp0dist\JungilSafety.exe
pause
exit /b 0
:err
echo 빌드 실패
pause
exit /b 1
