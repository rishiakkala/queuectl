# queuectl/__init__.py
"""
QueueCTL - A CLI-based background job orchestration system.

This package provides a complete job queue system with:
- Job enqueueing and prioritization
- Worker-based execution with concurrency
- Retry logic with exponential backoff
- Dead Letter Queue (DLQ) for failed jobs
- Metrics and monitoring
- Web dashboard

Usage:
    from queuectl import JobManager, Worker
"""

__version__ = "1.0.0"
__author__ = "Rishi Akkala"
__email__ = "rishiakkala6@gmail.com"

# Make key classes easily importable
from queuectl.job_manager import JobManager
from queuectl.worker import Worker
from queuectl.database import Database

__all__ = ['JobManager', 'Worker', 'Database', '__version__']
