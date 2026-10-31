@echo off
if not exist "%~dp0dist\Play.cmd" (
  echo Build and package this .nen project with Node_Engine first.
  exit /b 1
)
call "%~dp0dist\Play.cmd" %*
