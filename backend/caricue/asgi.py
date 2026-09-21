"""ASGI entrypoint.

Not used by the MVP deployment (Gunicorn + WSGI), kept as an extension point
for a future async transport.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caricue.settings")

application = get_asgi_application()
