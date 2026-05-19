@echo off
setlocal
set "ROOT=%~dp0"
set "BACKUP=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%IMPORT_PIL_BACKUP_AND_SHOW.ps1" -Backup "%BACKUP%"
