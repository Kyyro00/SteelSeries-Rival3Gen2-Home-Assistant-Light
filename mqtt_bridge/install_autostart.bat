@echo off
title Instalador Rival 3 MQTT - Home Assistant
set SCRIPT_DIR=%~dp0
set VBS_PATH=%SCRIPT_DIR%start_hidden.vbs
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT=%STARTUP_DIR%\HomeAssistant_Rival3_MQTT.lnk

if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo Creando entorno virtual e instalando dependencias...
    python -m venv "%SCRIPT_DIR%.venv"
    "%SCRIPT_DIR%.venv\Scripts\python.exe" -m pip install -r "%SCRIPT_DIR%requirements.txt"
)

if not exist "%SCRIPT_DIR%config.json" (
    copy "%SCRIPT_DIR%config.example.json" "%SCRIPT_DIR%config.json" >nul
    echo [AVISO] Se ha creado mqtt_bridge\config.json. Editalo con los datos de tu broker MQTT y vuelve a ejecutar este instalador.
    pause
    exit /b 0
)

echo Cerrando instancias previas si existen...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*rival3_mqtt_bridge.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

powershell -Command "$wsh = New-Object -ComObject WScript.Shell; $sc = $wsh.CreateShortcut('%SHORTCUT%'); $sc.TargetPath = 'wscript.exe'; $sc.Arguments = '\"%VBS_PATH%\"'; $sc.Description = 'SteelSeries Rival 3 Home Assistant MQTT Bridge'; $sc.Save()"

echo Acceso directo creado en Inicio. Iniciando puente en segundo plano...
start wscript.exe "%VBS_PATH%"
pause
