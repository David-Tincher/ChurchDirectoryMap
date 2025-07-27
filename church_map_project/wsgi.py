"""
WSGI config for church_map_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Use Railway settings if deployed on Railway, otherwise use default settings
if 'RAILWAY_ENVIRONMENT' in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'church_map_project.settings_railway')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'church_map_project.settings')

application = get_wsgi_application()
