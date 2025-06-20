"""
ASGI config for informesjw project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os
import sys
import pysqlite3
sys.modules['sqlite3'] = pysqlite3

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'informesjw.settings')

application = get_asgi_application()
