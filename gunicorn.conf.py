"""
Gunicorn configuration for Church Map Project
Optimized for AWS t2.micro instance
"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
# For t2.micro (1 vCPU, 1GB RAM), use 2-3 workers max
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "/home/ubuntu/church-map/logs/gunicorn_access.log"
errorlog = "/home/ubuntu/church-map/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'church_map_gunicorn'

# Daemon mode
daemon = False
pidfile = "/home/ubuntu/church-map/gunicorn.pid"

# User and group to run as
user = "ubuntu"
group = "ubuntu"

# Preload application for better memory usage
preload_app = True

# Graceful timeout
graceful_timeout = 30

# Temporary directory
tmp_upload_dir = None