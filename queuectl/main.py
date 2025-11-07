# queuectl/main.py
"""
QueueCTL CLI - Main entry point.
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

from queuectl.database import Database
from queuectl.job_manager import JobManager
from queuectl.worker import Worker


def cmd_init(args):
    """Initialize QueueCTL database and directories."""
    print("🔧 Initializing QueueCTL...")
    
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    
    logs_dir = data_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    db = Database()
    
    print("✅ Initialized successfully!")
    print(f"   Database: {db.db_path}")
    print(f"   Logs: {logs_dir}")


def cmd_enqueue(args):
    """Enqueue a new job - PowerShell compatible."""
    manager = JobManager()
    
    try:
        # Handle both single string and list (from nargs)
        if isinstance(args.payload, list):
            payload_str = ' '.join(args.payload)
        else:
            payload_str = args.payload
        
        # Clean up shell quote wrapping
        cleaned = payload_str.strip()
        
        # Remove outer quotes added by shell
        while cleaned and ((cleaned[0] == '"' and cleaned[-1] == '"') or 
                          (cleaned[0] == "'" and cleaned[-1] == "'")):
            cleaned = cleaned[1:-1]
        
        # Try normal JSON parsing first
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            # PowerShell likely stripped the quotes
            # Parse the broken format: {id:job1,command:echo Hello World}
            payload = parse_powershell_json(cleaned)
        
        # Validate and enqueue
        job_id = manager.enqueue(payload)
        return 0
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        print(f"\n📝 What was received:")
        print(f"   Type: {type(args.payload)}")
        print(f"   Value: {repr(args.payload)}")
        if isinstance(args.payload, list):
            print(f"   Joined: {repr(' '.join(args.payload))}")
        print(f"\n💡 For PowerShell, use DOUBLE quotes with backslash escaping:")
        print(f'   queuectl enqueue "{{\\"id\\":\\"job1\\",\\"command\\":\\"echo test\\"}}"')
        return 1
    except ValueError as e:
        print(f"❌ Validation error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def parse_powershell_json(s):
    """
    Parse PowerShell-mangled JSON where quotes were stripped.
    
    Converts: {id:job1,command:echo Hello World}
    To dict: {"id": "job1", "command": "echo Hello World"}
    """
    import re
    
    # Remove outer braces
    s = s.strip()
    if s.startswith('{') and s.endswith('}'):
        s = s[1:-1]
    
    result = {}
    
    # Simple regex to extract key:value pairs
    # This handles: key:value,key:value with spaces
    pattern = r'(\w+):([^,]+?)(?:,|$)'
    matches = re.findall(pattern, s)
    
    for key, value in matches:
        # Clean up the value
        value = value.strip()
        
        # Try to detect if it's a number
        try:
            # Try integer
            value = int(value)
        except ValueError:
            try:
                # Try float
                value = float(value)
            except ValueError:
                # It's a string - keep as-is
                pass
        
        result[key] = value
    
    return result



def cmd_list(args):
    """List jobs."""
    manager = JobManager()
    
    jobs = manager.list_jobs(state=args.state, limit=args.limit)
    
    if not jobs:
        print("📭 No jobs found")
        return 0
    
    print(f"\n📋 Jobs ({len(jobs)}):")
    print("-" * 80)
    print(f"{'ID':<20} {'State':<12} {'Priority':<8} {'Attempts':<10} {'Created':<20}")
    print("-" * 80)
    
    for job in jobs:
        print(f"{job['id']:<20} {job['state']:<12} {job['priority']:<8} "
              f"{job['attempts']}/{job['max_retries']:<8} {job['created_at']:<20}")
    
    print("-" * 80)
    return 0


def cmd_status(args):
    """Show queue status."""
    manager = JobManager()
    db = Database()
    
    summary = manager.get_status_summary()
    metrics = db.fetchone("SELECT * FROM metrics")
    
    print("\n📊 Queue Status")
    print("-" * 30)
    print(f"Pending:     {summary['pending']}")
    print(f"Processing:  {summary['processing']}")
    print(f"Completed:   {summary['completed']}")
    print(f"Failed:      {summary['failed']}")
    print(f"Dead (DLQ):  {summary['dead']}")
    print(f"Workers:     {metrics['active_workers']}")
    print("-" * 30)
    return 0


def cmd_logs(args):
    """Show job logs."""
    log_path = Path('data/logs') / f"{args.job_id}.log"
    
    if not log_path.exists():
        print(f"❌ No logs found for job '{args.job_id}'")
        return 1
    
    with open(log_path, 'r', encoding='utf-8') as f:
        print(f.read())
    
    return 0


def _run_worker(worker_id):
    """
    Worker entry point for multiprocessing.
    
    MUST be at module level (not nested) for Windows pickling.
    
    Args:
        worker_id: Unique worker identifier
    """
    worker = Worker(worker_id=worker_id)
    worker.start()


def cmd_worker_start(args):
    """Start workers."""
    count = args.count
    
    print(f"🚀 Starting {count} worker(s)... (Press Ctrl+C to stop)")
    
    if count == 1:
        # Single worker - run in foreground
        worker = Worker(worker_id=1)
        try:
            worker.start()
        except KeyboardInterrupt:
            print("\n⚠️  Shutting down...")
            worker.stop()
    else:
        # Multiple workers - use multiprocessing
        import multiprocessing
        
        # Windows requires functions to be picklable (module-level)
        processes = []
        try:
            for i in range(1, count + 1):
                p = multiprocessing.Process(target=_run_worker, args=(i,))
                p.start()
                processes.append(p)
            
            # Wait for all processes
            for p in processes:
                p.join()
        
        except KeyboardInterrupt:
            print("\n⚠️  Shutting down workers...")
            for p in processes:
                p.terminate()
            for p in processes:
                p.join()
    
    return 0



def cmd_metrics(args):
    """Show performance metrics."""
    db = Database()
    metrics = db.fetchone("SELECT * FROM metrics")
    
    print("\n📈 Metrics")
    print("-" * 30)
    print(f"Total Jobs:     {metrics['total_jobs']}")
    print(f"Completed:      {metrics['completed_jobs']}")
    print(f"Failed:         {metrics['failed_jobs']}")
    print(f"Dead:           {metrics['dead_jobs']}")
    print(f"Avg Runtime:    {metrics['avg_runtime_seconds']:.2f}s")
    print(f"Active Workers: {metrics['active_workers']}")
    print("-" * 30)
    return 0


def cmd_dlq_list(args):
    """List dead jobs."""
    manager = JobManager()
    jobs = manager.list_dlq()
    
    if not jobs:
        print("✨ DLQ is empty")
        return 0
    
    print(f"\n💀 Dead Letter Queue ({len(jobs)}):")
    print("-" * 80)
    print(f"{'ID':<20} {'Error':<40} {'Updated':<20}")
    print("-" * 80)
    
    for job in jobs:
        error = (job['error_message'] or '')[:37] + '...' if job['error_message'] and len(job['error_message']) > 40 else job['error_message'] or ''
        print(f"{job['id']:<20} {error:<40} {job['updated_at']:<20}")
    
    print("-" * 80)
    return 0


def cmd_dlq_retry(args):
    """Retry a dead job."""
    manager = JobManager()
    success = manager.retry_dlq_job(args.job_id)
    return 0 if success else 1


def cmd_config_show(args):
    """Show configuration."""
    db = Database()
    configs = db.fetchall("SELECT * FROM config ORDER BY key")
    
    print("\n⚙️  Configuration")
    print("-" * 40)
    for config in configs:
        print(f"{config['key']:<20} = {config['value']}")
    print("-" * 40)
    return 0


def cmd_config_set(args):
    """Set configuration value."""
    db = Database()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with db.transaction() as cursor:
        cursor.execute("""
            INSERT OR REPLACE INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (args.key, args.value, now))
    
    print(f"✅ Set {args.key} = {args.value}")
    return 0



