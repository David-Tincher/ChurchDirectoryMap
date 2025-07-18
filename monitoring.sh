#!/bin/bash

# Church Map Project Monitoring and Backup Script

PROJECT_DIR="/home/ubuntu/church-map"
BACKUP_DIR="/home/ubuntu/backups"
LOG_FILE="$PROJECT_DIR/logs/monitoring.log"

# Create backup directory
mkdir -p $BACKUP_DIR

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

# Function to check service status
check_service() {
    local service_name=$1
    if systemctl is-active --quiet $service_name; then
        log_message "✅ $service_name is running"
        return 0
    else
        log_message "❌ $service_name is not running"
        return 1
    fi
}

# Function to check disk space
check_disk_space() {
    local usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $usage -gt 80 ]; then
        log_message "⚠️  Disk usage is high: ${usage}%"
        return 1
    else
        log_message "✅ Disk usage is normal: ${usage}%"
        return 0
    fi
}

# Function to check memory usage
check_memory() {
    local mem_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ $mem_usage -gt 80 ]; then
        log_message "⚠️  Memory usage is high: ${mem_usage}%"
        return 1
    else
        log_message "✅ Memory usage is normal: ${mem_usage}%"
        return 0
    fi
}

# Function to backup database
backup_database() {
    local backup_file="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3"
    cp "$PROJECT_DIR/db_production.sqlite3" "$backup_file"
    
    # Keep only last 7 days of backups
    find $BACKUP_DIR -name "db_backup_*.sqlite3" -mtime +7 -delete
    
    log_message "✅ Database backed up to $backup_file"
}

# Function to check application health
check_app_health() {
    local response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
    if [ $response -eq 200 ]; then
        log_message "✅ Application is responding (HTTP $response)"
        return 0
    else
        log_message "❌ Application health check failed (HTTP $response)"
        return 1
    fi
}

# Function to restart services if needed
restart_services() {
    log_message "🔄 Restarting services..."
    sudo systemctl restart church-map
    sudo systemctl reload nginx
    sleep 5
    
    if check_service "church-map" && check_service "nginx"; then
        log_message "✅ Services restarted successfully"
        return 0
    else
        log_message "❌ Failed to restart services"
        return 1
    fi
}

# Main monitoring function
main_monitor() {
    log_message "🔍 Starting system monitoring..."
    
    local issues=0
    
    # Check services
    check_service "church-map" || ((issues++))
    check_service "nginx" || ((issues++))
    
    # Check system resources
    check_disk_space || ((issues++))
    check_memory || ((issues++))
    
    # Check application health
    check_app_health || ((issues++))
    
    # Backup database daily
    if [ "$(date +%H)" -eq 2 ]; then  # Run backup at 2 AM
        backup_database
    fi
    
    # If there are issues, try to restart services
    if [ $issues -gt 0 ]; then
        log_message "⚠️  Found $issues issues, attempting to restart services..."
        restart_services
    else
        log_message "✅ All systems normal"
    fi
    
    log_message "🏁 Monitoring completed"
}

# Run based on argument
case "$1" in
    "monitor")
        main_monitor
        ;;
    "backup")
        backup_database
        ;;
    "health")
        check_app_health
        ;;
    "restart")
        restart_services
        ;;
    *)
        echo "Usage: $0 {monitor|backup|health|restart}"
        echo "  monitor - Run full system monitoring"
        echo "  backup  - Backup database"
        echo "  health  - Check application health"
        echo "  restart - Restart services"
        exit 1
        ;;
esac