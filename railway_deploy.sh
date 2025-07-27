#!/bin/bash
# Railway deployment script for Church Map Project

echo "🚀 Starting Railway deployment for Church Map..."

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --settings=church_map_project.settings_railway

# Run migrations
echo "🔄 Running database migrations..."
python manage.py migrate --settings=church_map_project.settings_railway

# Check for any issues
echo "🔍 Running system checks..."
python manage.py check --settings=church_map_project.settings_railway

echo "✅ Railway deployment preparation complete!"
echo "Your Church Map should now be ready to deploy on Railway."