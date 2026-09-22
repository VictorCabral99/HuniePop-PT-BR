@echo off
REM Captura log do HuniePop (Unity) para diagnosticar tela preta.
set LOGDIR=C:\Projetos\translate\build\logs
mkdir "%LOGDIR%" 2>nul
set LOG=%LOGDIR%\huniepop_output.log
echo Log: %LOG%
echo.
echo 1) Feche o HuniePop se estiver aberto.
echo 2) Este script abre o jogo com -logFile.
echo 3) Quando der tela preta, feche o jogo e avise no chat.
echo.
pause
"C:\Program Files (x86)\Steam\steamapps\common\HuniePop\HuniePop.exe" -logFile "%LOG%"
echo.
echo Jogo fechou. Log em:
echo %LOG%
pause
