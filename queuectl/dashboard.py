# queuectl/dashboard.py
"""
Web Dashboard for QueueCTL.

Provides a real-time web interface for monitoring:
- Queue status and metrics
- Job list with filtering
- Job details and logs
- Worker status
- System health

Requires Flask: pip install flask
"""

from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import os
from pathlib import Path

from queuectl.database import Database
from queuectl.job_manager import JobManager

app = Flask(__name__)

# HTML Template (embedded for simplicity - could be moved to separate file)
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QueueCTL Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }
        
        h1 {
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .subtitle {
            color: #666;
            font-size: 1.1em;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        
        .stat-label {
            color: #888;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }
        
        .stat-card.pending .stat-value { color: #ffa500; }
        .stat-card.processing .stat-value { color: #2196F3; }
        .stat-card.completed .stat-value { color: #4CAF50; }
        .stat-card.failed .stat-value { color: #FF9800; }
        .stat-card.dead .stat-value { color: #f44336; }
        .stat-card.workers .stat-value { color: #9C27B0; }
        
        .content-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }
        
        .panel {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .panel h2 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        
        .filter-bar {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .filter-btn {
            padding: 8px 16px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.2s;
        }
        
        .filter-btn:hover {
            background: #667eea;
            color: white;
        }
        
        .filter-btn.active {
            background: #667eea;
            color: white;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            background: #f5f5f5;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #666;
            border-bottom: 2px solid #ddd;
        }
        
        td {
            padding: 12px;
            border-bottom: 1px solid #eee;
        }
        
        tr:hover {
            background: #f9f9f9;
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .status-badge.pending { background: #fff3cd; color: #856404; }
        .status-badge.processing { background: #cfe2ff; color: #084298; }
        .status-badge.completed { background: #d1e7dd; color: #0f5132; }
        .status-badge.failed { background: #ffe5b4; color: #664d03; }
        .status-badge.dead { background: #f8d7da; color: #842029; }
        
        .job-id {
            font-family: 'Courier New', monospace;
            font-weight: 600;
            color: #667eea;
        }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }
        
        .metric-label {
            color: #666;
            font-weight: 500;
        }
        
        .metric-value {
            font-weight: 600;
            color: #333;
        }
        
        .auto-refresh {
            text-align: center;
            padding: 10px;
            background: #e8f5e9;
            border-radius: 8px;
            color: #2e7d32;
            font-weight: 500;
            margin-top: 20px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        
        .no-data {
            text-align: center;
            padding: 40px;
            color: #999;
            font-style: italic;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .pulse {
            animation: pulse 2s ease-in-out infinite;
        }
        
        @media (max-width: 968px) {
            .content-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 QueueCTL Dashboard</h1>
            <p class="subtitle">Real-time Job Queue Monitoring</p>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card pending">
                <div class="stat-label">Pending</div>
                <div class="stat-value" id="stat-pending">-</div>
            </div>
            <div class="stat-card processing">
                <div class="stat-label">Processing</div>
                <div class="stat-value pulse" id="stat-processing">-</div>
            </div>
            <div class="stat-card completed">
                <div class="stat-label">Completed</div>
                <div class="stat-value" id="stat-completed">-</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-label">Failed</div>
                <div class="stat-value" id="stat-failed">-</div>
            </div>
            <div class="stat-card dead">
                <div class="stat-label">Dead (DLQ)</div>
                <div class="stat-value" id="stat-dead">-</div>
            </div>
            <div class="stat-card workers">
                <div class="stat-label">Active Workers</div>
                <div class="stat-value" id="stat-workers">-</div>
            </div>
        </div>
        
        <div class="content-grid">
            <div class="panel">
                <h2>📋 Recent Jobs</h2>
                
                <div class="filter-bar">
                    <button class="filter-btn active" onclick="filterJobs('all')">All</button>
                    <button class="filter-btn" onclick="filterJobs('pending')">Pending</button>
                    <button class="filter-btn" onclick="filterJobs('processing')">Processing</button>
                    <button class="filter-btn" onclick="filterJobs('completed')">Completed</button>
                    <button class="filter-btn" onclick="filterJobs('failed')">Failed</button>
                    <button class="filter-btn" onclick="filterJobs('dead')">Dead</button>
                </div>
                
                <div id="jobs-container">
                    <div class="loading">Loading jobs...</div>
                </div>
            </div>
            
            <div class="panel">
                <h2>📊 System Metrics</h2>
                <div id="metrics-container">
                    <div class="loading">Loading metrics...</div>
                </div>
            </div>
        </div>
        
        <div class="auto-refresh">
            ⟳ Auto-refreshing every 3 seconds
        </div>
    </div>
    
    <script>
        let currentFilter = 'all';
        
        // Fetch and update stats
        async function updateStats() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                document.getElementById('stat-pending').textContent = data.pending;
                document.getElementById('stat-processing').textContent = data.processing;
                document.getElementById('stat-completed').textContent = data.completed;
                document.getElementById('stat-failed').textContent = data.failed;
                document.getElementById('stat-dead').textContent = data.dead;
                document.getElementById('stat-workers').textContent = data.workers;
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }
        
        // Fetch and display jobs
        async function updateJobs() {
            try {
                const url = currentFilter === 'all' 
                    ? '/api/jobs' 
                    : `/api/jobs?state=${currentFilter}`;
                    
                const response = await fetch(url);
                const data = await response.json();
                
                const container = document.getElementById('jobs-container');
                
                if (data.jobs.length === 0) {
                    container.innerHTML = '<div class="no-data">No jobs found</div>';
                    return;
                }
                
                const tableHTML = `
                    <table>
                        <thead>
                            <tr>
                                <th>Job ID</th>
                                <th>State</th>
                                <th>Priority</th>
                                <th>Attempts</th>
                                <th>Created</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.jobs.map(job => `
                                <tr>
                                    <td class="job-id">${job.id}</td>
                                    <td><span class="status-badge ${job.state}">${job.state}</span></td>
                                    <td>${job.priority}</td>
                                    <td>${job.attempts}/${job.max_retries}</td>
                                    <td>${new Date(job.created_at).toLocaleString()}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                
                container.innerHTML = tableHTML;
            } catch (error) {
                console.error('Error fetching jobs:', error);
                document.getElementById('jobs-container').innerHTML = 
                    '<div class="no-data">Error loading jobs</div>';
            }
        }
        
        // Fetch and display metrics
        async function updateMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                
                const metricsHTML = `
                    <div class="metric-row">
                        <span class="metric-label">Total Jobs</span>
                        <span class="metric-value">${data.total_jobs}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Completed</span>
                        <span class="metric-value">${data.completed_jobs}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Failed</span>
                        <span class="metric-value">${data.failed_jobs}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Dead (DLQ)</span>
                        <span class="metric-value">${data.dead_jobs}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Avg Runtime</span>
                        <span class="metric-value">${data.avg_runtime_seconds.toFixed(2)}s</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Active Workers</span>
                        <span class="metric-value">${data.active_workers}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Last Updated</span>
                        <span class="metric-value">${new Date(data.updated_at).toLocaleString()}</span>
                    </div>
                `;
                
                document.getElementById('metrics-container').innerHTML = metricsHTML;
            } catch (error) {
                console.error('Error fetching metrics:', error);
                document.getElementById('metrics-container').innerHTML = 
                    '<div class="no-data">Error loading metrics</div>';
            }
        }
        
        // Filter jobs by state
        function filterJobs(state) {
            currentFilter = state;
            
            // Update active button
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            // Reload jobs
            updateJobs();
        }
        
        // Update all data
        function refreshAll() {
            updateStats();
            updateJobs();
            updateMetrics();
        }
        
        // Initial load
        refreshAll();
        
        // Auto-refresh every 3 seconds
        setInterval(refreshAll, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Render the main dashboard page."""
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/api/status')
def api_status():
    """
    Get queue status summary.
    
    Returns:
        JSON with job counts by state and worker count
    """
    try:
        manager = JobManager()
        db = Database()
        
        summary = manager.get_status_summary()
        metrics = db.fetchone("SELECT active_workers FROM metrics")
        
        return jsonify({
            'pending': summary['pending'],
            'processing': summary['processing'],
            'completed': summary['completed'],
            'failed': summary['failed'],
            'dead': summary['dead'],
            'workers': metrics['active_workers']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/jobs')
def api_jobs():
    """
    Get list of jobs with optional state filter.
    
    Query params:
        state: Filter by job state (pending/processing/completed/failed/dead)
        limit: Maximum number of jobs to return (default 50)
    
    Returns:
        JSON with list of jobs
    """
    try:
        manager = JobManager()
        
        state = request.args.get('state', None)
        limit = int(request.args.get('limit', 50))
        
        jobs = manager.list_jobs(state=state, limit=limit)
        
        # Convert Row objects to dictionaries
        jobs_list = []
        for job in jobs:
            jobs_list.append({
                'id': job['id'],
                'command': job['command'],
                'state': job['state'],
                'attempts': job['attempts'],
                'max_retries': job['max_retries'],
                'priority': job['priority'],
                'timeout': job['timeout'],
                'created_at': job['created_at'],
                'updated_at': job['updated_at'],
                'error_message': job['error_message']
            })
        
        return jsonify({'jobs': jobs_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics')
def api_metrics():
    """
    Get system metrics.
    
    Returns:
        JSON with performance metrics
    """
    try:
        db = Database()
        metrics = db.fetchone("SELECT * FROM metrics")
        
        return jsonify({
            'total_jobs': metrics['total_jobs'],
            'completed_jobs': metrics['completed_jobs'],
            'failed_jobs': metrics['failed_jobs'],
            'dead_jobs': metrics['dead_jobs'],
            'avg_runtime_seconds': float(metrics['avg_runtime_seconds']),
            'active_workers': metrics['active_workers'],
            'updated_at': metrics['updated_at']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/job/<job_id>')
def api_job_detail(job_id):
    """
    Get detailed information about a specific job.
    
    Args:
        job_id: Job identifier
    
    Returns:
        JSON with job details
    """
    try:
        manager = JobManager()
        job = manager.get_job(job_id)
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Read log file if exists
        log_path = Path('data/logs') / f"{job_id}.log"
        log_content = None
        
        if log_path.exists():
            with open(log_path, 'r', encoding='utf-8') as f:
                log_content = f.read()
        
        return jsonify({
            'id': job['id'],
            'command': job['command'],
            'state': job['state'],
            'attempts': job['attempts'],
            'max_retries': job['max_retries'],
            'priority': job['priority'],
            'timeout': job['timeout'],
            'run_at': job['run_at'],
            'next_attempt_at': job['next_attempt_at'],
            'created_at': job['created_at'],
            'updated_at': job['updated_at'],
            'completed_at': job['completed_at'],
            'error_message': job['error_message'],
            'output_path': job['output_path'],
            'log_content': log_content
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Run the Flask app (only when running directly, not via queuectl command)
if __name__ == '__main__':
    print("🌐 Starting QueueCTL Dashboard...")
    print("📍 Access at: http://localhost:5000")
    print("⚠️  Press Ctrl+C to stop")
    app.run(host='0.0.0.0', port=5000, debug=True)
