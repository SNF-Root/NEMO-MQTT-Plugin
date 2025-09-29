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
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: Django",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-django>=4.0",
            "black>=22.0",
            "flake8>=4.0",
            "isort>=5.0",
        ],
        "monitoring": [
            "redis>=4.0",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="nemo mqtt django plugin iot real-time",
    entry_points={
        'console_scripts': [
            'nemo-mqtt-setup=install_nemo_integration:main',
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/SNF-Root/NEMO-MQTT-Plugin/issues",
        "Source": "https://github.com/SNF-Root/NEMO-MQTT-Plugin",
        "Documentation": "https://github.com/SNF-Root/NEMO-MQTT-Plugin#readme",
    },
)
