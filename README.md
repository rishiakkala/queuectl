# QueueCTL

<div align="center">

**A Professional CLI-Based Background Job Orchestration System**

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)](https://www.microsoft.com/windows)

[Demo Video](#-demo-video) • [Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Documentation](#-documentation)

</div>

---

## 📺 Demo Video

Watch QueueCTL in action! This video demonstrates all major features including concurrent workers, priority queues, retry mechanisms, and real-time monitoring.

**▶️ [Click here to watch the demo video]([https://your-video-link-here.com](https://drive.google.com/file/d/1seo_7GdMnpIttjEhjwhRpnaDUZQjKf_o/view?usp=sharing))**

---

## 🎯 What is QueueCTL?

**QueueCTL** is a production-ready, CLI-based **background job orchestration system** built with Python. It provides a complete solution for managing and executing background jobs with features like:

- 🔄 **Persistent Job Queue** - Jobs are stored in SQLite database and survive system restarts
- ⚡ **Concurrent Processing** - Multiple workers can process jobs in parallel
- 🎯 **Priority-Based Execution** - High-priority jobs run first
- 🔁 **Automatic Retries** - Failed jobs retry automatically with exponential backoff
- 💀 **Dead Letter Queue** - Permanently failed jobs are isolated for manual review
- 📊 **Real-Time Monitoring** - Track job status, metrics, and logs
- 🌐 **Web Dashboard** - Optional Flask-based web interface

### Why QueueCTL?

Traditional background job systems like Celery or Redis Queue require complex infrastructure. **QueueCTL** provides a lightweight, self-contained solution perfect for:

- **Local development** and testing
- **Single-machine deployments**
- **Windows environments** where Unix-based tools are unavailable
- **Learning and experimentation** with job queue systems
- **Small to medium-scale** background processing needs

---

## ✨ Features

### Core Features

✅ **Persistent Job Queue**
- All jobs stored in SQLite database (`data/queuectl.db`)
- **Jobs survive system restarts** - no data loss on crash or reboot
- Atomic job claiming prevents duplicate processing
- ACID-compliant transactions ensure data integrity

✅ **Concurrent Worker Processing**
- Run multiple workers simultaneously for parallel execution
- Each worker claims jobs atomically (no race conditions)
- Configurable worker count based on CPU cores or workload

✅ **Priority Queue System**
- Jobs with higher priority execute first
- Supports positive and negative priorities
- FIFO ordering within the same priority level

✅ **Automatic Retry Mechanism**
- Failed jobs retry automatically with exponential backoff
- Configurable retry limits (default: 3 attempts)
- Backoff delays: 2s, 4s, 8s, 16s, 32s... (configurable base)

✅ **Dead Letter Queue (DLQ)**
- Permanently failed jobs move to DLQ after max retries
- Failed jobs can be retried manually from DLQ
- Prevents problematic jobs from blocking the queue

✅ **Comprehensive Monitoring**
- Real-time queue status (pending, processing, completed, failed, dead)
- Performance metrics (completion rate, average runtime)
- Detailed job logs with stdout, stderr, and exit codes

✅ **Scheduled Jobs**
- Schedule jobs to run at specific times using ISO 8601 timestamps
- Support for delayed execution (run_at parameter)

✅ **Web Dashboard** (Optional)
- Real-time visualization of job queue
- Filter jobs by state
- Auto-refresh every 3 seconds
- Accessible at `http://localhost:5000`

---

## 🏗️ How It Works

### Architecture Overview

```
┌─────────────┐
│   CLI User  │
└──────┬──────┘
       │ queuectl enqueue
       ▼
┌─────────────────────────────────────┐
│          SQLite Database            │
│  ┌─────────────────────────────┐   │
│  │  Jobs Table                 │   │
│  │  - id (unique)              │   │
│  │  - command                  │   │
│  │  - state (pending/processing│   │
│  │           /completed/failed │   │
│  │           /dead)            │   │
│  │  - priority                 │   │
│  │  - attempts                 │   │
│  │  - next_attempt_at          │   │
│  │  - created_at / updated_at  │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
       ▲
       │ Atomic Claim (SELECT ... FOR UPDATE)
       │
┌──────┴────────────────────────────┐
│        Worker Processes           │
│  ┌──────────┐  ┌──────────┐      │
│  │ Worker-1 │  │ Worker-2 │ ...  │
│  └──────────┘  └──────────┘      │
│       │              │            │
│       ▼              ▼            │
│  Execute       Execute            │
│  Command       Command            │
│       │              │            │
│       ▼              ▼            │
│  Update Job    Update Job         │
│  State         State              │
└───────────────────────────────────┘
```

### Job Lifecycle

```
 ┌─────────┐
 │ pending │  ← Job enqueued
 └────┬────┘
      │ Worker claims job
      ▼
 ┌────────────┐
 │ processing │  ← Job executing
 └─────┬──────┘
       │
       ├─ Success ──────────────┐
       │                        ▼
       │                   ┌───────────┐
       │                   │ completed │  ← Job succeeded
       │                   └───────────┘
       │
       ├─ Failure ──────────────┐
       │                        ▼
       │                   ┌────────┐
       │                   │ failed │  ← Retrying...
       │                   └───┬────┘
       │                       │
       │  ┌────────────────────┘
       │  │ (attempts < max_retries)
       │  │
       │  └─ Retry after backoff delay ─────┐
       │                                     │
       │  ┌──────────────────────────────────┘
       │  ▼
       │  Back to 'processing'
       │
       └─ Max retries exceeded ───┐
                                  ▼
                             ┌────────┐
                             │  dead  │  ← Moved to DLQ
                             └────────┘
```

### Key Concepts

1. **Atomic Job Claiming**
   - Workers use SQL transactions with `UPDATE ... WHERE id IN (SELECT ... LIMIT 1) RETURNING *`
   - Only one worker can claim a job at a time
   - Prevents race conditions in multi-worker scenarios

2. **Exponential Backoff**
   - Failed jobs retry with increasing delays: `delay = backoff_base ^ attempt_number`
   - Default: 2^1 = 2s, 2^2 = 4s, 2^3 = 8s
   - Prevents overwhelming failing services

3. **Persistent State**
   - All job data stored in SQLite with WAL mode
   - **System restart safe** - workers can restart and continue processing
   - Database survives crashes, power loss, or manual shutdowns

4. **Priority Scheduling**
   - Jobs ordered by: `priority DESC, created_at ASC`
   - Higher priority jobs execute first
   - Same-priority jobs execute in FIFO order

---

## 📋 Prerequisites

- **Python 3.8 or higher** (tested on 3.9, 3.10, 3.11, 3.13)
- **Windows 10/11** (PowerShell or Command Prompt)
- **pip** package manager
- **(Optional) Flask** for web dashboard

---

## 🚀 Installation

### Step 1: Clone or Download the Project

```powershell
# Using Git
git clone https://github.com/yourusername/queuectl.git
cd queuectl

# Or download ZIP and extract, then navigate to folder
cd path\to\queuectl
```

### Step 2: Create Virtual Environment

**PowerShell:**

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# If you get execution policy error:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1

# You should see (venv) in your prompt
```

**Command Prompt:**

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### Step 3: Install QueueCTL

```powershell
# Install in editable mode (recommended for development)
pip install -e .

# Or install normally
pip install .
```

### Step 4: Verify Installation

```powershell
# Check if queuectl command is available
queuectl --help
```

**Expected Output:**
```
usage: queuectl [-h] {init,enqueue,list,status,logs,worker,metrics,dlq,config,dashboard} ...

QueueCTL - A CLI-based background job orchestration system

positional arguments:
  {init,enqueue,list,status,logs,worker,metrics,dlq,config,dashboard}
    init                Initialize QueueCTL
    enqueue             Enqueue a new job
    list                List jobs
    status              Show queue status
    logs                Show job logs
    worker              Worker management
    metrics             Show performance metrics
    dlq                 Dead Letter Queue management
    config              Configuration management
    dashboard           Dashboard management

optional arguments:
  -h, --help            show this help message and exit
```

### Step 5: Initialize Database

```powershell
queuectl init
```

**Output:**
```
🔧 Initializing QueueCTL...
✅ Initialized successfully!
   Database: data/queuectl.db
   Logs: data\logs
```

### Step 6: (Optional) Install Dashboard

```powershell
pip install flask
```

---

## 🎬 Quick Start

### 1. Add Jobs to Queue

```powershell
# Simple job
queuectl enqueue '{"id":"job1","command":"echo Hello World"}'

# Job with priority
queuectl enqueue '{"id":"urgent","command":"echo High Priority","priority":10}'

# Job with custom timeout and retries
queuectl enqueue '{"id":"complex","command":"python script.py","timeout":600,"max_retries":5,"priority":5}'
```

### 2. View Jobs

```powershell
# List all jobs
queuectl list

# Filter by state
queuectl list --state pending
queuectl list --state completed
```

### 3. Start Workers

```powershell
# Single worker (sequential processing)
queuectl worker start

# Multiple workers (parallel processing)
queuectl worker start --count 3
```

**Stop workers:** Press `Ctrl+C`

### 4. Monitor Progress

```powershell
# Check queue status
queuectl status

# View metrics
queuectl metrics

# View job logs
queuectl logs job1
```

---

## 📖 Complete Command Reference

### Job Management

#### `queuectl enqueue`

Add a job to the queue.

**Format:**
```powershell
queuectl enqueue '{"id":"<job_id>","command":"<shell_command>"}'
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | ✅ Yes | - | Unique job identifier |
| `command` | string | ✅ Yes | - | Shell command to execute |
| `priority` | integer | No | 0 | Job priority (higher = executes first) |
| `timeout` | integer | No | 300 | Timeout in seconds |
| `max_retries` | integer | No | 3 | Maximum retry attempts |
| `run_at` | string | No | "now" | ISO 8601 timestamp or "now" |

**Examples:**

```powershell
# Basic job
queuectl enqueue '{"id":"task1","command":"echo Hello"}'

# High priority job
queuectl enqueue '{"id":"urgent","command":"python urgent.py","priority":10}'

# Job with all options
queuectl enqueue '{"id":"complete","command":"python process.py","priority":5,"timeout":600,"max_retries":5,"run_at":"2025-11-08T10:00:00"}'
```

---

#### `queuectl list`

List jobs in the queue.

**Usage:**
```powershell
queuectl list [--state STATE] [--limit LIMIT]
```

**Options:**
- `--state` - Filter by job state (pending, processing, completed, failed, dead)
- `--limit` - Maximum number of jobs to display (default: 50)

**Examples:**

```powershell
# List all jobs
queuectl list

# List pending jobs
queuectl list --state pending

# List completed jobs (last 20)
queuectl list --state completed --limit 20
```

**Output:**
```
📋 Jobs (5):
--------------------------------------------------------------------------------
ID                   State        Priority Attempts   Created
--------------------------------------------------------------------------------
urgent               pending      10       0/3        2025-11-07 18:40:52
job1                 completed    0        0/3        2025-11-07 18:40:45
task1                processing   0        0/3        2025-11-07 18:41:00
failing              failed       0        2/3        2025-11-07 18:41:10
dead-job             dead         0        3/3        2025-11-07 18:41:20
--------------------------------------------------------------------------------
```

---

#### `queuectl status`

Show queue status summary.

**Usage:**
```powershell
queuectl status
```

**Output:**
```
📊 Queue Status
------------------------------
Pending:     3
Processing:  1
Completed:   10
Failed:      2
Dead (DLQ):  1
Workers:     2
------------------------------
```

---

#### `queuectl logs`

View job output logs.

**Usage:**
```powershell
queuectl logs <job_id>
```

**Example:**
```powershell
queuectl logs job1
```

**Output:**
```
=== EXIT CODE ===
0

=== STDOUT ===
Hello World

=== STDERR ===

```

---

### Worker Management

#### `queuectl worker start`

Start worker(s) to process jobs.

**Usage:**
```powershell
queuectl worker start [--count COUNT]
```

**Options:**
- `--count` - Number of workers to start (default: 1)

**Examples:**

```powershell
# Single worker
queuectl worker start

# Three workers (parallel processing)
queuectl worker start --count 3
```

**Output:**
```
🚀 Starting 3 worker(s)... (Press Ctrl+C to stop)
🚀 [Worker-1] Started
🚀 [Worker-2] Started
🚀 [Worker-3] Started
⚙️  [Worker-1] Processing job 'urgent'...
⚙️  [Worker-2] Processing job 'job1'...
⚙️  [Worker-3] Processing job 'task1'...
✅ [Worker-2] Completed job 'job1' in 0.05s
✅ [Worker-1] Completed job 'urgent' in 0.06s
✅ [Worker-3] Completed job 'task1' in 0.08s
```

**Stop workers:** Press `Ctrl+C`

---

### Monitoring

#### `queuectl metrics`

Show performance metrics.

**Usage:**
```powershell
queuectl metrics
```

**Output:**
```
📈 Metrics
------------------------------
Total Jobs:     15
Completed:      12
Failed:         2
Dead:           1
Avg Runtime:    1.45s
Active Workers: 3
------------------------------
```

---

### Dead Letter Queue (DLQ)

#### `queuectl dlq list`

List jobs in Dead Letter Queue.

**Usage:**
```powershell
queuectl dlq list
```

**Output:**
```
💀 Dead Letter Queue (2):
--------------------------------------------------------------------------------
ID                   Error                                    Updated
--------------------------------------------------------------------------------
failing-job          Command exited with code 1               2025-11-07 18:45:30
timeout-job          Timeout expired (300s)                   2025-11-07 18:46:15
--------------------------------------------------------------------------------
```

---

#### `queuectl dlq retry`

Retry a job from DLQ.

**Usage:**
```powershell
queuectl dlq retry <job_id>
```

**Example:**
```powershell
queuectl dlq retry failing-job
```

**Output:**
```
🔄 Retrying job 'failing-job' from DLQ
```

---

### Configuration

#### `queuectl config show`

Show current configuration.

**Usage:**
```powershell
queuectl config show
```

**Output:**
```
⚙️  Configuration
----------------------------------------
backoff_base         = 2
default_priority     = 0
default_timeout      = 300
max_retries          = 3
----------------------------------------
```

---

#### `queuectl config set`

Update configuration.

**Usage:**
```powershell
queuectl config set <key> <value>
```

**Examples:**

```powershell
# Increase max retries
queuectl config set max_retries 5

# Change backoff base (retry delays)
queuectl config set backoff_base 3

# Set default timeout to 10 minutes
queuectl config set default_timeout 600
```

---

### Web Dashboard

#### `queuectl dashboard start`

Start web dashboard server.

**Usage:**
```powershell
queuectl dashboard start
```

**Output:**
```
🌐 Starting dashboard at http://localhost:5000
   Press Ctrl+C to stop
 * Running on http://127.0.0.1:5000
```

**Access:** Open browser to `http://localhost:5000`

**Features:**
- Real-time job status updates
- Filter by job state
- View metrics and logs
- Auto-refresh every 3 seconds

---

## 🔄 Persistence & Restart Behavior

### Jobs Survive System Restarts

**QueueCTL stores all job data in a persistent SQLite database (`data/queuectl.db`). This means:**

✅ **Jobs are NOT lost on system restart**
- Pending jobs remain in the queue
- Failed jobs retain their retry count and next attempt time
- Completed jobs remain in the database for auditing

✅ **Workers can be stopped and restarted**
- Stop workers with `Ctrl+C` at any time
- Restart workers later - they'll continue processing from where they left off
- No data loss or duplicate processing

✅ **Database survives crashes**
- SQLite with WAL mode ensures ACID compliance
- System crashes don't corrupt the database
- Jobs in "processing" state can be reset manually if needed

### Example Scenario

```powershell
# Day 1: Add jobs and start processing
queuectl enqueue '{"id":"job1","command":"echo Task 1"}'
queuectl enqueue '{"id":"job2","command":"echo Task 2"}'
queuectl enqueue '{"id":"job3","command":"echo Task 3"}'
queuectl worker start

# Job1 and Job2 complete, Job3 still processing...
# Press Ctrl+C or system crashes

# Day 2: Restart worker
queuectl worker start

# Worker continues processing Job3 and any remaining jobs!
# No jobs are lost!
```

### Checking Job Status After Restart

```powershell
# View all jobs (including completed ones)
queuectl list

# Check specific job status
queuectl list --state pending
queuectl list --state completed
```

---

## 🎯 Use Cases

### 1. Data Processing Pipeline

```powershell
# Extract, Transform, Load workflow
queuectl enqueue '{"id":"extract","command":"python extract_data.py","priority":10}'
queuectl enqueue '{"id":"transform","command":"python transform_data.py","priority":5}'
queuectl enqueue '{"id":"load","command":"python load_data.py","priority":1}'

# Process in order with single worker
queuectl worker start
```

### 2. Batch Processing

```powershell
# Process 100 files in parallel
for ($i=1; $i -le 100; $i++) {
    queuectl enqueue "{`"id`":`"file-$i`",`"command`":`"python process.py --file data/$i.csv`"}"
}

# Process with 10 workers
queuectl worker start --count 10
```

### 3. Scheduled Tasks

```powershell
# Schedule backup for midnight
$time = "2025-11-08T00:00:00"
queuectl enqueue "{`"id`":`"backup`",`"command`":`"python backup.py`",`"run_at`":`"$time`"}"

# Start worker (waits until midnight)
queuectl worker start
```

### 4. CI/CD Pipeline

```powershell
# Build, test, deploy
queuectl enqueue '{"id":"build","command":"python build.py","priority":10}'
queuectl enqueue '{"id":"test","command":"python test.py","priority":5}'
queuectl enqueue '{"id":"deploy","command":"python deploy.py","priority":1}'

queuectl worker start
```

---

## 🗂️ Project Structure

```
queuectl/
├── queuectl/                    # Main Python package
│   ├── __init__.py             # Package initialization
│   ├── main.py                 # CLI commands and entry point
│   ├── database.py             # SQLite operations
│   ├── job_manager.py          # Job CRUD operations
│   ├── worker.py               # Job execution engine
│   ├── dashboard.py            # Flask web dashboard
│   └── utils.py                # Helper functions
│
├── data/                        # Runtime data (created on init)
│   ├── queuectl.db             # SQLite database
│   └── logs/                   # Job output logs
│       ├── job1.log
│       └── job2.log
│
├── venv/                        # Virtual environment
│   └── Scripts/
│       └── queuectl.exe        # CLI executable
│
├── setup.py                     # Package configuration
├── pyproject.toml              # Modern Python packaging
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

---

## 🐛 Troubleshooting

### Issue: `queuectl` command not found

**Solution:**
```powershell
# Ensure virtual environment is activated
.\venv\Scripts\Activate.ps1

# Reinstall if needed
pip install -e .
```

---

### Issue: PowerShell execution policy error

**Solution:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

---

### Issue: Jobs not processing

**Solution:**
```powershell
# Check if jobs exist
queuectl list

# Check if database exists
dir data\queuectl.db

# Try with single worker and observe output
queuectl worker start
```

---

### Issue: Database locked error

**Cause:** Multiple worker processes accessing database simultaneously.

**Solution:** SQLite with WAL mode handles this automatically. If error persists:
```powershell
# Stop all workers
# Restart with fewer workers
queuectl worker start --count 2
```

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Jobs per second (single worker) | ~10-50 |
| Supported concurrent workers | Unlimited (CPU-limited) |
| Database size | Grows with job history |
| Job claiming latency | < 10ms |
| Dashboard refresh rate | 3 seconds |

---

## 🔒 Security Considerations

⚠️ **QueueCTL executes shell commands as provided. Use with caution!**

- **Command Injection Risk:** Validate all job commands before enqueuing
- **File System Access:** Commands run with same permissions as worker process
- **Local Use Only:** Not designed for public-facing deployments
- **No Authentication:** Dashboard has no built-in authentication

**Best Practices:**
- Run workers with limited user permissions
- Sanitize command inputs
- Use for trusted, internal workloads only
- Add authentication if deploying dashboard publicly

---

## 🤝 Contributing

Contributions welcome! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with Python 3 and SQLite
- CLI powered by argparse
- Web dashboard using Flask
- Inspired by Celery, Redis Queue, and similar job queue systems

---

## 📞 Support

For issues, questions, or feature requests:

- **GitHub Issues:** [https://github.com/yourusername/queuectl/issues](https://github.com/yourusername/queuectl/issues)
- **Email:** your.email@example.com

---

## 🎓 Author

**Your Name**
- B.Tech Computer Science Student
- Specialization: AI/ML, Reinforcement Learning
- Project: Built for internship/portfolio demonstration

---

<div align="center">

**⭐ If you found this project useful, please consider giving it a star! ⭐**

Made with ❤️ using Python | Windows | SQLite

</div>
