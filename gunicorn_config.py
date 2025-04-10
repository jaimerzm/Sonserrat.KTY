# Configuración optimizada de Gunicorn para entornos con recursos limitados (Render Free Tier)

# Configuración de workers
workers = 1  # Mantener un solo worker en el plan gratuito de Render
worker_class = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'  # Necesario para WebSockets

# Timeouts optimizados
timeout = 120  # Aumentar el timeout para evitar WORKER TIMEOUT
keepalive = 5  # Mantener conexiones abiertas por 5 segundos

# Configuración de memoria
max_requests = 200  # Reiniciar workers después de procesar este número de solicitudes
max_requests_jitter = 50  # Añadir variabilidad para evitar que todos los workers se reinicien a la vez

# Configuración de carga
worker_connections = 500  # Limitar el número de conexiones simultáneas por worker

# Configuración de logging
accesslog = '-'  # Enviar logs de acceso a stdout
errorlog = '-'  # Enviar logs de error a stdout
loglevel = 'info'  # Nivel de logging

# Configuración de rendimiento
preload_app = True  # Cargar la aplicación antes de iniciar los workers

# Configuración de buffer
forwarded_allow_ips = '*'  # Permitir X-Forwarded-For desde cualquier IP

# Configuración de seguridad
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# Configuración de gevent específica
gevent_monkey_patch = True  # Aplicar monkey patching de gevent

# Configuración para limitar el uso de memoria
threads = 1  # Usar un solo hilo por worker para reducir el uso de memoria

# Función para limitar el uso de memoria por worker
def pre_fork(server, worker):
    # Configuración antes de iniciar un worker
    pass

def post_fork(server, worker):
    # Configuración después de iniciar un worker
    import resource
    # Limitar el uso de memoria a 480MB (plan gratuito de Render tiene 512MB)
    # 480MB en bytes = 480 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (480 * 1024 * 1024, 500 * 1024 * 1024))