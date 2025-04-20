
# wsgi.py
from gevent import monkey
monkey.patch_all()

import os
import gc
import threading
import logging
import time  # Importar time

# Intentar importar app y socketio desde app.py
try:
    from app import app, socketio
except ImportError:
    # Si falla, intentar importar solo app (puede que socketio no esté definido o se use create_app)
    try:
        from app import app
        socketio = None # Marcar socketio como None si no se importa
        # O si usas create_app:
        # from app import create_app
        # app = create_app()
        # socketio = getattr(app, 'socketio', None) # Intentar obtener socketio si está en app
    except ImportError as e:
        logging.error(f"Error crítico: No se pudo importar 'app' desde app.py: {e}")
        raise # Relanzar la excepción para detener la ejecución

from whitenoise import WhiteNoise

# Configurar WhiteNoise para servir estáticos
# Asegúrate de que la ruta a 'static' sea correcta relativa a wsgi.py
static_folder_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
# Verifica si la carpeta static existe
if not os.path.isdir(static_folder_root):
    logging.warning(f"La carpeta estática '{static_folder_root}' no existe. WhiteNoise podría no funcionar correctamente.")
    # Considera crearla si es necesario: os.makedirs(static_folder_root, exist_ok=True)

# Aplicar WhiteNoise SOLO si 'app' se importó correctamente
if 'app' in locals() and hasattr(app, 'wsgi_app'):
    app.wsgi_app = WhiteNoise(app.wsgi_app, root=static_folder_root, prefix='static/')
elif 'app' in locals():
    logging.warning("El objeto 'app' no tiene el atributo 'wsgi_app'. WhiteNoise no se aplicará.")
else:
    logging.error("El objeto 'app' no está definido. WhiteNoise no se puede aplicar.")

# Limpieza periódica de memoria para Render
logger = logging.getLogger('wsgi')
def memory_cleanup():
    while True:
        try:
            collected = gc.collect()
            logger.info(f"Limpieza de memoria: {collected} objetos recolectados")
            time.sleep(300) # Espera 5 minutos (300 segundos)
        except Exception as e:
            logger.error(f"Error en limpieza de memoria: {str(e)}")
            time.sleep(60) # Espera 1 minuto antes de reintentar en caso de error

# Iniciar el hilo de limpieza solo en entorno Render
# Comprueba variables de entorno comunes de Render
if os.environ.get('RENDER', False) or os.environ.get('RENDER_SERVICE_ID', False):
    logger.info("Entorno Render detectado, iniciando limpieza de memoria periódica.")
    # Establecer RENDER=true si no está ya presente (útil para otras partes del código)
    os.environ['RENDER'] = 'true'
    # Iniciar el hilo como daemon para que no bloquee la salida de la app
    cleanup_thread = threading.Thread(target=memory_cleanup, daemon=True)
    cleanup_thread.start()
else:
    logger.info("No se detectó entorno Render, la limpieza de memoria periódica no se iniciará.")

# No es necesario iniciar el servidor aquí, Gunicorn lo hará.
# Si usas Flask-SocketIO y Gunicorn, asegúrate de que Gunicorn use el worker correcto (geventwebsocket)
# y que el comando de inicio sea algo como: gunicorn wsgi:app ... (o wsgi:socketio si usas socketio.run)
# Render usará el comando definido en Procfile o en la configuración del servicio.