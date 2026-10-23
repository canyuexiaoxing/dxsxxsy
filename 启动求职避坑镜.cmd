@echo off
cd /d "%~dp0"
start "" "%~dp0.venv\Scripts\jobmirror-pythonw.exe" "%~dp0desktop.py"
