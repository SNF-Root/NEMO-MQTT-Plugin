#!/usr/bin/env python
"""Run tests via pytest. Use: python run_tests.py or pytest"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.test_settings')

if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main(['-v', '--tb=short'] + sys.argv[1:]))
