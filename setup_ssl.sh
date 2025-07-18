#!/bin/bash

# SSL Setup Script for Church Map Project
# This script sets up Let's Encrypt SSL certificate

set -e

echo "🔒 Setting up SSL certificate with Let's Encrypt..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if domain is provided
if [ -z "$1" ]; then
    print_error "Please provide your domain name"
    echo "Usage: ./setup_ssl.sh your-domain.com"
    exit 1
fi

DOMAIN=$1
EMAIL="admin@$DOMAIN"  # Change this to your email

print_status "Setting up SSL for domain: $DOMAIN"

# Install Certbot
print_status "Installing Certbot..."
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
print_status "Obtaining SSL certificate..."
sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --email $EMAIL --agree-tos --non-interactive

# Update Nginx configuration for SSL
print_status "Updating Nginx configuration..."
sudo tee /etc/nginx/sites-available/church-map > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 4G;

    access_log /home/ubuntu/church-map/logs/nginx_access.log;
    error_log /home/ubuntu/church-map/logs/nginx_error.log;

    location /static/ {
        alias /home/ubuntu/church-map/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /home/ubuntu/church-map/mediafiles/;
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

# Test and reload Nginx
print_status "Testing Nginx configuration..."
sudo nginx -t
sudo systemctl reload nginx

# Set up automatic renewal
print_status "Setting up automatic SSL renewal..."
sudo crontab -l 2>/dev/null | { cat; echo "0 12 * * * /usr/bin/certbot renew --quiet"; } | sudo crontab -

# Update Django settings for HTTPS
print_status "Updating Django settings for HTTPS..."
SETTINGS_FILE="/home/ubuntu/church-map/church_map_project/settings_production.py"

# Backup original settings
sudo cp $SETTINGS_FILE ${SETTINGS_FILE}.backup

# Update ALLOWED_HOSTS and enable HTTPS settings
sudo sed -i "s/your-domain.com/$DOMAIN/g" $SETTINGS_FILE
sudo sed -i "s/www.your-domain.com/www.$DOMAIN/g" $SETTINGS_FILE
sudo sed -i "s/# SECURE_SSL_REDIRECT = True/SECURE_SSL_REDIRECT = True/g" $SETTINGS_FILE
sudo sed -i "s/# SESSION_COOKIE_SECURE = True/SESSION_COOKIE_SECURE = True/g" $SETTINGS_FILE
sudo sed -i "s/# CSRF_COOKIE_SECURE = True/CSRF_COOKIE_SECURE = True/g" $SETTINGS_FILE
sudo sed -i "s/# SECURE_HSTS_SECONDS = 31536000/SECURE_HSTS_SECONDS = 31536000/g" $SETTINGS_FILE
sudo sed -i "s/# SECURE_HSTS_INCLUDE_SUBDOMAINS = True/SECURE_HSTS_INCLUDE_SUBDOMAINS = True/g" $SETTINGS_FILE
sudo sed -i "s/# SECURE_HSTS_PRELOAD = True/SECURE_HSTS_PRELOAD = True/g" $SETTINGS_FILE

# Restart services
print_status "Restarting services..."
sudo systemctl restart church-map
sudo systemctl reload nginx

print_status "🎉 SSL setup completed!"
echo
print_status "Your Church Map is now secured with HTTPS!"
print_status "Access it at: https://$DOMAIN"
echo
print_status "SSL certificate will auto-renew every 12 hours via cron job"
print_warning "Make sure your domain DNS is pointing to this server's IP address"