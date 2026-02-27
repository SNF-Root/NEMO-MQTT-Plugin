#!/usr/bin/env python3
"""
Setup script for NEMO MQTT Plugin
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="nemo-mqtt-plugin",
    version="1.0.0",
    author="SNF-Root",
    author_email="alexdenton998@gmail.com",
    description="MQTT integration plugin for NEMO tool usage events",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/SNF-Root/NEMO-MQTT-Plugin",
    packages=find_packages(),
    package_data={
        'nemo_mqtt': [
            'templates/**/*',
            'migrations/**/*',
            '*.txt',
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires=">=3.8",
    install_requires=[
        "paho-mqtt>=1.6.1",
        "Django>=3.2",
        "redis>=4.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-django>=4.0",
            "pytest-cov>=3.0",
            "black>=22.0",
            "flake8>=4.0",
            "isort>=5.0",
            "mypy>=0.900",
        ],
        "test": [
            "pytest>=6.0",
            "pytest-django>=4.0",
            "pytest-cov>=3.0",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="nemo mqtt django plugin iot real-time monitoring",
    entry_points={
        'console_scripts': [
            'nemo-mqtt-setup=nemo_mqtt.management.commands.setup_nemo_integration:main',
        ],
    },
    project_urls={
        "Homepage": "https://github.com/SNF-Root/NEMO-MQTT-Plugin",
        "Bug Reports": "https://github.com/SNF-Root/NEMO-MQTT-Plugin/issues",
        "Source": "https://github.com/SNF-Root/NEMO-MQTT-Plugin",
        "Documentation": "https://github.com/SNF-Root/NEMO-MQTT-Plugin#readme",
        "Changelog": "https://github.com/SNF-Root/NEMO-MQTT-Plugin/blob/main/CHANGELOG.md",
    },
)
