@echo off
chcp 65001 >nul
setlocal EnableExtensions

:: ==========================================================
::  Upgrade Mentorize Odoo 17 otomatis
::  Jalankan file ini dengan klik kanan > Run as administrator
:: ==========================================================

:: Auto minta akses Administrator jika belum admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Meminta akses Administrator...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "SERVICE_NAME=odoo-server-17.0"
set "ODOO_PYTHON=D:\odoo\python\python.exe"
set "ODOO_BIN=D:\odoo\server\odoo-bin"
set "ODOO_CONF=D:\odoo\server\odoo.conf"
set "ODOO_DB=Mentorize"
set "MODULE_NAME=mentorize"
set "ADDONS_MODULE=D:\odoo\server\odoo\addons\mentorize"

echo.
echo ==========================================================
echo  STOP SERVICE ODOO
echo ==========================================================
net stop "%SERVICE_NAME%"
echo.

echo ==========================================================
echo  HAPUS CACHE MENTORIZE
echo ==========================================================
if exist "%ADDONS_MODULE%\controllers\__pycache__" (
    rmdir /s /q "%ADDONS_MODULE%\controllers\__pycache__"
    echo Cache controllers berhasil dihapus.
) else (
    echo Cache controllers tidak ditemukan, lanjut.
)

if exist "%ADDONS_MODULE%\__pycache__" (
    rmdir /s /q "%ADDONS_MODULE%\__pycache__"
    echo Cache module berhasil dihapus.
) else (
    echo Cache module tidak ditemukan, lanjut.
)
echo.

echo ==========================================================
echo  UPGRADE MODULE MENTORIZE
echo ==========================================================
"%ODOO_PYTHON%" "%ODOO_BIN%" -c "%ODOO_CONF%" -d "%ODOO_DB%" -u "%MODULE_NAME%" --stop-after-init --dev=assets

if %errorlevel% neq 0 (
    echo.
    echo ==========================================================
    echo  UPGRADE GAGAL
    echo ==========================================================
    echo Cek error di atas. Service Odoo tidak akan dijalankan otomatis.
    pause
    exit /b %errorlevel%
)

echo.
echo ==========================================================
echo  START SERVICE ODOO
echo ==========================================================
net start "%SERVICE_NAME%"

if %errorlevel% neq 0 (
    echo.
    echo Service gagal dinyalakan. Coba jalankan manual dari Services Windows.
    pause
    exit /b %errorlevel%
)

echo.
echo ==========================================================
echo  SELESAI
echo ==========================================================
echo Mentorize sudah di-upgrade dan Odoo sudah dijalankan lagi.
echo Buka: http://localhost:8069
echo.
pause
