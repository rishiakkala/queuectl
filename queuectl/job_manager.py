# queuectl/job_manager.py
"""
Job Manager - High-level job operations.
"""

import json
from datetime import datetime
from queuectl.database import Database
from queuectl.utils import parse_time, validate_job_payload, get_log_path

class JobManager:
    """Manages job lifecycle operations."""
    
    def __init__(self, db=None):
        """Initialize JobManager."""
        self.db = db or Database()
    
    def enqueue(self, payload):
        """Add a job to the queue."""
        # Validate and normalize payload
        job = validate_job_payload(payload)
        
        # Extract fields with defaults
        job_id = job['id']
        command = job['command']
        priority = job.get('priority', 0)
        timeout = job.get('timeout', 300)
        max_retries = job.get('max_retries', 3)
        run_at = parse_time(job.get('run_at', 'now'))
        
        # Log path
        output_path = str(get_log_path(job_id))
        
        # Get current time
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert into database
        with self.db.transaction() as cursor:
            cursor.execute("""
                INSERT INTO jobs (
                    id, command, state, priority, timeout, 
                    max_retries, run_at, next_attempt_at, output_path,
                    created_at, updated_at
                ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, command, priority, timeout,
                max_retries, run_at.strftime('%Y-%m-%d %H:%M:%S'), 
                run_at.strftime('%Y-%m-%d %H:%M:%S'), output_path, now, now
            ))
            
            # Update metrics
            cursor.execute("""
                UPDATE metrics 
                SET total_jobs = total_jobs + 1,
                    updated_at = ?
            """, (now,))
        
        print(f"✅ Enqueued job '{job_id}' (priority={priority}, run_at={run_at.strftime('%Y-%m-%d %H:%M:%S')})")
        return job_id
    
    def get_job(self, job_id):
        """Retrieve job by ID."""
        return self.db.fetchone("""
            SELECT * FROM jobs WHERE id = ?
        """, (job_id,))
    
    def list_jobs(self, state=None, limit=50):
        """List jobs, optionally filtered by state."""
        if state:
            return self.db.fetchall("""
                SELECT * FROM jobs 
                WHERE state = ?
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (state, limit))
        else:
            return self.db.fetchall("""
                SELECT * FROM jobs 
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (limit,))
    
    def update_job_state(self, job_id, new_state, error_message=None):
        """Update job state."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self.db.transaction() as cursor:
            if new_state == 'completed':
                cursor.execute("""
                    UPDATE jobs 
                    SET state = ?, 
                        completed_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (new_state, now, now, job_id))
            elif error_message:
                cursor.execute("""
                    UPDATE jobs 
                    SET state = ?, 
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (new_state, error_message, now, job_id))
            else:
                cursor.execute("""
                    UPDATE jobs 
                    SET state = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (new_state, now, job_id))
    
    def get_status_summary(self):
        """Get queue status summary."""
        row = self.db.fetchone("""
            SELECT 
                SUM(CASE WHEN state = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN state = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN state = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN state = 'dead' THEN 1 ELSE 0 END) as dead
            FROM jobs
        """)
        
        return {
            'pending': row['pending'] or 0,
            'processing': row['processing'] or 0,
            'completed': row['completed'] or 0,
            'failed': row['failed'] or 0,
            'dead': row['dead'] or 0
        }
    
    def move_to_dlq(self, job_id):
        """Move job to Dead Letter Queue."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self.db.transaction() as cursor:
            cursor.execute("""
                UPDATE jobs 
                SET state = 'dead',
                    updated_at = ?
                WHERE id = ?
            """, (now, job_id))
            
            cursor.execute("""
                UPDATE metrics 
                SET dead_jobs = dead_jobs + 1,
                    updated_at = ?
            """, (now,))
        
        print(f"💀 Moved job '{job_id}' to DLQ")
    
    def retry_dlq_job(self, job_id):
        """Retry a job from DLQ."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self.db.transaction() as cursor:
            cursor.execute("""
                UPDATE jobs 
                SET state = 'pending',
                    attempts = 0,
                    next_attempt_at = ?,
                    updated_at = ?,
                    error_message = NULL
                WHERE id = ? AND state = 'dead'
            """, (now, now, job_id))
            
            if cursor.rowcount == 0:
                print(f"❌ Job '{job_id}' not found in DLQ")
                return False
            
            cursor.execute("""
                UPDATE metrics 
                SET dead_jobs = dead_jobs - 1,
                    updated_at = ?
            """, (now,))
        
        print(f"🔄 Retrying job '{job_id}' from DLQ")
        return True
    
    def list_dlq(self):
        """List all jobs in Dead Letter Queue."""
        return self.db.fetchall("""
            SELECT * FROM jobs 
            WHERE state = 'dead'
            ORDER BY updated_at DESC
        """)
