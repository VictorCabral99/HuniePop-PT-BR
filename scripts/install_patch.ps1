# Patch SEGURO apenas (in-place). Nao use expand — causa tela preta.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

python scripts/apply_patch_inplace.py --pilot --install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/build_dropin.py --patch-dir build/patch_inplace
Write-Host "Patch UI in-place instalado. Expand esta desativado (tela preta)."
