@echo off
echo ========================================
echo   铁路售票系统 - 一键修复同步脚本
echo ========================================
echo.

cd /d C:\Users\曹兆旺\railway-ticket-system

echo [1/4] 强制同步GitHub最新代码...
git fetch origin
git reset --hard origin/main

echo [2/4] 清理Python缓存...
cd 铁路售票系统
if exist __pycache__ rd /s /q __pycache__
if exist blueprints\register_bp\__pycache__ rd /s /q blueprints\register_bp\__pycache__

echo [3/4] 删除旧数据库（首次启动会自动重建）...
if exist data\railway.db del /f data\railway.db

echo [4/4] 启动系统...
python app.py

pause
