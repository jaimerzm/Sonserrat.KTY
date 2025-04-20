# gunicorn_config.py
import os

# Número de procesos (ajusta según cores/ram)
workers = int(os.getenv('WEB_CONCURRENCY', '2'))
# WebSocket support via gevent-websocket
worker_class = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'
# Tiempo máximo en segundos por request (aumenta si hay tareas largas)
timeout = 120

# Escucha en el puerto que Render expone vía $PORT
bind = '0.0.0.0:' + os.getenv('PORT', '10000')