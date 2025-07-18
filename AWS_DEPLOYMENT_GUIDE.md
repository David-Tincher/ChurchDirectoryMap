# AWS EC2 Deployment Guide for Church Map Project

## Prerequisites

- AWS Account
- Domain name (optional but recommended)
- Basic knowledge of SSH and Linux commands

## Step 1: Launch EC2 Instance

### 1.1 Create EC2 Instance
1. Go to AWS EC2 Console
2. Click "Launch Instance"
3. Choose **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type**
4. Select **t2.micro** (Free Tier eligible)
5. Configure Instance Details:
   - Keep defaults for most settings
   - Enable "Auto-assign Public IP"
6. Add Storage: 8 GB (default) is sufficient
7. Configure Security Group:
   - SSH (port 22) - Your IP only
   - HTTP (port 80) - Anywhere (0.0.0.0/0)
   - HTTPS (port 443) - Anywhere (0.0.0.0/0)
8. Review and Launch
9. Create/Select Key Pair for SSH access

### 1.2 Connect to Instance
```bash
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

## Step 2: Upload Project Files

### Option A: Using SCP
```bash
# From your local machine
scp -i your-key.pem -r /path/to/your/project ubuntu@your-ec2-ip:/home/ubuntu/church-map
```

### Option B: Using Git
```bash
# On EC2 instance
cd /home/ubuntu
git clone https://github.com/yourusername/church-map.git
```

## Step 3: Run Deployment Script

```bash
# Make script executable
chmod +x /home/ubuntu/church-map/deploy.sh

# Run deployment
cd /home/ubuntu/church-map
./deploy.sh
```

## Step 4: Configure Domain (Optional)

### 4.1 Point Domain to EC2
1. Go to your domain registrar
2. Create an A record pointing to your EC2 public IP
3. Create a CNAME record for www pointing to your domain

### 4.2 Set up SSL
```bash
# Run SSL setup script
./setup_ssl.sh your-domain.com
```

## Step 5: Final Configuration

### 5.1 Update Settings
Edit `/home/ubuntu/church-map/church_map_project/settings_production.py`:
- Update `ALLOWED_HOSTS` with your domain/IP
- Configure email settings if needed
- Set OpenRouteService API key if using

### 5.2 Restart Services
```bash
sudo systemctl restart church-map
sudo systemctl reload nginx
```

## Step 6: Set Up Monitoring

### 6.1 Add Monitoring Cron Job
```bash
# Edit crontab
crontab -e

# Add these lines:
# Check system every 5 minutes
*/5 * * * * /home/ubuntu/church-map/monitoring.sh monitor

# Daily backup at 2 AM
0 2 * * * /home/ubuntu/church-map/monitoring.sh backup
```

## Useful Commands

### Service Management
```bash
# Check service status
sudo systemctl status church-map
sudo systemctl status nginx

# Restart services
sudo systemctl restart church-map
sudo systemctl reload nginx

# View logs
sudo journalctl -u church-map -f
tail -f /home/ubuntu/church-map/logs/gunicorn_error.log
tail -f /home/ubuntu/church-map/logs/nginx_error.log
```

### Database Management
```bash
# Access Django shell
cd /home/ubuntu/church-map
source venv/bin/activate
python manage.py shell

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic
```

### Backup and Restore
```bash
# Manual backup
./monitoring.sh backup

# List backups
ls -la /home/ubuntu/backups/

# Restore from backup
cp /home/ubuntu/backups/db_backup_YYYYMMDD_HHMMSS.sqlite3 /home/ubuntu/church-map/db_production.sqlite3
sudo systemctl restart church-map
```

## Security Considerations

### 5.1 Firewall (UFW)
```bash
# Enable firewall
sudo ufw enable

# Allow SSH, HTTP, HTTPS
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# Check status
sudo ufw status
```

### 5.2 Automatic Updates
```bash
# Enable automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 5.3 Fail2Ban (Optional)
```bash
# Install fail2ban for SSH protection
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## Troubleshooting

### Common Issues

1. **502 Bad Gateway**
   - Check if Gunicorn is running: `sudo systemctl status church-map`
   - Check Gunicorn logs: `tail -f /home/ubuntu/church-map/logs/gunicorn_error.log`

2. **Static Files Not Loading**
   - Run: `python manage.py collectstatic`
   - Check Nginx configuration

3. **Database Errors**
   - Check if database file exists and has correct permissions
   - Run migrations: `python manage.py migrate`

4. **Memory Issues**
   - Monitor with: `free -h`
   - Consider reducing Gunicorn workers in `gunicorn.conf.py`

### Log Locations
- Application logs: `/home/ubuntu/church-map/logs/`
- System logs: `sudo journalctl -u church-map`
- Nginx logs: `/var/log/nginx/`

## Cost Estimation

### Monthly Costs (t2.micro)
- EC2 Instance: ~$8-10/month (Free Tier: $0 for first year)
- Data Transfer: ~$1-2/month (minimal for this application)
- Domain: ~$10-15/year (optional)
- **Total**: ~$10-12/month (or ~$1-2/month with Free Tier)

## Performance Optimization

### For t2.micro Optimization
1. **Reduce Gunicorn workers** if memory usage is high
2. **Enable Django caching** in settings
3. **Use CloudFront CDN** for static files (optional)
4. **Monitor CPU credits** in AWS console

### Scaling Options
- **t3.micro**: Better baseline performance
- **t3.small**: More memory and CPU
- **Application Load Balancer**: For high availability
- **RDS**: For managed database (if needed)

## Backup Strategy

### Automated Backups
- Database: Daily at 2 AM (via cron)
- Logs: Rotated weekly
- Static files: Backed up with code

### Manual Backup
```bash
# Full project backup
tar -czf church-map-backup-$(date +%Y%m%d).tar.gz /home/ubuntu/church-map
```

## Support

For issues with this deployment:
1. Check logs first
2. Verify all services are running
3. Check AWS security groups
4. Ensure domain DNS is configured correctly