def cmd_dashboard_start(args):
    """Start web dashboard."""
    print("🌐 Starting dashboard at http://localhost:5000")
    print("   Press Ctrl+C to stop")
    
    try:
        from queuectl.dashboard import app
        app.run(host='0.0.0.0', port=5000, debug=False)
    except ImportError:
        print("❌ Flask not installed. Install with: pip install flask")
        return 1
    except KeyboardInterrupt:
        print("\n⚠️  Stopping dashboard...")
        return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='queuectl',
        description='QueueCTL - A CLI-based background job orchestration system'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # init command
    subparsers.add_parser('init', help='Initialize QueueCTL')
    
    # enqueue command - MODIFIED for PowerShell compatibility
    enqueue_parser = subparsers.add_parser('enqueue', help='Enqueue a new job')
    enqueue_parser.add_argument('payload', nargs='*', help='Job payload (JSON)')
    
    # list command
    list_parser = subparsers.add_parser('list', help='List jobs')
    list_parser.add_argument('--state', help='Filter by state')
    list_parser.add_argument('--limit', type=int, default=50, help='Max jobs to show')
    
    # status command
    subparsers.add_parser('status', help='Show queue status')
    
    # logs command
    logs_parser = subparsers.add_parser('logs', help='Show job logs')
    logs_parser.add_argument('job_id', help='Job ID')
    
    # worker commands
    worker_parser = subparsers.add_parser('worker', help='Worker management')
    worker_subparsers = worker_parser.add_subparsers(dest='worker_command')
    
    worker_start_parser = worker_subparsers.add_parser('start', help='Start workers')
    worker_start_parser.add_argument('--count', type=int, default=1, help='Number of workers')
    
    # metrics command
    subparsers.add_parser('metrics', help='Show performance metrics')
    
    # dlq commands
    dlq_parser = subparsers.add_parser('dlq', help='Dead Letter Queue management')
    dlq_subparsers = dlq_parser.add_subparsers(dest='dlq_command')
    
    dlq_subparsers.add_parser('list', help='List dead jobs')
    
    dlq_retry_parser = dlq_subparsers.add_parser('retry', help='Retry a dead job')
    dlq_retry_parser.add_argument('job_id', help='Job ID')
    
    # config commands
    config_parser = subparsers.add_parser('config', help='Configuration management')
    config_subparsers = config_parser.add_subparsers(dest='config_command')
    
    config_subparsers.add_parser('show', help='Show configuration')
    
    config_set_parser = config_subparsers.add_parser('set', help='Set configuration value')
    config_set_parser.add_argument('key', help='Config key')
    config_set_parser.add_argument('value', help='Config value')
    
    # dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Dashboard management')
    dashboard_subparsers = dashboard_parser.add_subparsers(dest='dashboard_command')
    dashboard_subparsers.add_parser('start', help='Start dashboard server')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Route to appropriate command handler
    if not args.command:
        parser.print_help()
        return 1
    
    command_map = {
        'init': cmd_init,
        'enqueue': cmd_enqueue,
        'list': cmd_list,
        'status': cmd_status,
        'logs': cmd_logs,
        'metrics': cmd_metrics,
    }
    
    # Handle nested subcommands
    if args.command == 'worker':
        if args.worker_command == 'start':
            return cmd_worker_start(args)
        else:
            print("❌ Unknown worker command")
            return 1
    
    elif args.command == 'dlq':
        if args.dlq_command == 'list':
            return cmd_dlq_list(args)
        elif args.dlq_command == 'retry':
            return cmd_dlq_retry(args)
        else:
            print("❌ Unknown dlq command")
            return 1
    
    elif args.command == 'config':
        if args.config_command == 'show':
            return cmd_config_show(args)
        elif args.config_command == 'set':
            return cmd_config_set(args)
        else:
            print("❌ Unknown config command")
            return 1
    
    elif args.command == 'dashboard':
        if args.dashboard_command == 'start':
            return cmd_dashboard_start(args)
        else:
            print("❌ Unknown dashboard command")
            return 1
    
    elif args.command in command_map:
        return command_map[args.command](args)
    
    else:
        print(f"❌ Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
