# setup.py
"""
QueueCTL packaging configuration.

This file tells pip how to install queuectl as a global command.

Key concept: The 'entry_points' section creates a launcher script
that runs queuectl.main:main() when you type 'queuectl'.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read long description from README
readme_file = Path(__file__).parent / 'README.md'
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ''

setup(
    name='queuectl',
    version='1.0.0',
    description='A CLI-based background job orchestration system',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/queuectl',
    
    # Find all packages (automatically discovers queuectl/)
    packages=find_packages(),
    
    # Python version requirement
    python_requires='>=3.8',
    
    # Dependencies
    install_requires=[
        # No external dependencies for core functionality
        # Flask is optional (only for dashboard)
    ],
    
    # Optional dependencies
    extras_require={
        'dashboard': ['flask>=2.0.0'],
        'dev': ['pytest', 'black', 'flake8'],
    },
    
    # ⭐ THIS IS THE KEY PART ⭐
    # Creates a global command 'queuectl' that runs main() from queuectl/main.py
    entry_points={
        'console_scripts': [
            'queuectl=queuectl.main:main',
        ],
    },
    
    # Package metadata
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    
    # Keywords for PyPI search
    keywords='cli job queue background-jobs celery worker scheduler',
    
    # Include non-Python files
    include_package_data=True,
)
