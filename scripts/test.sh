#!/bin/bash
# Run tests with coverage

echo "🧪 Running tests..."

# Install test dependencies
pip install -e .[dev,test]

# Run tests with coverage
pytest tests/ \
    --cov=nemo_mqtt \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-report=xml \
    -v

echo "✅ Tests complete! Coverage report available in htmlcov/"
