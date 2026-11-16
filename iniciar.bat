@echo off
rem ======================================================================
rem  Factor Solar - arranque en Windows
rem  1. Crea (una sola vez) el entorno de Python en backend\.venv
rem  2. Instala las dependencias de Python si cambiaron
rem  3. Construye la interfaz (frontend\dist) si falta o si el codigo es mas nuevo
rem  4. Arranca el servidor en http://localhost:8000 y abre el navegador
rem  Para cerrar la app: cierra esta ventana o pulsa Ctrl+C.
rem  Variable opcional: FACTOR_SOLAR_SIN_NAVEGADOR=1 no abre el navegador.
rem ======================================================================
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "RAIZ=%CD%"
set "PUERTO=8000"

echo.
echo  Factor Solar - preparando la aplicacion
echo  ---------------------------------------

rem ---------- Python ----------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] No se encontro Python. Instala Python 3.11 o mas nuevo desde https://www.python.org
    echo         y marca "Add python.exe to PATH" durante la instalacion.
    goto :fallo
)

set "VENV=%RAIZ%\backend\.venv"
if not exist "%VENV%\Scripts\python.exe" (
    echo [1/4] Creando el entorno de Python en backend\.venv ...
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno de Python.
        goto :fallo
    )
) else (
    echo [1/4] Entorno de Python listo.
)
set "VPY=%VENV%\Scripts\python.exe"

rem Se reinstala solo si requirements.txt cambio desde la ultima instalacion.
set "REQ=%RAIZ%\backend\requirements.txt"
set "SELLO=%VENV%\requisitos-instalados.txt"
fc /b "%REQ%" "%SELLO%" >nul 2>&1
if errorlevel 1 (
    echo [2/4] Instalando dependencias de Python ^(la primera vez tarda unos minutos^) ...
    "%VPY%" -m pip install --disable-pip-version-check -q -r "%REQ%"
    if errorlevel 1 (
        echo [ERROR] Fallo la instalacion de dependencias de Python. Revisa la conexion a internet.
        goto :fallo
    )
    copy /y "%REQ%" "%SELLO%" >nul
) else (
    echo [2/4] Dependencias de Python al dia.
)

rem ---------- Interfaz (Node) ----------
set "FRONT=%RAIZ%\frontend"
set "CONSTRUIR=0"
if not exist "%FRONT%\dist\index.html" set "CONSTRUIR=1"
if "%CONSTRUIR%"=="0" (
    rem Se reconstruye si algun archivo de src, index.html o package.json es mas nuevo que dist\index.html.
    powershell -NoProfile -Command "$d=(Get-Item '%FRONT%\dist\index.html').LastWriteTime; $f=@(Get-ChildItem '%FRONT%\src' -Recurse -File) + @(Get-Item '%FRONT%\index.html','%FRONT%\package.json'); if (($f | Measure-Object LastWriteTime -Maximum).Maximum -gt $d) { exit 1 } else { exit 0 }"
    if errorlevel 1 set "CONSTRUIR=1"
)
if "%CONSTRUIR%"=="1" (
    where npm >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Hay que construir la interfaz y no se encontro Node.js.
        echo         Instala Node.js 20 o mas nuevo desde https://nodejs.org y vuelve a abrir iniciar.bat.
        goto :fallo
    )
    pushd "%FRONT%"
    if not exist "node_modules" (
        echo [3/4] Instalando dependencias de la interfaz ^(npm ci^) ...
        call npm ci --no-audit --no-fund
        if errorlevel 1 (
            echo      npm ci fallo; se intenta npm install ...
            call npm install --no-audit --no-fund
            if errorlevel 1 (
                popd
                echo [ERROR] No se pudieron instalar las dependencias de la interfaz.
                goto :fallo
            )
        )
    )
    echo [3/4] Construyendo la interfaz ^(npm run build^) ...
    call npm run build
    if errorlevel 1 (
        popd
        echo [ERROR] Fallo la construccion de la interfaz.
        goto :fallo
    )
    popd
) else (
    echo [3/4] Interfaz construida y al dia.
)

rem ---------- Servidor ----------
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %PUERTO% -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [ERROR] El puerto %PUERTO% ya esta en uso. Quiza la app ya esta abierta: prueba http://localhost:%PUERTO%
    echo         Si no, cierra el otro programa que usa ese puerto y vuelve a intentarlo.
    goto :fallo
)

echo [4/4] Arrancando el servidor en http://localhost:%PUERTO%
echo       Deja esta ventana abierta mientras usas la app. Para cerrarla: Ctrl+C o cierra la ventana.
echo.
if not "%FACTOR_SOLAR_SIN_NAVEGADOR%"=="1" (
    rem Abre el navegador cuando el servidor ya responde (espera hasta 30 s).
    start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 60; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 'http://localhost:%PUERTO%/api/salud' | Out-Null; Start-Process 'http://localhost:%PUERTO%'; break } catch { Start-Sleep -Milliseconds 500 } }"
)
pushd "%RAIZ%\backend"
"%VPY%" -m uvicorn app:app --host 127.0.0.1 --port %PUERTO%
popd
endlocal
exit /b 0

:fallo
echo.
echo No se pudo iniciar la aplicacion. Lee el mensaje de arriba.
if not "%FACTOR_SOLAR_SIN_NAVEGADOR%"=="1" pause
endlocal
exit /b 1
