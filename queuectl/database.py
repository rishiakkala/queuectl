# queuectl/database.py
"""
Database layer for QueueCTL.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

class Database:
    """Thread-safe SQLite database manager."""
    
    def __init__(self, db_path='data/queuectl.db'):
        """Initialize database connection."""
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Establish database connection with optimizations."""
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None
        )
        self.conn.row_factory = sqlite3.Row
        
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
    
    def _create_tables(self):
        """Create database schema if not exists."""
        cursor = self.conn.cursor()
        
        # Jobs table - NO default timestamps
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                priority INTEGER DEFAULT 0,
                timeout INTEGER DEFAULT 300,
                run_at TIMESTAMP,
                next_attempt_at TIMESTAMP,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                completed_at TIMESTAMP,
                output_path TEXT,
                error_message TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_worker_query 
            ON jobs(state, priority DESC, next_attempt_at, created_at)
        """)
        
        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_jobs INTEGER DEFAULT 0,
                completed_jobs INTEGER DEFAULT 0,
                failed_jobs INTEGER DEFAULT 0,
                dead_jobs INTEGER DEFAULT 0,
                avg_runtime_seconds REAL DEFAULT 0.0,
                active_workers INTEGER DEFAULT 0,
                updated_at TIMESTAMP
            )
        """)
        
        cursor.execute("SELECT COUNT(*) as count FROM metrics")
        if cursor.fetchone()['count'] == 0:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO metrics (total_jobs, completed_jobs, failed_jobs, dead_jobs, updated_at)
                VALUES (0, 0, 0, 0, ?)
            """, (now,))
        
        # Config table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP
            )
        """)
        
        default_configs = {
            'max_retries': '3',
            'backoff_base': '2',
            'default_timeout': '300',
            'default_priority': '0'
        }
        
        for key, value in default_configs.items():
            cursor.execute("""
                INSERT OR IGNORE INTO config (key, value) 
                VALUES (?, ?)
            """, (key, value))
        
        self.conn.commit()
    
    @contextmanager
    def transaction(self):
        """Context manager for atomic transactions."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
    
    def execute(self, query, params=None):
        """Execute a query and return cursor."""
        cursor = self.conn.cursor()
        if params:
            return cursor.execute(query, params)
        return cursor.execute(query)
    
    def fetchone(self, query, params=None):
        """Execute query and fetch one result."""
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def fetchall(self, query, params=None):
        """Execute query and fetch all results."""
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
