
from gevent import monkey
monkey.patch_all()   # parchea socket, ssl, threading, etc. para que Gevent sea compatible con HTTPX

import os
from app import create_app  # o tu import habitual de Flask
app = create_app()

# WhiteNoise, si lo usas:
from whitenoise import WhiteNoise
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')