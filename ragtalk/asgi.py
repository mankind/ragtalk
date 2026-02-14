"""
ASGI config for ragtalk project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

from django.urls import path

from django.core.asgi import get_asgi_application

from echo.consumers import DocumentConsumer, ChatConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ragtalk.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            # Lead tip: versioning your WS endpoints is a nice touch
            path("ws/documents/", DocumentConsumer.as_asgi()),
              # Real-time Chat & Streaming
            path("ws/chat/", ChatConsumer.as_asgi()),
        ])
    ),
})