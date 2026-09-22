@echo off
REM Patch PT-BR in-place (seguro) + drop-in
cd /d "%~dp0.."
python scripts\apply_patch_inplace.py --pilot --install || exit /b 1
python scripts\verify_patch.py --pilot --patch-dir build\patch_inplace || exit /b 1
python scripts\build_dropin.py --patch-dir build\patch_inplace || exit /b 1
echo.
echo Patch instalado. Drop-in em dist\HuniePop_PT-BR
echo Se a tela ficar preta, restaure o backup em assets\original\backup_*
pause
