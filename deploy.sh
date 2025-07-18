#!/bin/bash

# Church Map Project Deployment Script for AWS EC2 t2.micro
# Run this script on your EC2 instance

set -e  # Exit on any error

echo "🚀 Starting Church Map deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="church-map"
PROJECT_DIR="/home/ubuntu/$PROJECT_NAME"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="church-map"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Update system packages
print_status "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install required packages
print_status "Installing required packages..."
sudo apt install -y python3 python3-pip python3-venv nginx git supervisor

# Create project directory
print_status "Setting up project directory..."
sudo mkdir -p $PROJECT_DIR
sudo chown ubuntu:ubuntu $PROJECT_DIR

# Navigate to project directory
cd $PROJECT_DIR

# Create virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install django djangorestframework requests gunicorn

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
mkdir -p staticfiles
mkdir -p mediafiles

# Set up Django project (if not already present)
if [ ! -f "manage.py" ]; then
    print_warning "Django project not found. Please upload your project files to $PROJECT_DIR"
    print_warning "Make sure to include: manage.py, church_map_project/, churches/, requirements.txt"
    exit 1
fi

# Install project dependencies
if [ -f "requirements.txt" ]; then
    print_status "Installing project dependencies..."
    pip install -r requirements.txt
fi

# Set up environment variables
print_status "Setting up environment variables..."
cat > .env << EOF
DJANGO_SETTINGS_MODULE=church_map_project.settings_production
SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
EOF

# Run Django setup
print_status "Setting up Django..."
export DJANGO_SETTINGS_MODULE=church_map_project.settings_production
python manage.py collectstatic --noinput
python manage.py migrate

# Create superuser (optional)
print_status "Creating Django superuser..."
echo "You can create a superuser now or skip this step."
read -p "Create superuser? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python manage.py createsuperuser
fi

# Set up Gunicorn service
print_status "Setting up Gunicorn service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Church Map Gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
Environment="DJANGO_SETTINGS_MODULE=church_map_project.settings_production"
ExecStart=$VENV_DIR/bin/gunicorn --config gunicorn.conf.py church_map_project.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Set up Nginx configuration
print_status "Setting up Nginx..."
sudo tee /etc/nginx/sites-available/$SERVICE_NAME > /dev/null << EOF
server {
    listen 80;
    server_name _;  # Replace with your domain

    client_max_body_size 4G;

    access_log $PROJECT_DIR/logs/nginx_access.log;
    error_log $PROJECT_DIR/logs/nginx_error.log;

    location /static/ {
        alias $PROJECT_DIR/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias $PROJECT_DIR/mediafiles/;
        expires 1y;
        add_header Cache-Control "public";
    }

    location / {
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Host \$http_host;
        proxy_redirect off;
        proxy_pass http://127.0.0.1:8000;
    }
}
EOF

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Set up log rotation
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/$SERVICE_NAME > /dev/null << EOF
$PROJECT_DIR/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
    postrotate
        systemctl reload $SERVICE_NAME
        systemctl reload nginx
    endscript
}
EOF

# Set permissions
print_status "Setting permissions..."
sudo chown -R ubuntu:ubuntu $PROJECT_DIR
chmod +x $PROJECT_DIR/manage.py

# Start services
print_status "Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME
sudo systemctl enable nginx
sudo systemctl restart nginx

# Check service status
print_status "Checking service status..."
sudo systemctl status $SERVICE_NAME --no-pager
sudo systemctl status nginx --no-pager

# Final instructions
print_status "🎉 Deployment completed!"
echo
print_status "Your Church Map is now running!"
print_status "Access it at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo
print_status "Useful commands:"
echo "  - Check application logs: sudo journalctl -u $SERVICE_NAME -f"
echo "  - Check Nginx logs: sudo tail -f $PROJECT_DIR/logs/nginx_*.log"
echo "  - Restart application: sudo systemctl restart $SERVICE_NAME"
echo "  - Restart Nginx: sudo systemctl restart nginx"
echo
print_warning "Don't forget to:"
echo "  1. Update ALLOWED_HOSTS in settings_production.py with your domain/IP"
echo "  2. Set up SSL certificate (Let's Encrypt recommended)"
echo "  3. Configure your domain DNS to point to this server"
echo "  4. Set up monitoring and backups"