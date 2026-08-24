@echo off
chcp 65001 >nul
title Одна Друга — Beta v24
echo.
echo ==========================================
echo      Одна Друга — Beta v24
echo ==========================================
echo.
echo Запуск production-сервера Waitress...
echo Откройте в браузере: http://127.0.0.1:8000
echo Для остановки нажмите Ctrl+C.
echo.
py serve_beta.py
pause
