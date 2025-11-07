# queuectl/worker.py
"""
Worker - Job execution engine.

Responsibilities:
- Claim jobs atomically (prevent duplicate processing)
- Execute shell commands with timeout
- Handle retries with exponential backoff
- Capture and log output
- Update metrics
"""

import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
import signal
import sys

from queuectl.database import Database
from queuectl.utils import get_log_path

class Worker:
    """
    Background worker that processes jobs from the queue.
    
    Each worker:
    1. Continuously polls for eligible jobs
    2. Claims one job atomically
    3. Executes the command with timeout
    4. Updates job state based on result
    5. Implements retry with exponential backoff
    """
    
    def __init__(self, worker_id, db=None):
        """
        Initialize worker.
        
        Args:
            worker_id: Unique worker identifier (for logging)
            db: Database instance
        """
        self.worker_id = worker_id
        self.db = db or Database()
        self.running = False
        self.backoff_base = self._get_config('backoff_base', 2)
    
    def _get_config(self, key, default):
        """Get configuration value from database."""
        row = self.db.fetchone("SELECT value FROM config WHERE key = ?", (key,))
        if row:
            try:
                return int(row['value'])
            except ValueError:
                return default
        return default
    
    def start(self):
        """
        Start the worker loop.
        
        Runs until stopped with Ctrl+C or stop() call.
        """
        self.running = True
        print(f"🚀 [Worker-{self.worker_id}] Started")
        
        # Register signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Increment active worker count
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.db.execute("""
            UPDATE metrics 
            SET active_workers = active_workers + 1,
                updated_at = ?
        """, (now,))
        self.db.conn.commit()
        
        try:
            while self.running:
                job = self._claim_next_job()
                
                if job:
                    self._process_job(job)
                else:
                    # No jobs available, wait before polling again
                    time.sleep(1)
        finally:
            # Decrement active worker count
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.db.execute("""
                UPDATE metrics 
                SET active_workers = active_workers - 1,
                    updated_at = ?
            """, (now,))
            self.db.conn.commit()
            print(f"🛑 [Worker-{self.worker_id}] Stopped")
    
    def stop(self):
        """Stop the worker gracefully."""
        self.running = False
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        print(f"\n⚠️  [Worker-{self.worker_id}] Received shutdown signal")
        self.stop()
    
    def _claim_next_job(self):
        """
        Atomically claim the next eligible job.
        
        Eligibility criteria:
        - State is 'pending' OR 'failed' (for retries)
        - next_attempt_at <= now (ready to run)
        
        Ordered by:
        - Priority DESC (higher priority first)
        - created_at ASC (FIFO within same priority)
        
        Returns:
            Job row or None if no jobs available
        """
        try:
            with self.db.transaction() as cursor:
                # Use Python's datetime (local time) instead of SQLite's datetime('now') (UTC)
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Find and claim job in one atomic operation
                cursor.execute("""
                    UPDATE jobs
                    SET state = 'processing',
                        updated_at = ?
                    WHERE id IN (
                        SELECT id FROM jobs
                        WHERE state IN ('pending', 'failed')
                          AND next_attempt_at <= ?
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                    )
                    RETURNING *
                """, (now, now))
                
                job = cursor.fetchone()
                return job
        except Exception as e:
            print(f"❌ [Worker-{self.worker_id}] Error claiming job: {e}")
            return None
    
    def _process_job(self, job):
        """
        Execute job command and handle result.
        
        Args:
            job: Job row from database
        """
        job_id = job['id']
        command = job['command']
        timeout = job['timeout']
        
        print(f"⚙️  [Worker-{self.worker_id}] Processing job '{job_id}'...")
        
        start_time = time.time()
        
        try:
            # Execute command with timeout
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            
            # Write output to log file
            self._write_log(job_id, result.returncode, result.stdout, result.stderr)
            
            if result.returncode == 0:
                # Success
                self._mark_completed(job_id, elapsed)
                print(f"✅ [Worker-{self.worker_id}] Completed job '{job_id}' in {elapsed:.2f}s")
            else:
                # Command failed (non-zero exit code)
                self._handle_failure(job, f"Command exited with code {result.returncode}")
        
        except subprocess.TimeoutExpired:
            # Job exceeded timeout
            elapsed = time.time() - start_time
            self._write_log(job_id, -1, "", f"TIMEOUT after {timeout}s")
            self._handle_failure(job, f"Timeout expired ({timeout}s)")
            print(f"⏱️  [Worker-{self.worker_id}] Job '{job_id}' timed out after {timeout}s")
        
        except Exception as e:
            # Unexpected error during execution
            elapsed = time.time() - start_time
            self._write_log(job_id, -1, "", str(e))
            self._handle_failure(job, f"Execution error: {str(e)}")
            print(f"❌ [Worker-{self.worker_id}] Job '{job_id}' failed: {e}")
    
    def _write_log(self, job_id, exit_code, stdout, stderr):
        """
        Write job output to log file.
        
        Format:
        === EXIT CODE ===
        <code>
        
        === STDOUT ===
        <output>
        
        === STDERR ===
        <errors>
        """
        log_path = get_log_path(job_id)
        
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"=== EXIT CODE ===\n{exit_code}\n\n")
            f.write(f"=== STDOUT ===\n{stdout}\n\n")
            f.write(f"=== STDERR ===\n{stderr}\n")
    
    def _mark_completed(self, job_id, elapsed_seconds):
        """
        Mark job as completed and update metrics.
        
        Args:
            job_id: Job identifier
            elapsed_seconds: Execution time
        """
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self.db.transaction() as cursor:
            cursor.execute("""
                UPDATE jobs
                SET state = 'completed',
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (now, now, job_id))
            
            # Update metrics
            cursor.execute("""
                UPDATE metrics
                SET completed_jobs = completed_jobs + 1,
                    avg_runtime_seconds = (
                        (avg_runtime_seconds * completed_jobs + ?) / (completed_jobs + 1)
                    ),
                    updated_at = ?
            """, (elapsed_seconds, now))
    
    def _handle_failure(self, job, error_message):
        """
        Handle job failure with retry logic.
        
        Flow:
        1. Increment attempts
        2. If attempts < max_retries:
           - Calculate backoff delay
           - Schedule retry
           - Mark as 'failed'
        3. If attempts >= max_retries:
           - Move to DLQ (state='dead')
        
        Args:
            job: Job row
            error_message: Failure reason
        """
        job_id = job['id']
        attempts = job['attempts'] + 1
        max_retries = job['max_retries']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self.db.transaction() as cursor:
            if attempts < max_retries:
                # Calculate exponential backoff
                delay_seconds = self.backoff_base ** attempts
                next_attempt_at = (datetime.now() + timedelta(seconds=delay_seconds)).strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute("""
                    UPDATE jobs
                    SET state = 'failed',
                        attempts = ?,
                        next_attempt_at = ?,
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (attempts, next_attempt_at, error_message, now, job_id))
                
                cursor.execute("""
                    UPDATE metrics
                    SET failed_jobs = failed_jobs + 1,
                        updated_at = ?
                """, (now,))
                
                print(f"🔄 [Worker-{self.worker_id}] Job '{job_id}' will retry in {delay_seconds}s (attempt {attempts}/{max_retries})")
            
            else:
                # Max retries exceeded - move to DLQ
                cursor.execute("""
                    UPDATE jobs
                    SET state = 'dead',
                        attempts = ?,
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (attempts, error_message, now, job_id))
                
                cursor.execute("""
                    UPDATE metrics
                    SET dead_jobs = dead_jobs + 1,
                        updated_at = ?
                """, (now,))
                
                print(f"💀 [Worker-{self.worker_id}] Job '{job_id}' moved to DLQ after {attempts} attempts")
