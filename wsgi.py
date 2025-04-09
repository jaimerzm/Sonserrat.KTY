# Script de inicialización optimizado para entornos con recursos limitados
import os
import logging
import gc
import time
import threading
from app import app, socketio

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('wsgi')

# Función para limpiar memoria periódicamente
def memory_cleanup():
    """Realiza limpieza de memoria periódica para evitar fugas de memoria"""
    while True:
        try:
            # Forzar recolección de basura
            collected = gc.collect()
            logger.info(f"Limpieza de memoria programada: {collected} objetos recolectados")
            
            # Esperar 5 minutos antes de la próxima limpieza
            time.sleep(300)
        except Exception as e:
            logger.error(f"Error en limpieza de memoria: {str(e)}")
            time.sleep(60)  # Esperar un minuto en caso de error

# Iniciar hilo de limpieza de memoria
# Detectar si estamos en Render por la presencia de variables de entorno específicas
is_render = os.environ.get('RENDER', False) or os.environ.get('RENDER_SERVICE_ID', False)
if is_render:
    # Establecer variable de entorno RENDER para que otras partes de la aplicación lo detecten
    os.environ['RENDER'] = 'true'
    logger.info("Detectado entorno Render - Iniciando optimizaciones de memoria")
    cleanup_thread = threading.Thread(target=memory_cleanup, daemon=True)
    cleanup_thread.start()

# Función para iniciar la aplicación
def create_app():
    """Crea y configura la aplicación"""
    logger.info("Iniciando aplicación con configuración optimizada")
    return app

# Punto de entrada para Gunicorn
app = create_app()

# Función para ejecutar la aplicación en modo desarrollo
if __name__ == '__main__':
    # En desarrollo, usar el servidor integrado de Flask-SocketIO
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Iniciando servidor de desarrollo en puerto {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=True)