@echo off
cd /d D:\code\ai-stock
call venv\Scripts\activate.bat
python scripts\validate_limit_threshold.py
pause
