"""
WSGI config for sermons project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os
import time
import traceback
import signal
import sys

from django.core.wsgi import get_wsgi_application

# Only add production paths if they exist
for p in ["/var/www/api.dailyoffice2019.com/site", "/var/www/api.dailyoffice2019.com/env/lib/python3.9/site-packages"]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.append(p)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "website.settings")

application = get_wsgi_application()
