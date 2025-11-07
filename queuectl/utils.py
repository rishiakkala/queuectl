# queuectl/utils.py
"""
Utility functions for QueueCTL.
"""

from datetime import datetime
from pathlib import Path
import json


def parse_time(time_str):
    """
    Parse ISO 8601 timestamp string into datetime object.
    
    Supported formats:
    - ISO 8601 with timezone: "2025-11-05T15:00:00Z"
    - ISO 8601 without timezone: "2025-11-05T15:00:00"
    - Simple date-time: "2025-11-05 15:00:00"
    - None or "now": Current time
    
    Args:
        time_str: ISO 8601 timestamp string or "now"
        
    Returns:
        datetime object (timezone-naive, local time)
        
    Examples:
        >>> parse_time("2025-11-05T15:00:00Z")
        datetime(2025, 11, 5, 15, 0, 0)
        
        >>> parse_time("now")
        datetime(2025, 11, 7, 14, 37, 0)
        
    Raises:
        ValueError: If timestamp format is invalid
    """
    if not time_str or time_str.lower() == 'now':
        return datetime.now()
    
    # Remove timezone suffix if present (we work in local time)
    if time_str.endswith('Z'):
        time_str = time_str[:-1]
    
    # Try ISO 8601 format: 2025-11-05T15:00:00
    try:
        return datetime.fromisoformat(time_str)
    except ValueError:
        pass
    
    # Try space-separated format: 2025-11-05 15:00:00
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass
    
    # If all formats fail, raise error
    raise ValueError(
        f"Invalid timestamp format: '{time_str}'. "
        f"Use ISO 8601 format: '2025-11-05T15:00:00' or 'now'"
    )


def validate_job_payload(payload):
    """
    Validate job JSON payload.
    
    Required fields:
    - id: Unique job identifier (string)
    - command: Shell command to execute (string)
    
    Optional fields:
    - priority: Integer (default: 0)
    - timeout: Execution timeout in seconds (default: 300)
    - max_retries: Maximum retry attempts (default: 3)
    - run_at: ISO 8601 timestamp or "now" (default: "now")
    
    Args:
        payload: Dictionary or JSON string
        
    Returns:
        dict: Validated and normalized payload
        
    Raises:
        ValueError: If validation fails
        
    Examples:
        >>> validate_job_payload('{"id":"job1","command":"echo test"}')
        {'id': 'job1', 'command': 'echo test'}
        
        >>> validate_job_payload({
        ...     "id": "job1",
        ...     "command": "python script.py",
        ...     "run_at": "2025-11-05T15:00:00Z"
        ... })
        {'id': 'job1', 'command': 'python script.py', 'run_at': '2025-11-05T15:00:00Z'}
    """
    # Parse JSON if string
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    # Check required fields
    if 'id' not in payload:
        raise ValueError("Missing required field: 'id'")
    if 'command' not in payload:
        raise ValueError("Missing required field: 'command'")
    
    # Validate types
    if not isinstance(payload['id'], str):
        raise ValueError("'id' must be a string")
    if not isinstance(payload['command'], str):
        raise ValueError("'command' must be a string")
    
    # Validate optional fields
    if 'priority' in payload:
        if not isinstance(payload['priority'], int):
            raise ValueError("'priority' must be an integer")
    
    if 'timeout' in payload:
        if not isinstance(payload['timeout'], int) or payload['timeout'] <= 0:
            raise ValueError("'timeout' must be a positive integer")
    
    if 'max_retries' in payload:
        if not isinstance(payload['max_retries'], int) or payload['max_retries'] < 0:
            raise ValueError("'max_retries' must be a non-negative integer")
    
    # Validate run_at format if provided
    if 'run_at' in payload:
        try:
            parse_time(payload['run_at'])
        except ValueError as e:
            raise ValueError(f"Invalid 'run_at' format: {e}")
    
    return payload


def format_duration(seconds):
    """
    Format duration in seconds to human-readable string.
    
    Examples:
        >>> format_duration(65)
        "1m 5s"
        
        >>> format_duration(3665)
        "1h 1m 5s"
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


def ensure_log_directory():
    """
    Ensure the logs directory exists.
    
    Creates: data/logs/
    """
    log_dir = Path('data/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_path(job_id):
    """
    Get the log file path for a job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Path object: data/logs/<job_id>.log
    """
    ensure_log_directory()
    return Path('data/logs') / f"{job_id}.log"
