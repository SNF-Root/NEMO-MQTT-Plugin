#!/bin/bash
# Clean up development artifacts

echo "🧹 Cleaning up development artifacts..."

# Remove Python cache files
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove build artifacts
rm -rf build/
rm -rf dist/
rm -rf *.egg-info/
rm -rf .eggs/

# Remove test artifacts
rm -rf .pytest_cache/
rm -rf .coverage
rm -rf htmlcov/
rm -rf .mypy_cache/

# Remove virtual environment
rm -rf venv/
rm -rf .venv/

# Remove IDE files
rm -rf .vscode/
rm -rf .idea/

# Remove OS files
find . -name ".DS_Store" -delete
find . -name "Thumbs.db" -delete

echo "✅ Cleanup complete!"
