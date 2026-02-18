#!/bin/bash
# Run linting checks

echo "🔍 Running linting checks..."

# Install linting tools
pip install flake8 mypy

# Run flake8
echo "Running flake8..."
flake8 nemo_mqtt/ --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 nemo_mqtt/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

# Run mypy
echo "Running mypy..."
mypy nemo_mqtt/ --ignore-missing-imports

echo "✅ Linting complete!"
