param(
    [string]$PythonExe = "python",
    [string]$VenvDir = ".venv"
)

Write-Host "Creating virtual environment in $VenvDir..."
$python = Get-Command $PythonExe -ErrorAction Stop
& $python.Source -m venv $VenvDir

Write-Host "Activating virtual environment..."
& "$PWD\$VenvDir\Scripts\Activate.ps1"

Write-Host "Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip setuptools wheel

Write-Host "Installing dependencies from requirements.txt..."
python -m pip install -r requirements.txt

Write-Host "Environment setup complete."