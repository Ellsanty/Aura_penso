@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python314\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
echo Preparando dependencias de AURA...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Creando icono de Windows...
"%PYTHON_EXE%" -c "from PIL import Image,ImageDraw; im=Image.new('RGBA',(256,256),'#090D18'); d=ImageDraw.Draw(im); d.ellipse((16,16,240,240),fill='#8978FF'); d.polygon([(128,50),(184,199),(153,199),(143,171),(113,171),(103,199),(72,199)],fill='white'); d.rounded_rectangle((117,143,139,156),radius=4,fill='#8978FF'); im.save('logo-aura.ico',sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])"
if errorlevel 1 goto error
echo Empaquetando AURA...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --windowed --onefile --name AURA --icon logo-aura.ico --collect-all groq --collect-all customtkinter --collect-all winotify --collect-all pystray asistente_local.py
if errorlevel 1 goto error
echo.
echo Listo: dist\AURA.exe
pause
exit /b 0
:error
echo.
echo No se pudo completar. Revisa la instalacion de Python y la conexion a Internet.
pause
exit /b 1
