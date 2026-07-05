@echo off
setlocal
set CMAKE="C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
set BUILD_DIR=%~dp0build

echo === Build ===
%CMAKE% --build "%BUILD_DIR%" --config Release
if %ERRORLEVEL% neq 0 (
    echo.
    echo BLAD BUDOWANIA! Sprawdz bledy powyzej.
    pause
    exit /b 1
)

echo.
echo === Deploy ===
powershell -ExecutionPolicy Bypass -File "%~dp0deploy.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo BLAD DEPLOYU!
    pause
    exit /b 1
)

echo.
echo === Gotowe! ===
