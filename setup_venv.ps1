$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".venv")) {
  Write-Host "Creando entorno virtual en .venv ..."
  python -m venv .venv
}

Write-Host "Actualizando pip e instalando dependencias (requirements.txt) ..."
& ".\\.venv\\Scripts\\python" -m pip install --upgrade pip
& ".\\.venv\\Scripts\\python" -m pip install -r ".\\requirements.txt"

Write-Host "Ejecutando test_modulos.py con el entorno virtual ..."
& ".\\.venv\\Scripts\\python" ".\\test_modulos.py"

Write-Host "Listo. Para ejecutar el sistema completo:"
Write-Host "  .\\.venv\\Scripts\\python .\\main.py"

