"""
Gunicorn configuration for Church Map Project
Optimized for Railway deployment
"""

import multiprocessing
import os

# Server socket - Railway provides PORT environment variable
port = os.environ.get('PORT', '8000')
bind = f"0.0.0.0:{port}"
backlog = 2048

# Worker processes
# Railway deployment - use conservative worker count to prevent resource exhaustion
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging - Use stdout/stderr for Railway
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'church_map_gunicorn'

# Daemon mode - must be False for Railway
daemon = False

# Preload application for better memory usage
preload_app = True

# Graceful timeout
graceful_timeout = 30

# Temporary directory
tmp_upload_dir = None