# gunicorn_config.py
import os
import resource

workers = 1
worker_class = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'
timeout = 120
keepalive = 5
threads = 1

# Reiniciar después de X requests para liberar memoria
max_requests = 200
max_requests_jitter = 50

accesslog = '-'
errorlog = '-'
loglevel = 'info'

preload_app = True
forwarded_allow_ips = '*'

secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

def pre_fork(server, worker):
    pass

def post_fork(server, worker):
    # Limitar el uso de memoria a 450MB (soft limit) y 500MB (hard limit)
    # Solo intentar establecer límites si el módulo resource está disponible (no en Windows)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (450 * 1024 * 1024, 500 * 1024 * 1024))
        server.log.info(f"Límite de memoria establecido para worker {worker.pid}: 450MB (soft), 500MB (hard)")
    except (ImportError, AttributeError, ValueError, OSError) as e:
        # ImportError/AttributeError si resource no está disponible (Windows)
        # ValueError si los límites son inválidos
        # OSError si el sistema no permite setrlimit
        server.log.warning(f"No se pudo establecer el límite de memoria para worker {worker.pid}: {e}")

# El bind se configura automáticamente por Render a través de la variable PORT
# No es necesario definir 'bind' aquí si Render lo gestiona.
# bind = '0.0.0.0:' + os.getenv('PORT', '10000') # Comentado, Render lo maneja