#!/usr/bin/env bash
PYTHON_EXE=${PYTHON_EXE:-python3}
VENV_DIR=${VENV_DIR:-.venv}

echo "Creating virtual environment in $VENV_DIR..."
$PYTHON_EXE -m venv "$VENV_DIR"

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip setuptools wheel

echo "Installing dependencies from requirements.txt..."
python -m pip install -r requirements.txt

echo "Environment setup complete."