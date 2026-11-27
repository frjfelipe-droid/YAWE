@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Verificando bibliotecas (na primeira vez pode demorar um pouco)...
py -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo Nao foi possivel instalar as bibliotecas. Verifique sua internet e tente de novo.
  pause
  exit /b 1
)
py web.py
pause
