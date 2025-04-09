# Configuración optimizada para SocketIO en entornos con recursos limitados

# Importaciones necesarias
import logging
import gc
import time
from functools import wraps
from flask import request

# Configuración de logging
logger = logging.getLogger('socketio_config')

# Configuración de SocketIO
socketio_config = {
    'async_mode': 'gevent',  # Usar gevent como modo asíncrono
    'ping_timeout': 30,       # Timeout para pings en segundos
    'ping_interval': 15,      # Intervalo de ping en segundos
    'max_http_buffer_size': 5 * 1024 * 1024,  # 5MB máximo para mensajes
    'manage_session': False,  # Usar la gestión de sesiones de Flask
    'logger': True,           # Habilitar logging
    'engineio_logger': True,  # Habilitar logging de engineio
    'cors_allowed_origins': '*',  # Permitir conexiones desde cualquier origen
    'always_connect': False,  # No conectar automáticamente si hay errores
    'cookie': None,           # No usar cookies para sesiones
}

# Función para limpiar recursos después de desconexiones
def cleanup_on_disconnect(f):
    """Decorador para limpiar recursos después de desconexiones"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        finally:
            # Forzar recolección de basura después de cada desconexión
            collected = gc.collect()
            logger.debug(f"Limpieza después de desconexión: {collected} objetos recolectados")
    return wrapped

# Función para manejar reconexiones
def handle_reconnect(socketio, namespace='/'):
    """Configura manejo de reconexiones para SocketIO"""
    @socketio.on('connect', namespace=namespace)
    def on_connect():
        logger.info(f"Cliente conectado: {request.sid}")
        
    @socketio.on('disconnect', namespace=namespace)
    @cleanup_on_disconnect
    def on_disconnect():
        logger.info(f"Cliente desconectado: {request.sid}")
        
    @socketio.on_error_default
    def default_error_handler(e):
        logger.error(f"Error en SocketIO: {str(e)}")

# Función para monitorear uso de memoria de SocketIO
def monitor_socketio_memory(socketio, interval=300):
    """Monitorea el uso de memoria de SocketIO y realiza limpiezas periódicas"""
    import threading
    
    def memory_monitor():
        while True:
            try:
                # Obtener número de clientes conectados
                connected_count = len(socketio.server.eio.sockets)
                logger.info(f"Clientes SocketIO conectados: {connected_count}")
                
                # Forzar recolección de basura
                collected = gc.collect()
                logger.info(f"Limpieza de memoria SocketIO: {collected} objetos recolectados")
                
                # Esperar antes de la próxima verificación
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error en monitoreo de memoria SocketIO: {str(e)}")
                time.sleep(60)  # Esperar un minuto en caso de error
    
    # Iniciar hilo de monitoreo
    monitor_thread = threading.Thread(target=memory_monitor, daemon=True)
    monitor_thread.start()
    
    return monitor_thread