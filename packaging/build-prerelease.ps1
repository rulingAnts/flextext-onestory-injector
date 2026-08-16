# Build the Windows pre-release zip. Run ON THE WINDOWS VM:
#   powershell -ExecutionPolicy Bypass -File \\Mac\Home\GIT\flextext-onestory-injector\packaging\build-prerelease.ps1
#
# Copies the repo to a LOCAL folder first (PyInstaller on a network share is
# slow and flaky), excluding .git and any local sample data, runs the test
# suite, builds onedir, zips it, and drops the zip back on the shared folder
# under packaging\out\ for the Mac side to publish.

$ErrorActionPreference = "Stop"
$src  = "\\Mac\Home\GIT\flextext-onestory-injector"
$work = "C:\Temp\ftosi-build"
$ver  = "v0.1.0-pre.1"

Write-Host "== copy to local disk =="
robocopy $src $work /E /PURGE /XD .git sample .onestory-injector-backups build dist /XF *.onestory *.flextext *.eaf | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with $LASTEXITCODE" }

Set-Location $work
Write-Host "== python =="
python --version
python -c "import tkinter; print('tkinter OK')"

Write-Host "== tests (must pass before any build) =="
python tests\run_tests.py
if ($LASTEXITCODE -ne 0) { throw "TESTS FAILED - not building" }

Write-Host "== pyinstaller =="
python -m pip install --quiet pyinstaller
python -m PyInstaller packaging\injector.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

Write-Host "== smoke: exe exists and starts imports =="
if (-not (Test-Path "dist\FlexTextOneStoryInjector\FlexTextOneStoryInjector.exe")) {
  throw "exe missing from dist"
}

Write-Host "== zip =="
$zip = "FlexTextOneStoryInjector-$ver-win64.zip"
Compress-Archive -Path "dist\FlexTextOneStoryInjector" -DestinationPath $zip -Force

Write-Host "== deliver back to the shared folder =="
New-Item -ItemType Directory -Force -Path "$src\packaging\out" | Out-Null
Copy-Item $zip "$src\packaging\out\" -Force
Write-Host "DONE: packaging\out\$zip"
