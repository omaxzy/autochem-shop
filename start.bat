@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Installing...
pip install flask flask-sqlalchemy pillow
echo.
echo STARTING SHOP
echo Shop: http://localhost:5000
echo Admin: http://localhost:5000/admin
echo.
python app.py
pause