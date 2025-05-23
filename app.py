from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory, abort
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, login_required, current_user, login_user
from datetime import timedelta
from dotenv import load_dotenv
import google.generativeai as genai
import os
import time
import logging
import json
from models import db, User, Conversation, Message
from auth import auth as auth_blueprint, oauth
import PIL.Image
import io
import base64
import pathlib
import textwrap
import mimetypes
from groq import Groq
genai_types = genai.types # Usar el alias genai importado previamente

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración de archivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Configurar Google AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
logger.info("Intentando configurar Google AI y Groq...")

# Configurar Groq AI
if GROQ_API_KEY:
    try:
        # Inicializar el cliente Groq directamente sin manipular proxies
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("Groq API configurada exitosamente")
    except Exception as e:
        logger.error(f"Error al configurar Groq API: {str(e)}")
        groq_client = None
else:
    logger.warning("GROQ_API_KEY no está configurada")
    groq_client = None

# Variables globales para los modelos
model = None
vision_model = None
image_gen_model = None  # Modelo para generación/edición de imágenes

def save_message_to_db(conversation_id, content, role):
    """
    Guarda un mensaje en la base de datos.
    
    Args:
        conversation_id: ID de la conversación
        content: Contenido del mensaje
        role: Rol del mensaje ('user' o 'assistant')
    """
    try:
        # Obtener o crear la conversación
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            conversation = Conversation(id=conversation_id)
            db.session.add(conversation)
        
        # Crear y guardar el mensaje
        message = Message(
            conversation_id=conversation_id,
            content=content,
            role=role
        )
        db.session.add(message)
        db.session.commit()
        logger.debug(f"Mensaje guardado en DB - Conversación: {conversation_id}, Rol: {role}")
        
    except Exception as e:
        logger.error(f"Error guardando mensaje en DB: {str(e)}")
        db.session.rollback()

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # Configuración del modelo
    generation_config = {
        "temperature": 0.9,
        "top_p": 1,
        "top_k": 32,
        "max_output_tokens": 2048,
    }

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    # Usar el mismo modelo para todo
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",    # Última versión Gemini 2.0 Flash
        generation_config=generation_config,
        safety_settings=safety_settings
    )

    # Modelo para generación/edición de imágenes (Gemini Flash)
    try:
        image_gen_model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp-image-generation",  # Gemini Flash 2.0 Experimento (imagen)
            generation_config=generation_config, # Ajustar si es necesario
            safety_settings=safety_settings
        )
        logger.info("Modelo de generación de imágenes configurado exitosamente")
    except Exception as e:
        logger.error(f"Error configurando modelo de generación de imágenes: {e}")
        image_gen_model = None

    # Cliente Google AI (genai.Client) no se usa directamente aquí.
    # La inicialización del modelo principal (texto/imagen) se hace arriba.
    # genai_client = None # Mantener como None si Veo 2 no está activo/configurado
    genai_client = None
    if GOOGLE_API_KEY:
        try:
            genai_client = genai.Client()
            logger.info("Google AI Client (for Veo 2) initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google AI Client for Veo 2: {e}")
            genai_client = None # Ensure it's None if initialization fails
    else:
        logger.warning("GOOGLE_API_KEY not found. Google AI Client for Veo 2 cannot be initialized.")

    # Initialize chat instance (para el modelo de texto principal)
    chat = model.start_chat(history=[])
    logger.info("Google AI model y chat configurados exitosamente")
    logger.info("Google AI configurado exitosamente")
except Exception as e:
    logger.error(f"Error configurando Google AI: {e}")
    model = None

# Almacenamiento de contexto por conversación
conversation_history = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(file):
    try:
        if isinstance(file, io.BytesIO):
            # Si es un BytesIO, leemos directamente los bytes
            image_bytes = file.getvalue()
            file_size = len(image_bytes)
            logger.debug(f"Procesando BytesIO, tamaño: {file_size/1024/1024:.2f}MB")
        else:
            # Si es un objeto file de Flask, leemos como antes
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            image_bytes = file.read()
            logger.debug(f"Procesando archivo, tamaño: {file_size/1024/1024:.2f}MB")
            
        if file_size > MAX_FILE_SIZE:
            logger.error(f"Archivo demasiado grande: {file_size/1024/1024:.2f}MB")
            return None
            
        # Para BytesIO no necesitamos verificar el tipo de archivo ya que viene de base64
        if not isinstance(file, io.BytesIO):
            filename = file.filename.lower()
            if not allowed_file(filename):
                logger.error(f"Tipo de archivo no permitido: {filename}")
                return None
            
        if not image_bytes:
            logger.error("No se pudieron leer bytes del archivo")
            return None
            
        try:
            # Abrir la imagen con PIL
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
            # Convertir a RGB si es necesario
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Guardar la imagen procesada en un BytesIO
            output = io.BytesIO()
            img.save(output, format='JPEG')
            output.seek(0)
            
            logger.debug("Imagen procesada exitosamente")
            return output
            
        except Exception as e:
            logger.error(f"Error al procesar la imagen con PIL: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error en process_image: {e}")
        return None

# --- Mover la inicialización de Flask aquí ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE  # 20MB max-limit
# --- Fin de la inicialización movida ---

# Asegurarse de que el directorio instance existe
instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# Configuración básica
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())

# Configuración de la base de datos: usa DATABASE_URL si está disponible (Render), si no, usa SQLite local
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    # Asegurarse de que la URL de Heroku/Render sea compatible con SQLAlchemy 1.4+
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    logger.info("Usando base de datos PostgreSQL de Render")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "db.sqlite")}'
    logger.info("DATABASE_URL no encontrada o no es PostgreSQL, usando SQLite local")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de sesiones y cookies
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=31)
app.config['REMEMBER_COOKIE_SECURE'] = False  # Cambiar a True en producción
app.config['REMEMBER_COOKIE_HTTPONLY'] = True

# Inicializar extensiones
db.init_app(app)

# Importar configuración optimizada de SocketIO
from socketio_config import socketio_config

# Configuración optimizada de SocketIO para reducir uso de memoria
socketio = SocketIO(app, **socketio_config)

# Configurar monitoreo de memoria para SocketIO
if os.environ.get('RENDER', False):
    from socketio_config import monitor_socketio_memory
    monitor_socketio_memory(socketio, interval=300)

# Inicializar OAuth con la app Flask
oauth.init_app(app)

# Configurar Login Manager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)
login_manager.session_protection = "strong"

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except:
        return None

# Registrar blueprint de autenticación
app.register_blueprint(auth_blueprint)

# Almacenamiento de sesiones de chat
chat_sessions = {}

@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=31)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    if not current_user.is_authenticated:
        # Check if this is a guest user session
        if session.get('is_guest'):
            logger.info("Usuario invitado conectado")
            return True
        # Allow unauthenticated users to connect
        logger.info("Usuario no autenticado conectado")
        return True
    logger.info(f"Usuario {current_user.username} conectado")

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        logger.info(f"Usuario {current_user.username} desconectado")

def generate_image_edit_from_upload(input_image, prompt):
    """
    Edita una imagen usando Gemini 2.0 Flash
    
    Args:
        input_image: Archivo de imagen subido por el usuario
        prompt: Instrucciones de edición proporcionadas por el usuario
    
    Returns:
        URL de la imagen editada o mensaje de error
    """
    try:
        logger.info(f"Editando imagen con Gemini 2.0 Flash. Prompt: {prompt}")
        
        # Procesar la imagen de entrada
        processed_image = None
        if isinstance(input_image, str):
            # Si es una cadena base64
            if ',' in input_image:
                header, encoded = input_image.split(',', 1)
                image_data = base64.b64decode(encoded.strip())
            else:
                image_data = base64.b64decode(input_image.strip())
            processed_image = io.BytesIO(image_data)
        else:
            # Si es un objeto de archivo
            input_image.seek(0)
            processed_image = io.BytesIO(input_image.read())
        
        if not processed_image:
            return "Error: No se pudo procesar la imagen para edición."
        
        # Usar instancia global de edición (image_gen_model)
        global image_gen_model # Necesario para acceder al modelo global
        if image_gen_model is None:
            logger.error("El modelo global de generación/edición de imágenes (image_gen_model) no está inicializado.")
            return "Error: El servicio de edición de imágenes no está disponible actualmente."
        
        # No es necesario image_model = image_gen_model, solo usa image_gen_model directamente
        # No es necesario genai.configure aquí, ya está configurado globalmente.

        # Preparar la imagen para la API
        img = PIL.Image.open(processed_image)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Configuración de generación específica para edición de imágenes
        generation_config = {
            "temperature": 0.7,
            "top_p": 1.0,
            "top_k": 32,
            "max_output_tokens": 2048,
        }

        # Crear el contenido para la solicitud
        content = [
            {"text": f"Edita esta imagen según estas instrucciones: {prompt}"},
            {"inline_data": {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(processed_image.getvalue()).decode('utf-8')
            }}
        ]

        response = image_gen_model.generate_content( # Usa el modelo global directamente
            content
            # generation_config y safety_settings ya están en el image_gen_model global
        )
        
        # Procesar la respuesta
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    try:
                        # Guardar la imagen en el servidor
                        inline_data = part.inline_data
                        image_data = inline_data.data
                        image_mime = inline_data.mime_type
                        
                        # Crear un nombre de archivo único
                        timestamp = int(time.time())
                        file_extension = mimetypes.guess_extension(image_mime) or '.png'
                        filename = f"edited_image_{timestamp}{file_extension}"
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        
                        # Guardar la imagen - decodificar base64 si es necesario
                        if isinstance(image_data, str):
                            if image_data.startswith('data:'):
                                # Es una cadena base64 con prefijo
                                header, encoded = image_data.split(",", 1)
                                image_data = base64.b64decode(encoded)
                            else:
                                # Es una cadena base64 sin prefijo
                                image_data = base64.b64decode(image_data)
                        
                        # Guardar la imagen
                        with open(filepath, "wb") as f:
                            f.write(image_data)
                        
                        # Crear URL para la imagen
                        image_url = f"/uploads/{filename}"
                        logger.info(f"Imagen editada guardada en: {filepath}")
                        return f"\n[GENERATED_IMAGE:{image_url}]"
                    except Exception as img_save_error:
                        logger.error(f"Error al guardar la imagen editada: {str(img_save_error)}")
                        return f"Error al guardar la imagen editada: {str(img_save_error)}"
        
        return "No se pudo generar la edición de la imagen."
    except Exception as e:
        logger.error(f"Error en generate_image_edit_from_upload: {str(e)}")
        return f"Error al editar la imagen: {str(e)}"

def save_binary_file(file_path, data):
    """
    Guarda datos binarios en un archivo
    
    Args:
        file_path: Ruta del archivo donde guardar los datos
        data: Datos binarios a guardar
    """
    try:
        with open(file_path, "wb") as f:
            f.write(data)
        logger.info(f"Archivo guardado en: {file_path}")
    except Exception as e:
        logger.error(f"Error al guardar el archivo {file_path}: {e}")
        raise

def with_retries(max_retries=3, delay=1):
    """
    Decorador para reintentar funciones que pueden fallar temporalmente
    
    Args:
        max_retries: Número máximo de reintentos
        delay: Tiempo de espera entre reintentos en segundos
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Error después de {max_retries} intentos: {str(e)}")
                        raise
                    logger.warning(f"Intento {retries} fallido: {str(e)}. Reintentando en {delay} segundos...")
                    time.sleep(delay)
        return wrapper
    return decorator

@with_retries()
def generate_video_from_text(prompt_text,
                             duration_seconds: int = 5,
                             number_of_videos: int = 1,
                             aspect_ratio: str = "16:9"):
    """
    Genera videos a partir de un prompt de texto usando Google Veo 2.

    Args:
        prompt_text (str): El texto que describe el video a generar.
        duration_seconds (int): Duración del video en segundos (5-8).
        number_of_videos (int): Número de videos a generar (1-4).

    Returns:
        list: Lista de URLs de los videos generados o lista vacía en caso de error.
    """
    if not genai_client:
        logger.error("Video generation client not available (genai.Client is not initialized).")
        return []

    try:
        logger.info(f"Generando video desde texto: '{prompt_text}', Duración: {duration_seconds}s, Cantidad: {number_of_videos}, Aspect Ratio: {aspect_ratio}")

        # Validar parámetros
        duration_seconds = max(5, min(int(duration_seconds), 8))
        number_of_videos = max(1, min(int(number_of_videos), 4))

        # Configuración específica para Veo 2
        video_config = genai_types.GenerateVideosConfig(
            person_generation="dont_allow", # O "allow_adult"
            aspect_ratio=aspect_ratio, # Leído de los parámetros
            duration_seconds=duration_seconds,
            number_of_videos=number_of_videos
        )

        # Iniciar la operación de generación de video
        operation = genai_client.models.generate_videos(
            model="veo-2.0-generate-001", # Asegúrate de que este sea el nombre correcto del modelo Veo 2
            prompt=prompt_text,
            config=video_config,
        )

        logger.info(f"Operación de generación de video iniciada: {operation.name}")

        # Esperar a que la operación se complete (con timeouts y logging)
        timeout_seconds = 300  # 5 minutos de timeout total
        poll_interval_seconds = 20
        start_time = time.time()

        while not operation.done:
            current_time = time.time()
            if current_time - start_time > timeout_seconds:
                logger.error(f"Timeout esperando la generación del video (Operación: {operation.name})")
                return []

            logger.debug(f"Esperando {poll_interval_seconds}s para la operación {operation.name}. Estado actual: {operation.metadata.state if operation.metadata else 'Unknown'}")
            time.sleep(poll_interval_seconds)
            try:
                # Re-fetch the operation object to get the latest status.
                operation = genai_client.operations.get(name=operation.name) # Use operation.name
                logger.debug(f"Estado de la operación {operation.name}: {'Done' if operation.done else 'Running'}. Progreso: {operation.metadata.progress_percent if operation.metadata and hasattr(operation.metadata, 'progress_percent') else 'N/A'}")
            except Exception as poll_error:
                logger.error(f"Error al obtener el estado de la operación {operation.name}: {poll_error}")
                # Consider if this should be a critical failure or allow retries
                time.sleep(poll_interval_seconds) # Wait before retrying poll

        # Procesar la respuesta
        video_urls = []
        if operation.done and operation.response:
            if hasattr(operation.response, 'generated_videos') and operation.response.generated_videos:
                for n, generated_video_container in enumerate(operation.response.generated_videos):
                    try:
                        # The actual video data might be nested, e.g. generated_video_container.video
                        # Check the exact structure from SDK documentation or by inspecting the object.
                        # Assuming 'generated_video_container' itself has 'video' attribute which then has 'uri' or 'data'
                        
                        # Let's assume 'generated_video_container' is the direct video object based on previous logic
                        # and it might have a 'uri' or 'data' attribute, or a 'file_resource' which has 'uri'.
                        # The existing code uses generated_video.video.save() or generated_video.video.name
                        
                        video_resource = None
                        if hasattr(generated_video_container, 'video'): # Common pattern: container has a 'video' attribute
                            video_resource = generated_video_container.video
                        elif hasattr(generated_video_container, 'file_resource'): # Another possible pattern
                             video_resource = generated_video_container.file_resource
                        else:
                            logger.warning(f"Video container {n} does not have a directly accessible 'video' or 'file_resource' attribute. Inspect object: {generated_video_container}")
                            # Try to access attributes that might hold the video data or reference
                            # This part might need adjustment based on actual SDK response object structure
                            if hasattr(generated_video_container, 'data'): # Example if data is directly on container
                                video_resource = generated_video_container 
                            # Add more checks if necessary based on SDK

                        if not video_resource:
                            logger.error(f"No video resource found in generated_video_container {n}")
                            continue

                        timestamp = int(time.time())
                        filename = f"generated_video_{timestamp}_{n}.mp4"
                        filepath = os.path.join(UPLOAD_FOLDER, filename)

                        logger.info(f"Procesando video {n+1}/{len(operation.response.generated_videos)}...")

                        # Attempt to save or download the video
                        if hasattr(video_resource, 'save') and callable(video_resource.save):
                            logger.info(f"Intentando guardar video usando .save() para {filename}")
                            video_resource.save(filepath)
                            logger.info(f"Video guardado en: {filepath} usando .save()")
                        elif hasattr(video_resource, 'uri'): # If there's a URI, try to download
                            logger.info(f"Intentando descargar video desde URI: {video_resource.uri} para {filename}")
                            # The SDK might provide a direct download method or require using genai_client.files.download
                            # Assuming genai_client.files.get(name=uri).download() if uri is a resource name
                            # This part is speculative and needs to match the SDK's way of handling URIs.
                            # The previous code used genai_client.files.get(name=video_resource.name)
                            # then genai_client.files.download(name=file_info.name)
                            # This implies video_resource should have a 'name' attribute if 'save' is not present.
                            if hasattr(video_resource, 'name'):
                                file_info = genai_client.files.get(name=video_resource.name)
                                if file_info and hasattr(file_info, 'uri') and not filepath.startswith("gs://"): # Check if it's a GCS URI
                                     # If file_info.uri is a GCS URI, direct download might not be the way
                                     logger.info(f"Video resource name: {video_resource.name}, URI: {file_info.uri}")
                                     # The download method should handle fetching the bytes
                                     downloaded_content = genai_client.files.download(name=video_resource.name)
                                     with open(filepath, 'wb') as f:
                                         f.write(downloaded_content)
                                     logger.info(f"Video descargado y guardado en: {filepath}")
                                elif filepath.startswith("gs://"):
                                    logger.warning(f"Video URI es una ruta GCS: {file_info.uri}. Se requiere un manejo especial o acceso directo.")
                                    # For GCS URIs, the client might not be able to directly download.
                                    # The application would need GCS access configured or the URI itself might be the deliverable.
                                    # For this example, we'll assume direct download is possible or URI is the link.
                                    # If the URI is the public URL, we can just use it.
                                    # This part needs clarification on how GCS URIs are handled by the SDK for end-user access.
                                    # Adding the GCS URI directly if it's a valid URL.
                                    if file_info.uri.startswith("https://"): # Simplistic check
                                        video_urls.append(file_info.uri)
                                        logger.info(f"Usando GCS URI directamente: {file_info.uri}")
                                        continue # Skip local saving if GCS URI is used directly
                                else:
                                     logger.error(f"No se pudo determinar cómo descargar el video para {filename} desde el recurso: {video_resource}")
                                     continue
                            else:
                                logger.error(f"Video resource para {filename} no tiene método 'save' ni atributo 'name' para descarga.")
                                continue
                        else:
                            logger.error(f"No se pudo guardar o descargar el video {n}. El objeto video_resource no tiene 'save' ni 'uri'/'name'. Atributos: {dir(video_resource)}")
                            continue
                        
                        video_url = f"/uploads/{filename}"
                        video_urls.append(video_url)

                    except Exception as video_save_error:
                        logger.error(f"Error al procesar o guardar el video {n}: {str(video_save_error)}", exc_info=True)
                
                if video_urls:
                    logger.info(f"Se procesaron y guardaron {len(video_urls)} videos.")
                else:
                    logger.warning(f"La operación {operation.name} finalizó, se encontraron videos generados, pero ninguno pudo ser procesado/guardado.")
            else:
                # Log details if response structure is unexpected
                logger.warning(f"La operación {operation.name} finalizó pero no se encontraron 'generated_videos' en la respuesta o la respuesta está vacía.")
                if operation.error:
                    logger.error(f"La operación de generación de video falló con error: {operation.error.message} (Código: {operation.error.code})")
        else:
            # Handle cases where operation didn't complete successfully or response is missing
            if operation.error:
                logger.error(f"La operación de generación de video falló con error: {operation.error.message} (Código: {operation.error.code})")
            else:
                logger.warning(f"La operación {operation.name} no finalizó correctamente o no tuvo respuesta. Estado: {'Done' if operation.done else 'Running'}")


        return video_urls

    except genai_types.generation_types.BlockedPromptException as bpe:
        logger.error(f"Generación de video bloqueada debido al prompt: {bpe}")
        raise  # Re-raise to be caught by the caller task
    except Exception as e:
        logger.error(f"Error en generate_video_from_text: {str(e)}", exc_info=True)
        # Consider re-raising or returning a specific error object/message
        return [] # Return empty list on other errors

@with_retries()
def generate_image_from_text(prompt_text):
    """
    Genera una imagen a partir de un prompt de texto usando Gemini Flash.

    Args:
        prompt_text (str): El texto que describe la imagen a generar.

    Returns:
        str: URL de la imagen generada o un mensaje de error.
    """
    try:
        logger.info(f"Generando imagen desde texto: '{prompt_text}'")
        
        # Usar el modelo global image_gen_model si está disponible y configurado correctamente.
        # Esto asegura consistencia en el nombre del modelo y sus configuraciones.
        global image_gen_model # Necesario para acceder al modelo global
        if image_gen_model is None:
            logger.error("El modelo global de generación de imágenes (image_gen_model) no está inicializado.")
            return "Error: El servicio de generación de imágenes no está disponible actualmente."

        # No es necesario genai.configure aquí, ya está configurado globalmente.
        # No es necesario definir model_name, generation_config, safety_settings localmente
        # si usamos el image_gen_model global que ya los tiene.
        
        logger.info(f"Usando el modelo global de generación de imágenes: {image_gen_model.model_name}")

        # Asegurarse de que el directorio de imágenes generadas exista
        generated_images_dir = os.path.join(UPLOAD_FOLDER)
        if not os.path.exists(generated_images_dir):
            os.makedirs(generated_images_dir)
            logger.info(f"Directorio creado: {generated_images_dir}")
        
        # Realizar la llamada al modelo para generación de imágenes usando el modelo global
        response = image_gen_model.generate_content(
            prompt_text,
            # generation_config y safety_settings ya están en el image_gen_model global
            stream=False
        )
        
        # Procesar la respuesta con logging mejorado
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            try:
                                # Guardar la imagen en el servidor
                                inline_data = part.inline_data
                                image_data = inline_data.data
                                image_mime = inline_data.mime_type
                                
                                # Crear un nombre de archivo único
                                timestamp = int(time.time())
                                file_extension = mimetypes.guess_extension(image_mime) or '.png'
                                filename = f"generated_image_{timestamp}{file_extension}"
                                filepath = os.path.join(generated_images_dir, filename)
                                
                                # Guardar la imagen - decodificar base64 si es necesario
                                if isinstance(image_data, str):
                                    if image_data.startswith('data:'):
                                        # Es una cadena base64 con prefijo
                                        header, encoded = image_data.split(",", 1)
                                        image_data = base64.b64decode(encoded)
                                    else:
                                        # Es una cadena base64 sin prefijo
                                        image_data = base64.b64decode(image_data)
                                
                                # Guardar la imagen usando la función auxiliar
                                save_binary_file(filepath, image_data)
                                
                                # Crear URL para la imagen
                                image_url = f"/uploads/{filename}"
                                logger.info(f"Imagen generada guardada en: {filepath}")
                                return f"\n[GENERATED_IMAGE:{image_url}]"
                            except Exception as img_save_error:
                                logger.error(f"Error al guardar la imagen generada: {str(img_save_error)}")
                                return f"Error al guardar la imagen generada: {str(img_save_error)}"
                        elif hasattr(part, 'text') and part.text:
                            # Si hay texto pero no imagen, lo registramos con más detalle
                            text_content = part.text
                            logger.warning(f"El modelo devolvió texto en lugar de imagen: {text_content[:200]}...")
                            # Verificar si el texto indica un bloqueo de seguridad
                            if any(term in text_content.lower() for term in ['safety', 'seguridad', 'block', 'bloqueado', 'policy', 'política']):
                                logger.warning("Posible bloqueo por filtros de seguridad detectado en el texto de respuesta")
                                return f"El modelo no pudo generar la imagen debido a filtros de seguridad: {text_content[:200]}..."
                            return f"El modelo devolvió texto en lugar de imagen: {text_content[:200]}..."
                    
                    # Verificar si hay información sobre la razón de finalización
                    if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                        logger.warning(f"Razón de finalización: {candidate.finish_reason}")
                        if str(candidate.finish_reason).lower() != 'stop':
                            return f"Generación interrumpida: {candidate.finish_reason}"
        elif hasattr(response, 'text'):
            # Si la respuesta tiene texto directamente
            text_content = response.text
            logger.warning(f"El modelo devolvió solo texto: {text_content[:200]}...")
            # Verificar si el texto indica un bloqueo de seguridad
            if any(term in text_content.lower() for term in ['safety', 'seguridad', 'block', 'bloqueado', 'policy', 'política']):
                logger.warning("Posible bloqueo por filtros de seguridad detectado en el texto de respuesta")
                return f"El modelo no pudo generar la imagen debido a filtros de seguridad: {text_content[:200]}..."
            return f"El modelo devolvió texto en lugar de imagen: {text_content[:200]}..."
        elif hasattr(response, 'parts'):
            # Intentar procesar directamente las partes de la respuesta
            for part in response.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    try:
                        # Guardar la imagen en el servidor
                        inline_data = part.inline_data
                        image_data = inline_data.data
                        image_mime = inline_data.mime_type
                        
                        # Crear un nombre de archivo único
                        timestamp = int(time.time())
                        file_extension = mimetypes.guess_extension(image_mime) or '.png'
                        filename = f"generated_image_{timestamp}{file_extension}"
                        filepath = os.path.join(generated_images_dir, filename)
                        
                        # Guardar la imagen - decodificar base64 si es necesario
                        if isinstance(image_data, str):
                            if image_data.startswith('data:'):
                                # Es una cadena base64 con prefijo
                                header, encoded = image_data.split(",", 1)
                                image_data = base64.b64decode(encoded)
                            else:
                                # Es una cadena base64 sin prefijo
                                image_data = base64.b64decode(image_data)
                        
                        # Guardar la imagen usando la función auxiliar
                        save_binary_file(filepath, image_data)
                        
                        # Crear URL para la imagen
                        image_url = f"/uploads/{filename}"
                        logger.info(f"Imagen generada guardada en: {filepath}")
                        return f"\n[GENERATED_IMAGE:{image_url}]"
                    except Exception as img_save_error:
                        logger.error(f"Error al guardar la imagen generada: {str(img_save_error)}")
                        return f"Error al guardar la imagen generada: {str(img_save_error)}"
                elif hasattr(part, 'text') and part.text:
                    # Si hay texto en las partes pero no imagen
                    text_content = part.text
                    logger.warning(f"Parte de texto encontrada en la respuesta: {text_content[:200]}...")
                    # Verificar si el texto indica un bloqueo de seguridad
                    if any(term in text_content.lower() for term in ['safety', 'seguridad', 'block', 'bloqueado', 'policy', 'política']):
                        logger.warning("Posible bloqueo por filtros de seguridad detectado en el texto de respuesta")
                        return f"El modelo no pudo generar la imagen debido a filtros de seguridad: {text_content[:200]}..."
        
        # Intentar extraer la imagen de la respuesta como un todo
        try:
            if hasattr(response, 'image') and response.image:
                # Guardar la imagen en el servidor
                image_data = response.image
                image_mime = "image/png"  # Asumimos PNG por defecto
                
                # Crear un nombre de archivo único
                timestamp = int(time.time())
                filename = f"generated_image_{timestamp}.png"
                filepath = os.path.join(generated_images_dir, filename)
                
                # Guardar la imagen usando la función auxiliar
                save_binary_file(filepath, image_data)
                
                # Crear URL para la imagen
                image_url = f"/uploads/{filename}"
                logger.info(f"Imagen generada guardada en: {filepath}")
                return f"\n[GENERATED_IMAGE:{image_url}]"
        except Exception as e:
            logger.error(f"Error al procesar la imagen de la respuesta: {str(e)}")
        
        # Verificar si hay información de prompt_feedback (bloqueos de seguridad)
        try:
            if hasattr(response, 'prompt_feedback'):
                prompt_feedback = response.prompt_feedback
                logger.warning(f"Información de prompt_feedback: {prompt_feedback}")
                
                if hasattr(prompt_feedback, 'block_reason') and prompt_feedback.block_reason:
                    block_reason = prompt_feedback.block_reason
                    logger.warning(f"Generación bloqueada por seguridad: {block_reason}")
                    return f"La generación de imagen fue bloqueada por filtros de seguridad ({block_reason}). Intenta con un prompt diferente."
                
                if hasattr(prompt_feedback, 'safety_ratings') and prompt_feedback.safety_ratings:
                    safety_ratings = prompt_feedback.safety_ratings
                    logger.warning(f"Safety ratings: {safety_ratings}")
                    # Verificar si alguna calificación de seguridad está por encima del umbral
                    high_ratings = [rating for rating in safety_ratings if hasattr(rating, 'severity') and rating.severity >= 3]
                    if high_ratings:
                        categories = [rating.category for rating in high_ratings if hasattr(rating, 'category')]
                        logger.warning(f"Categorías de seguridad con alta severidad: {categories}")
                        return f"La generación de imagen fue bloqueada por filtros de seguridad en las categorías: {', '.join(categories)}. Intenta con un prompt diferente."
        except Exception as e:
            logger.error(f"Error al analizar prompt_feedback: {str(e)}")
        
        # Registrar la estructura completa de la respuesta para depuración
        logger.error(f"Estructura de respuesta completa: {str(response)}")
        logger.error(f"Atributos disponibles en la respuesta: {dir(response)}")
        
        return "No se pudo generar la imagen. El modelo no devolvió datos de imagen. Revisa los logs para más detalles."
    except Exception as e:
        logger.error(f"Error en generate_image_from_text: {str(e)}", exc_info=True)
        return f"Error al generar la imagen: {str(e)}"

def get_gemini_response(conversation_history, user_message, images=None):
    """
    Genera una respuesta utilizando el modelo Gemini basada en el historial de conversación,
    el mensaje del usuario y opcionalmente imágenes.
    
    Args:
        conversation_history: Lista de objetos Message con el historial de la conversación
        user_message: Mensaje de texto del usuario
        images: Lista de imágenes procesadas para visión (opcional)
    
    Returns:
        str: Respuesta generada por el modelo
    """
    try:
        logger.info(f"Generando respuesta con Gemini. Mensaje: {user_message[:50]}{'...' if len(user_message) > 50 else ''}")
        logger.info(f"Imágenes adjuntas: {len(images) if images else 0}")
        
        # Configurar el modelo Gemini
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Configuración de generación
        generation_config = {
            "temperature": 0.9,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 2048,
        }
        
        # Configuración de seguridad
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # Crear el modelo
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",    # Última versión Gemini 2.0 Flash
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Preparar el historial de la conversación para el modelo
        chat_history = []
        for msg in conversation_history:
            chat_history.append({"role": msg.role, "parts": [{"text": msg.content}]})
        
        # Iniciar chat con historial
        chat = model.start_chat(history=chat_history)
        
        # Preparar el mensaje del usuario
        parts = []
        if user_message:
            parts.append({"text": user_message})
        
        # Agregar imágenes si existen
        if images:
            for img in images:
                parts.append({
                    "inline_data": {
                        "mime_type": img['mime_type'],
                        "data": img['data']
                    }
                })
            # Si no hay mensaje de texto pero hay imágenes, agregar un prompt por defecto
            if not user_message:
                parts.append({"text": "Describe lo que ves en esta imagen"})
        
        # Enviar mensaje y obtener respuesta
        response = chat.send_message(parts)
        if hasattr(response, 'resolve'):
            response.resolve()
        
        # Extraer el texto de la respuesta
        assistant_response = response.text
        logger.info(f"Respuesta generada: {assistant_response[:50]}{'...' if len(assistant_response) > 50 else ''}")
        
        return assistant_response
        
    except Exception as e:
        logger.error(f"Error en get_gemini_response: {str(e)}", exc_info=True)
        return f"Error al generar respuesta: {str(e)}"

import base64
import mimetypes
from functools import wraps

# Decorador para reintentos (si no existe, definir uno simple)
def with_retries(retries=3, delay=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}/{retries} failed for {func.__name__}: {e}")
                    last_exception = e
                    time.sleep(delay)
            logger.error(f"{func.__name__} failed after {retries} retries.")
            raise last_exception
        return wrapper
    return decorator

# Función auxiliar para guardar mensajes (si no existe)
def save_message_to_db(conversation_id, content, role):
    try:
        message = Message(conversation_id=conversation_id, content=content, role=role)
        db.session.add(message)
        db.session.commit()
        logger.debug(f"Saved message to DB: ConvID={conversation_id}, Role={role}, Content='{content[:50]}...'")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving message to DB: {e}")

# Función auxiliar para guardar archivos binarios (si no existe)
def save_binary_file(filepath, data):
    try:
        with open(filepath, 'wb') as f:
            f.write(data)
        logger.info(f"File saved successfully: {filepath}")
    except Exception as e:
        logger.error(f"Error saving binary file {filepath}: {e}")
        raise

@app.route('/chat', methods=['POST'])
@login_required
def handle_chat_post():
    # This route handles the initial POST request from the frontend
    # It starts the generation process and returns an initial JSON response.
    # The actual result will be sent via Socket.IO.
    try:
        user_message = request.form.get('message', '').strip()
        conversation_id_str = request.form.get('conversation_id')
        model_type = request.form.get('model', 'gemini')
        files = request.files.getlist('attachments') # Use request.files for FormData
        is_web_search = request.form.get('web_search', 'false').lower() == 'true'
        # Get video params if model is video
        duration_seconds = request.form.get('durationSeconds')
        number_of_videos = request.form.get('numberOfVideos')

        # Try to get SID from session if stored, otherwise None
        sid = session.get('sid') 
        logger.debug(f"Received POST /chat - ConvID: {conversation_id_str}, Model: {model_type}, Files: {len(files)}, WebSearch: {is_web_search}, SID: {sid}")

        # --- Get or Create Conversation --- 
        conversation_id = None
        if not conversation_id_str or conversation_id_str.lower() == 'null' or conversation_id_str == 'undefined':
            conversation = Conversation(user_id=current_user.id, model_name=model_type, title="Nueva Conversación")
            db.session.add(conversation)
            db.session.commit()
            conversation_id = conversation.id
            logger.info(f"Created new conversation via POST: {conversation_id}")
            # Emit new conversation info immediately if created here
            socketio.emit('conversation_update', {
                'id': conversation.id,
                'title': conversation.title,
                'starred': conversation.starred,
                'created_at': conversation.created_at.isoformat()
            }, room=sid) # Emit to specific user if SID is known
        else:
            try:
                conversation_id = int(conversation_id_str)
                conversation = db.session.get(Conversation, conversation_id)
                if not conversation or conversation.user_id != current_user.id:
                    logger.error(f"Invalid or unauthorized conversation ID: {conversation_id}")
                    return jsonify({'status': 'error', 'message': 'Conversación inválida o no autorizada'}), 403
            except ValueError:
                 logger.error(f"Invalid conversation ID format: {conversation_id_str}")
                 return jsonify({'status': 'error', 'message': 'ID de conversación inválido'}), 400

        # --- Process Attachments (Images) --- 
        processed_images = []
        if files:
            logger.debug(f"Processing {len(files)} files from POST")
            for file in files:
                if file and file.filename: # Basic check for file and filename
                    if not allowed_file(file.filename):
                        logger.warning(f"Skipping file with invalid extension: {file.filename}. Allowed: {ALLOWED_EXTENSIONS}")
                        continue # Skip to the next file

                    # Now check content type for allowed files
                    if file.content_type.startswith('image/'):
                        try:
                            # Read file content into memory
                            file_content = file.read()
                            # Encode to base64 for consistency
                            encoded_content = base64.b64encode(file_content).decode('utf-8')
                            processed_images.append({
                                'mime_type': file.content_type,
                                'data': encoded_content # Send base64 encoded data
                            })
                            logger.debug(f"Processed image: {file.filename}")
                        except Exception as img_proc_error:
                            logger.error(f"Error processing image {file.filename}: {img_proc_error}")
                    else:
                        # This case means allowed_file() was true, but content_type is not image.
                        logger.warning(f"Skipping file with allowed extension but non-image content type: {file.filename} (Content-Type: {file.content_type})")
                else: # Handle cases where file object or filename might be missing
                    logger.warning("Received a file object without a filename or the file object itself is invalid.")
            
            if not processed_images and files: # This log is after attempting to process all files
                 logger.warning("Files were attached but none could be processed as valid images (either due to extension, content type, or processing error).")
                 # Decide if this is an error or just a note

        # --- Save User Message --- 
        if user_message or processed_images: # Save even if only images are sent
            db_message_content = user_message
            if processed_images:
                db_message_content += f"\n[{len(processed_images)} image(s) attached]"
            save_message_to_db(conversation_id, db_message_content.strip(), 'user')
            # Frontend should optimistically display the user message

        # --- Handle Title Generation --- 
        if conversation.title == "Nueva Conversación" and user_message:
            try:
                title_prompt = f"Generate a short, descriptive title (max 5 words) for a conversation that starts with: {user_message}"
                generated_title = None
                if groq_client: # Prioritize Groq for speed if available
                    title_model_name = "meta-llama/llama-4-maverick-17b-128e-instruct"
                    title_messages = [{"role": "user", "content": title_prompt}]
                    title_max_tokens = 15
                    title_temp = 0.5
                    logger.debug(f"Groq Title Gen Request: Model='{title_model_name}', Messages={json.dumps(title_messages)}, MaxTokens={title_max_tokens}, Temp={title_temp}")
                    title_completion = groq_client.chat.completions.create(
                        model=title_model_name,
                        messages=title_messages,
                        max_tokens=title_max_tokens,
                        temperature=title_temp
                    )
                    logger.debug(f"Groq Title Gen Raw Response: {title_completion.model_dump_json(indent=2)}")
                    generated_title = title_completion.choices[0].message.content.strip().replace('"', '')
                    logger.debug(f"Groq Extracted Title: {generated_title}")
                elif GOOGLE_API_KEY: # Fallback to Gemini if Groq unavailable
                     # Use a faster Gemini model if possible, or the main one
                     # title_response = model.generate_content(title_prompt) # This might be slow
                     # generated_title = title_response.text.strip().replace('"', '')
                     pass # Skipping Gemini title gen for now to keep it fast
                
                conversation.title = generated_title[:50] if generated_title else user_message[:50].strip()
                db.session.commit()
                logger.info(f"Generated title for Conv {conversation_id}: {conversation.title}")
                # Emit title update
                socketio.emit('conversation_update', {
                    'id': conversation_id,
                    'title': conversation.title
                }, room=sid) # Emit to specific user if SID is known
            except Exception as title_err:
                 logger.error(f"Error generating title: {title_err}", exc_info=True)
                 # Continue without title generation if it fails

        # --- Trigger Background Task for Response Generation --- 
        task_data = {
            'conversation_id': conversation_id,
            'user_message': user_message,
            'processed_images': processed_images,
            'model_type': model_type,
            'is_web_search': is_web_search,
            'video_params': {
                'duration': duration_seconds,
                'count': number_of_videos,
                'aspect_ratio': request.form.get('video_aspect_ratio', '16:9') # Leer aspect ratio desde form
            } if model_type == 'kkty2-video' else None,
            'sid': sid # Pass SID to the background task
        }
        socketio.start_background_task(target=generate_response_task, **task_data)

        # Return immediate JSON response to the fetch call
        return jsonify({'status': 'processing', 'message': 'Solicitud recibida, procesando...', 'conversation_id': conversation_id})

    except Exception as e:
        logger.error(f"Error in /chat POST handler: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error interno del servidor: {str(e)}'}), 500

# Separate function for background task
def generate_response_task(conversation_id, user_message, processed_images, model_type, is_web_search, video_params, sid):
    with app.app_context(): # Need app context for DB operations and config
        try:
            logger.info(f"Background task started for Conv {conversation_id}, Model: {model_type}, SID: {sid}")
            
            # --- Lógica de Generación de Video (kkty2-video) --- 
            if model_type == 'kkty2-video':
                if not user_message:
                    error_msg = 'Por favor, proporciona un prompt para generar el video.'
                    socketio.emit('message', {'role': 'assistant', 'content': error_msg, 'done': True, 'conversation_id': conversation_id}, room=sid)
                    save_message_to_db(conversation_id, error_msg, 'assistant')
                    return

                # Safely get video params with defaults
                duration = 5
                count = 1
                try:
                    if video_params:
                        duration = int(video_params.get('duration', 5))
                        count = int(video_params.get('count', 1))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid video parameters received: {video_params}. Using defaults.")
                
                # Clamp values to reasonable limits
                duration = max(5, min(duration, 8))
                count = max(1, min(count, 4))
                aspect = video_params.get('aspect_ratio', '16:9')
                if aspect not in ['16:9', '9:16']:
                    aspect = '16:9' # Default a 16:9 si es inválido

                logger.info(f"Video generation request: Duration={duration}, Count={count}, Aspect={aspect}")

                try:
                    # Emit message indicating start
                    start_msg = f'Generando {count} video(s) de {duration}s con Veo 2... (esto puede tardar unos minutos)'
                    socketio.emit('message', {'role': 'assistant', 'content': start_msg, 'done': False, 'conversation_id': conversation_id}, room=sid)
                    
                    # Call the video generation function
                    video_urls = generate_video_from_text(
                        prompt_text=user_message,
                        duration_seconds=duration,
                        number_of_videos=count,
                        aspect_ratio=aspect
                    )

                    if video_urls:
                        response_content = f"Aquí tienes los videos generados a partir de '{user_message}':\n"
                        for url in video_urls:
                            response_content += f"[GENERATED_VIDEO:{url}]\n"
                        socketio.emit('message', {'role': 'assistant', 'content': response_content, 'done': True, 'conversation_id': conversation_id, 'model_type': model_type}, room=sid)
                        save_message_to_db(conversation_id, response_content, 'assistant')
                    else:
                        # This case might happen if generate_video_from_text returns [] on failure
                        error_message = "Lo siento, no pude generar los videos con Veo 2. Hubo un problema durante la generación. Por favor, revisa el prompt, asegúrate de que el servicio Veo 2 esté activo y tu API key tenga permisos, o intenta de nuevo más tarde."
                        socketio.emit('message', {'role': 'assistant', 'content': error_message, 'done': True, 'conversation_id': conversation_id, 'model_type': model_type}, room=sid)
                        save_message_to_db(conversation_id, error_message, 'assistant')
                
                except genai_types.generation_types.BlockedPromptException as bpe:
                    logger.error(f"Generación de video bloqueada debido al prompt para Conv {conversation_id}: {bpe}")
                    error_msg = "Tu solicitud de generación de video fue bloqueada porque el prompt infringe las políticas de seguridad. Por favor, modifica el prompt e intenta de nuevo."
                    socketio.emit('message', {'role': 'assistant', 'content': error_msg, 'done': True, 'conversation_id': conversation_id, 'model_type': model_type}, room=sid)
                    save_message_to_db(conversation_id, error_msg, 'assistant')
                except Exception as video_error:
                    logger.error(f"Error generando video con Veo 2 para Conv {conversation_id}: {str(video_error)}", exc_info=True)
                    error_msg = f'Error al generar el video con Veo 2: {str(video_error)}.'
                    if "API key not valid" in str(video_error) or "PERMISSION_DENIED" in str(video_error):
                         error_msg = "Error: La clave API para la generación de video no es válida, no tiene permisos para Veo 2 o falta."
                    elif "quota" in str(video_error).lower():
                         error_msg = "Error: Se ha excedido la cuota para la generación de video."
                    elif "client is not configured" in str(video_error).lower():
                        error_msg = "Error: El cliente de generación de video no está configurado correctamente. Revisa la configuración del servidor."
                    
                    socketio.emit('message', {'role': 'assistant', 'content': error_msg, 'done': True, 'conversation_id': conversation_id, 'model_type': model_type}, room=sid)
                    save_message_to_db(conversation_id, error_msg, 'assistant')
                return # End task after video logic

            # --- Other Model Logic (Gemini, Groq, Image Gen, Web Search etc.) ---
            # Get conversation history (only needed for models that use it)
            previous_messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()
            
            assistant_response = ""
            is_streaming = False
            try:
                if is_web_search:
                     logger.info(f"Performing web search for: {user_message}")
                     try:
                         search_prompt = f"Actúa como un asistente de búsqueda web experto. Busca información sobre: {user_message}. Proporciona una respuesta detallada y actualizada."
                         # Ensure 'model' is the correct Gemini model instance configured for text
                         if not model:
                             raise Exception("Gemini text model not initialized.")
                         response = model.generate_content(search_prompt)
                         assistant_response = response.text
                     except Exception as search_err:
                         logger.error(f"Error during web search generation: {search_err}")
                         assistant_response = f"Error al realizar la búsqueda web: {search_err}"

                elif model_type == 'gemini':
                    if not model:
                         raise Exception("Gemini model not initialized.")
                    # Adapt get_gemini_response if needed, ensure it handles base64 images
                    assistant_response = get_gemini_response(previous_messages, user_message, images=processed_images)
                
                elif model_type == 'groq':
                    if not groq_client:
                        raise Exception("Groq API key not configured.")
                    is_streaming = True # Groq uses streaming
                    
                    # Prepare messages for Groq
                    conversation_history_for_groq = []
                    for msg in previous_messages:
                         # Ensure history format is correct for Groq
                         role = msg.role if msg.role in ['user', 'assistant'] else 'user' # Default unknown roles to user
                         conversation_history_for_groq.append({"role": role, "content": msg.content})

                    user_content_for_groq = user_message
                    if processed_images:
                         # Check if a vision model is available and selected for Groq
                         # For now, assume text model and add note
                         user_content_for_groq += "\n[Nota: El usuario adjuntó imágenes. No puedo verlas directamente.]" 
                    
                    messages_for_groq = conversation_history_for_groq + [{"role": "user", "content": user_content_for_groq}]
                    
                    # Select appropriate Groq model
                    groq_model_name = "meta-llama/llama-4-maverick-17b-128e-instruct"  # Llama 4 Maverick (Meta)
                    # if processed_images and groq_vision_model_available:
                    #     groq_model_name = "groq-vision-model-name" # Keep vision model separate if needed
                    
                    groq_request_params = {
                        "model": groq_model_name,
                        "messages": messages_for_groq,
                        "temperature": 0.7,
                        "max_tokens": 2048,
                        "stream": True
                    }
                    logger.debug(f"Groq Chat Request: {json.dumps(groq_request_params)}")

                    completion = groq_client.chat.completions.create(**groq_request_params)
                    
                    logger.info("Groq stream initiated.")
                    full_groq_response = ""
                    chunk_counter = 0
                    for chunk in completion:
                        if chunk_counter < 3: # Log first 3 chunks in detail
                            logger.debug(f"Groq Stream Chunk [{chunk_counter}]: {chunk.model_dump_json(indent=2)}")
                        
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            chunk_content = chunk.choices[0].delta.content
                            full_groq_response += chunk_content
                            logger.debug(f"Groq Stream: Received content chunk (length: {len(chunk_content)})")
                            # Emit progress chunks
                            socketio.emit('message_progress', {'content': chunk_content, 'conversation_id': conversation_id}, room=sid)
                        elif chunk.choices and chunk.choices[0].delta and not chunk.choices[0].delta.content:
                             logger.debug(f"Groq Stream: Received empty delta chunk (possibly finish reason): {chunk.model_dump_json(indent=2)}")
                        else:
                             logger.debug(f"Groq Stream: Received non-content or unexpected chunk: {chunk.model_dump_json(indent=2)}")
                        chunk_counter += 1
                    
                    logger.info(f"Groq stream finished. Total chunks processed: {chunk_counter}")
                    assistant_response = full_groq_response # Store full response for DB
                    logger.debug(f"Groq Full Assembled Response (first 200 chars): {assistant_response[:200]}")
                    # Emit final message marker for streaming
                    socketio.emit('message', {'role': 'assistant', 'content': '', 'done': True, 'conversation_id': conversation_id}, room=sid)

                # Add logic for image generation models if they were part of handle_message
                # elif model_type == 'gemini-flash-image':
                #     assistant_response = generate_image_from_text(user_message)
                # elif model_type == 'gemini-image-edit': # Example
                #     if processed_images:
                #         assistant_response = generate_image_edit_from_upload(processed_images[0]['data'], user_message)
                #     else:
                #         assistant_response = "Se requiere una imagen para la edición."

                else: # Default or unknown model
                    logger.warning(f"Unsupported model type requested: {model_type}")
                    assistant_response = f"Modelo '{model_type}' no soportado o no reconocido."

                # --- Emit final response (only if not streaming) --- 
                if not is_streaming:
                    socketio.emit('message', {
                        'role': 'assistant',
                        'content': assistant_response,
                        'done': True,
                        'conversation_id': conversation_id
                    }, room=sid)
                
                # --- Save Assistant Response --- 
                if assistant_response:
                    save_message_to_db(conversation_id, assistant_response, 'assistant')
                logger.info(f"Background task finished successfully for Conv {conversation_id}")

            except Exception as api_error:
                logger.error(f"Error during API call in background task (Conv {conversation_id}): {str(api_error)}", exc_info=True)
                error_msg = f"Error al generar respuesta: {str(api_error)}"
                if "429" in str(api_error):
                    error_msg = "Lo siento, hemos alcanzado el límite de la API. Por favor, intenta de nuevo más tarde."
                # Emit error message
                socketio.emit('message', {'role': 'assistant', 'content': error_msg, 'done': True, 'conversation_id': conversation_id}, room=sid)
                save_message_to_db(conversation_id, error_msg, 'assistant') # Save error message

        except Exception as task_error:
            logger.error(f"Critical error in background task generate_response_task (Conv {conversation_id}): {str(task_error)}", exc_info=True)
            # Emit generic error if task fails unexpectedly
            error_msg = f'Error interno grave al procesar la solicitud.'
            socketio.emit('message', {'role': 'assistant', 'content': error_msg, 'done': True, 'conversation_id': conversation_id}, room=sid)
            save_message_to_db(conversation_id, f'Error interno grave: {str(task_error)}', 'assistant')

# Store SID in session on connect
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        session['sid'] = request.sid
        logger.info(f"User {current_user.username} connected with SID: {request.sid}")
    else:
        logger.warning("Unauthenticated user connected")
        # Optionally disconnect unauthenticated users
        # return False 

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        logger.info(f"User {current_user.username} disconnected SID: {request.sid}")
        # Optionally clear SID from session
        # session.pop('sid', None)
    else:
        logger.info(f"Unauthenticated user disconnected SID: {request.sid}")

# Keep the original @socketio.on('message') for potential future use or other message types
# but ensure it does NOT handle the main chat generation logic anymore.
@socketio.on('message')
def handle_socket_message(data):
    # This handler is NO LONGER used for chat generation.
    # It can be used for other real-time interactions if needed.
    # logger.debug(f"Received socket message (not for chat generation): {data}")
    # # Example: Handle a 'typing' indicator
    # sid = session.get('sid')
    # if data.get('type') == 'typing' and current_user.is_authenticated:
    #      emit('typing_status', {'user': current_user.username, 'is_typing': data.get('is_typing')}, broadcast=True, include_self=False, room=sid) # Emit to others
    # pass
    # try:
    #     user_message = data.get('message', '').strip()
    #     conversation_id = data.get('conversationId')
    #     files = data.get('files', [])
    #     model_type = data.get('model', 'gemini')  # Default to gemini if not specified
    #     is_image_generation = data.get('isImageGeneration', False)  # Check if this is an image generation request
    #     is_image_edit = data.get('isImageEdit', False)  # Check if this is an image editing request
        
    #     # Si no hay ID de conversación, crear uno nuevo
    #     if not conversation_id:
    #         conversation = Conversation()
    #         # Asignar user_id solo si el usuario está autenticado
    #         if current_user.is_authenticated:
    #             conversation.user_id = current_user.id
    #         conversation.model_name = model_type
    #         conversation.title = "Nueva Conversación"
    #         db.session.add(conversation)
    #         db.session.commit()
    #         conversation_id = conversation.id
    #         logger.debug(f"Creada nueva conversación con ID: {conversation_id}")
        
    #     logger.debug(f"Recibido mensaje - ID: {conversation_id}, Texto: {user_message}, Archivos: {len(files)}, Modelo: {model_type}, Es edición de imagen: {is_image_edit}")
        
    #     # Procesar imágenes si hay
    #     processed_images = []
    #     if files:
    #         logger.debug(f"Procesando {len(files)} archivos")
    #         for file_data in files:
    #             if not file_data:
    #                 logger.error("Datos de archivo vacíos recibidos")
    #                 continue
                
    #             try:
    #                 # Decodificar la imagen base64
    #                 if isinstance(file_data, str):
    #                     if ',' in file_data:
    #                         header, encoded = file_data.split(',', 1)
    #                         logger.debug(f"Tipo de imagen detectado: {header}")
    #                     else:
    #                         encoded = file_data
                        
    #                     try:
    #                         image_data = base64.b64decode(encoded.strip())
    #                         logger.debug(f"Imagen decodificada correctamente")
    #                         processed_images.append({
    #                             'mime_type': 'image/jpeg',
    #                             'data': encoded.strip()
    #                         })
    #                     except Exception as decode_error:
    #                         logger.error(f"Error decodificando base64: {decode_error}")
    #                         continue
    #             except Exception as inner_e: # Added missing except block
    #                 logger.error(f"Error processing file data structure: {inner_e}")
    #                 continue
    #             # This except handles errors in the outer loop logic, not the inner try
    #             # except Exception as e: # This was likely misplaced or intended for outer scope
    #             #    logger.error(f"Error general procesando imagen: {str(e)}")
    #             #    continue
    #                 logger.error(f"Error general procesando imagen: {str(e)}")
    #                 continue

    #         if len(processed_images) == 0 and files:
    #             error_msg = "No se pudo procesar ninguna imagen. Formatos permitidos: png, jpg, gif, webp, jpeg. Tamaño máximo: 20MB"
    #             logger.error(error_msg)
    #             emit('message', {'role': 'assistant', 'content': error_msg})
    #             return

    #     try:
    #         # Guardar mensaje del usuario primero
    #         if user_message:  # Solo guardar si hay mensaje de texto
    #             save_message_to_db(conversation_id, user_message, 'user')
            
    #         # Obtener historial de mensajes de la conversación
    #         previous_messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()
    #         conversation_history_text = []
    #         for msg in previous_messages:
    #             conversation_history_text.append({"role": msg.role, "content": msg.content})

    #         # Generate title if this is the first message
    #         conversation = Conversation.query.get(conversation_id)
    #         if conversation and conversation.title == "Nueva Conversación" and user_message:
    #             title_prompt = f"Generate a short, descriptive title (max 3-4 words) for a conversation that starts with: {user_message}"
    #             if model_type == 'gemini':
    #                 title_response = model.generate_content(title_prompt)
    #                 conversation.title = title_response.text[:200]  # Limit title length
    #             elif model_type == 'groq' and groq_client:
    #                 title_completion = groq_client.chat.completions.create(
    #                     model="meta-llama/llama-4-maverick-17b-128e-instruct",
    #                     messages=[{"role": "user", "content": title_prompt}],
    #                     max_tokens=10
    #                 )
    #                 conversation.title = title_completion.choices[0].message.content[:200]
    #             db.session.commit()
    #             # Emit title update to frontend
    #             emit('conversation_update', {
    #                 'id': conversation_id,
    #                 'title': conversation.title
    #             })

    #         # Verificar si es una solicitud de edición de imagen
    #         if is_image_edit and processed_images:
    #             try:
    #                 logger.info("Procesando solicitud de edición de imagen")
                    
    #                 # Tomar la primera imagen procesada para editar
    #                 input_image = processed_images[0]['data']
                    
    #                 # Llamar a la función de edición de imagen
    #                 edit_result = generate_image_edit_from_upload(input_image, user_message)
                    
    #                 # Emitir la respuesta con el tipo correcto
    #                 if '[GENERATED_IMAGE:' in edit_result:
    #                     # Extraer la URL de la imagen
    #                     img_match = edit_result.strip().split('[GENERATED_IMAGE:')[1].split(']')[0]
    #                     emit('message', {
    #                         'role': 'assistant',
    #                         'type': 'image_url',
    #                         'content': img_match,
    #                         'done': True
    #                     })
    #                 else:
    #                     emit('message', {
    #                         'role': 'assistant',
    #                         'type': 'text',
    #                         'content': edit_result,
    #                         'done': True
    #                     })
                    
    #                 # Guardar la respuesta del asistente
    #                 save_message_to_db(conversation_id, edit_result, 'assistant')
                    
    #             except Exception as edit_error:
    #                 logger.error(f"Error al editar imagen: {str(edit_error)}")
    #                 error_msg = f"Error al editar la imagen: {str(edit_error)}"
    #                 emit('message', {
    #                     'role': 'assistant',
    #                     'content': error_msg,
    #                     'done': True
    #                 })
            
    #         # Verificar si es una solicitud de generación de imagen a partir de texto
    #         elif is_image_generation:
    #             try:
    #                 logger.info("Procesando solicitud de generación de imagen a partir de texto")
                    
    #                 # Llamar a la función de generación de imagen
    #                 generation_result = generate_image_from_text(user_message)
                    
    #                 # Emitir la respuesta con el tipo correcto
    #                 if '[GENERATED_IMAGE:' in generation_result:
    #                     # Extraer la URL de la imagen
    #                     img_match = generation_result.strip().split('[GENERATED_IMAGE:')[1].split(']')[0]
    #                     emit('message', {
    #                         'role': 'assistant',
    #                         'type': 'image_url',
    #                         'content': img_match,
    #                         'done': True
    #                     })
    #                 else:
    #                     emit('message', {
    #                         'role': 'assistant',
    #                         'type': 'text',
    #                         'content': generation_result,
    #                         'done': True
    #                     })
                    
    #                 # Guardar la respuesta del asistente
    #                 save_message_to_db(conversation_id, generation_result, 'assistant')
                    
    #             except Exception as gen_error:
    #                 logger.error(f"Error al generar imagen a partir de texto: {str(gen_error)}")
    #                 error_msg = f"Error al generar la imagen: {str(gen_error)}"
    #                 emit('message', {
    #                     'role': 'assistant',
    #                     'content': error_msg,
    #                     'done': True
    #                 })
                    
    #         # Generate response based on model type
    #         elif model_type == 'gemini-flash':
    #             # Generar imagen con Gemini 2.0 Flash
    #             try:
    #                 logger.info("Generando imagen con Gemini 2.0 Flash")
                    
    #                 # Configurar la API key para el modelo de generación de imágenes
    #                 genai.configure(api_key=GOOGLE_API_KEY)
                    
    #                 # Usar el modelo correcto para generación de imágenes
    #                 model_name = "gemini-2.0-flash-exp-image-generation"
                    
    #                 # Crear el modelo generativo
    #                 image_model = genai.GenerativeModel(model_name)
                    
    #                 # Preparar la solicitud para generar imagen
    #                 prompt = user_message if user_message else "Genera una imagen creativa"
                    
    #                 # Configurar para generar imagen
    #                 generation_config = {
    #                     "temperature": 0.7,
    #                     "top_p": 1.0,
    #                     "top_k": 32,
    #                     "max_output_tokens": 2048,
    #                 }
                    
    #                 # Configurar el tipo de respuesta que queremos (imagen)
    #                 response_types = ["image", "text"]
                    
    #                 # Procesar la respuesta
    #                 text_response = ""
    #                 image_url = ""
                    
    #                 # Realizar la llamada al modelo para generación de imágenes
    #                 response = image_model.generate_content(
    #                     prompt,
    #                     generation_config=generation_config
    #                 )
                    
    #                 # Procesar la respuesta completa
    #                 if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
    #                     # Procesar texto si hay
    #                     for part in response.candidates[0].content.parts:
    #                         if hasattr(part, 'text') and part.text:
    #                             text_response += part.text
                            
    #                         # Procesar imagen
    #                         if hasattr(part, 'inline_data') and part.inline_data:
    #                             try:
    #                                 # Guardar la imagen en el servidor
    #                                 inline_data = part.inline_data
    #                                 image_data = inline_data.data
    #                                 image_mime = inline_data.mime_type
                                    
    #                                 # Crear un nombre de archivo único
    #                                 timestamp = int(time.time())
    #                                 file_extension = mimetypes.guess_extension(image_mime) or '.png'
    #                                 filename = f"generated_image_{timestamp}{file_extension}"
    #                                 filepath = os.path.join(UPLOAD_FOLDER, filename)
                                    
    #                                 # Guardar la imagen - decodificar base64 si es necesario
    #                                 if isinstance(image_data, str):
    #                                     if image_data.startswith('data:'):
    #                                         # Es una cadena base64 con prefijo
    #                                         header, encoded = image_data.split(",", 1)
    #                                         image_data = base64.b64decode(encoded)
    #                                     else:
    #                                         # Es una cadena base64 sin prefijo
    #                                         image_data = base64.b64decode(image_data)
                                    
    #                                 # Guardar la imagen
    #                                 with open(filepath, "wb") as f:
    #                                     f.write(image_data)
                                    
    #                                 # Crear URL para la imagen
    #                                 image_url = f"/uploads/{filename}"
    #                                 logger.info(f"Imagen generada guardada en: {filepath}")
    #                             except Exception as img_save_error:
    #                                 logger.error(f"Error al guardar la imagen generada: {str(img_save_error)}")
    #                                 # Continuar con el proceso aunque falle el guardado de la imagen
                    
    #                 # Formatear la respuesta final con la imagen
    #                 final_response = text_response
    #                 if image_url:
    #                     final_response += f"\n[GENERATED_IMAGE:{image_url}]"
                    
    #                 # Emitir la respuesta con el tipo correcto
    #                 if '[GENERATED_IMAGE:' in final_response:
    #                     # Extraer la URL de la imagen
    #                     img_match = final_response.strip().split('[GENERATED_IMAGE:')[1].split(']')[0]
    #                     emit('message', {
    #                         'role': 'assistant',
    #                         'type': 'image_url',
    #                         'content': img_match,
    #                         'done': True
    #                     })
    #                 else:
    #                     emit('message', {
    #                         'role': 'assistant',
    #                         'type': 'text',
    #                         'content': final_response,
    #                         'done': True
    #                     })
                    
    #                 # Guardar la respuesta del asistente
    #                 save_message_to_db(conversation_id, final_response, 'assistant')
                    
    #             except Exception as img_error:
    #                 logger.error(f"Error al generar imagen: {str(img_error)}")
    #                 error_msg = f"Error al generar la imagen: {str(img_error)}"
    #                 emit('message', {
    #                     'role': 'assistant',
    #                     'content': error_msg,
    #                     'done': True
    #                 })
                    
    #         # --- Lógica de Groq ---        
    #         elif model_type == 'groq':
    #             if not groq_client:
    #                 raise Exception("Groq API no está configurada. Por favor, configure GROQ_API_KEY en el archivo .env")

    #             # Configuración común para todas las llamadas
    #             common_params = {
    #                 "temperature": 0.7,
    #                 "max_tokens": 2048,
    #                 "top_p": 1,
    #                 "stream": True,
    #                 "stop": None
    #             }

    #             # Preparar el contenido del mensaje para Groq
    #             # Groq no soporta el formato de contenido mixto de la misma manera que Gemini
    #             # Simplificamos para usar solo texto para Groq
    #             if user_message:
    #                 user_content = user_message
    #                 if processed_images:
    #                     user_content += "\n[Nota: El usuario también ha adjuntado imágenes que no se pueden procesar directamente con este modelo]"
    #             else:
    #                 user_content = "Describe lo que ves en esta imagen" if processed_images else ""
                
    #             # Crear la solicitud a la API de Groq con el historial de la conversación
    #             messages = conversation_history_text + [{"role": "user", "content": user_content}]
    #             completion = groq_client.chat.completions.create(
    #                 model="meta-llama/llama-4-maverick-17b-128e-instruct",
    #                 messages=messages,
    #                 **common_params
    #             )

    #             # Procesar la respuesta en streaming
    #             accumulated_response = ""
    #             buffer = ""
    #             buffer_size_threshold = 50  # Enviar actualizaciones cada 50 caracteres
                
    #             for chunk in completion:
    #                 if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
    #                     chunk_content = chunk.choices[0].delta.content
    #                     accumulated_response += chunk_content
    #                     buffer += chunk_content
                        
    #                     # Solo emitir actualizaciones de progreso cuando el buffer alcance cierto tamaño
    #                     if len(buffer) >= buffer_size_threshold:
    #                         emit('message_progress', {
    #                             'content': buffer,
    #                             'conversation_id': conversation_id
    #                         })
    #                         buffer = ""
                
    #             # Emitir respuesta final completa (no fragmentada)
    #             emit('message', {
    #                 'role': 'assistant',
    #                 'type': 'text',
    #                 'content': accumulated_response,
    #                 'done': True
    #             })
                
    #             # Guardar la respuesta del asistente en la base de datos
    #             save_message_to_db(conversation_id, accumulated_response, 'assistant')
    #         else:  # default to gemini
    #             # Preparar el contenido para la llamada a la API de Gemini, incluyendo el historial
    #             contents_for_gemini = []
                
    #             # Añadir mensajes del historial
    #             for msg in conversation_history_text:
    #                 # Asegurar que los roles del historial sean 'user' o 'model'
    #                 role = 'model' if msg['role'] == 'assistant' else msg['role']
    #                 # Asumiendo que msg['content'] es texto plano. Si puede incluir imágenes, se necesita lógica adicional.
    #                 contents_for_gemini.append({"role": role, "parts": [{"text": msg['content']}]})

    #             # Preparar las partes del mensaje actual del usuario
    #             current_user_parts = []
    #             if user_message:
    #                 current_user_parts.append({"text": user_message})
                
    #             # Añadir imágenes si las hay al mensaje actual del usuario
    #             if processed_images:
    #                 for img in processed_images:
    #                     current_user_parts.append({
    #                         "inline_data": {
    #                             "mime_type": img['mime_type'],
    #                             "data": img['data']
    #                         }
    #                     })
    #                 if not user_message:
    #                     # Añadir un prompt por defecto si solo se envían imágenes
    #                     current_user_parts.append({"text": "Describe lo que ves en esta imagen"})
                
    #             # Añadir el mensaje actual del usuario al contenido si hay partes
    #             if current_user_parts:
    #                 contents_for_gemini.append({"role": "user", "parts": current_user_parts})
                
    #             # Llamar a generate_content con el historial completo y el mensaje actual
    #             # Asegurarse de que contents_for_gemini no esté vacío antes de llamar
    #             if contents_for_gemini:
    #                 # --- Add logging here ---
    #                 logger.debug(f"Llamando a generate_content con el siguiente historial para conversation_id {conversation_id}:")
    #                 try:
    #                     # Usar json.dumps para una mejor visualización, manejar errores si no es serializable
    #                     logger.debug(json.dumps(contents_for_gemini, indent=2, ensure_ascii=False))
    #                 except TypeError:
    #                     logger.debug(f"Contenido no serializable (puede contener datos binarios): {contents_for_gemini}")
    #                 # --- End logging ---
    #                 response = model.generate_content(contents=contents_for_gemini)
    #                 if hasattr(response, 'resolve'):
    #                     response.resolve()
    #                 # Extraer solo el texto de la respuesta
    #                 assistant_response = response.text
    #             else:
    #                 # Manejar el caso donde no hay contenido para enviar (ej. primer mensaje vacío)
    #                 assistant_response = "Por favor, envía un mensaje o una imagen."
    #                 logger.warning("Intento de llamada a generate_content sin contenido.")
                
    #             # Emitir la respuesta
    #             emit('message', {
    #                 'role': 'assistant',
    #                 'content': assistant_response
    #             })
                
    #             # Guardar la respuesta del asistente
    #             save_message_to_db(conversation_id, assistant_response, 'assistant')
                    
    #     except Exception as api_error:
    #         logger.error(f"Error al generar respuesta: {str(api_error)}")
    #         if "429" in str(api_error):
    #             error_msg = "Lo siento, hemos alcanzado el límite de la API. Por favor, intenta de nuevo más tarde."
    #         else:
    #             error_msg = f"Error al procesar el mensaje: {str(api_error)}"
            
    #         emit('message', {
    #             'role': 'assistant',
    #             'content': error_msg,
    #             'done': True
    #         })
            
    # except Exception as e:
    #     error_msg = f"Error al procesar el mensaje: {str(e)}"
    #     logger.error(error_msg)
    #     emit('message', {
    #         'role': 'assistant',
    #         'content': error_msg
    #     })
    logger.warning("Legacy socketio.on('message') handler was called. This should ideally not happen for chat messages.")

@app.route('/api/conversations')
@login_required
def get_conversations():
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()
    return jsonify({
        'conversations': [{
            'id': conv.id,
            'title': conv.title or 'Nueva conversación',
            'starred': conv.starred,
            'created_at': conv.created_at.isoformat()
        } for conv in conversations]
    })

@app.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation():
    conversation = Conversation(user_id=current_user.id)
    db.session.add(conversation)
    db.session.commit()
    return jsonify({
        'id': conversation.id,
        'title': conversation.title or 'Nueva conversación',
        'starred': conversation.starred,
        'created_at': conversation.created_at.isoformat()
    })

@app.route('/api/conversations/<int:conversation_id>')
@login_required
def get_conversation(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if conversation.user_id != current_user.id:
        abort(403)
    
    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at.asc()).all()
    return jsonify({
        'id': conversation.id,
        'title': conversation.title or 'Nueva conversación',
        'starred': conversation.starred,
        'created_at': conversation.created_at.isoformat(),
        'messages': [{
            'id': msg.id,
            'content': msg.content,
            'role': msg.role,
            'created_at': msg.created_at.isoformat()
        } for msg in messages]
    })

@app.route('/api/conversations/<int:conversation_id>/star', methods=['POST'])
@login_required
def toggle_star(conversation_id):
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verificar que el usuario sea el propietario de la conversación
        if conversation.user_id != current_user.id:
            abort(403)
        
        # Obtener el nuevo estado de starred del JSON enviado
        data = request.get_json()
        if data and 'starred' in data:
            conversation.starred = data['starred']
            db.session.commit()
            
            logger.info(f"Conversación {conversation_id} marcada como {'destacada' if conversation.starred else 'no destacada'}")
            
            return jsonify({
                'success': True,
                'id': conversation.id,
                'starred': conversation.starred
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se proporcionó el estado de destacado'
            }), 400
    except Exception as e:
        logger.error(f"Error al cambiar estado destacado: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/uploads/<path:path>')
def send_upload(path):
    return send_from_directory('uploads', path)

@app.route('/api/search', methods=['POST'])
@login_required
def web_search():
    if not request.is_json:
        return jsonify({
            'error': 'Se requiere Content-Type: application/json'
        }), 415
    
    try:
        data = request.get_json()
        query = data.get('query', '')
        session_id = data.get('session_id', 'default')

        if not query:
            return jsonify({
                'error': 'No se proporcionó consulta de búsqueda',
                'status': 'error'
            }), 400

        try:
            response = model.generate_content(
                f"""Actúa como un asistente de búsqueda web experto. 
                Busca información sobre: {query}
                
                Proporciona una respuesta detallada y actualizada basada en la información disponible.
                Si es posible, incluye fuentes o referencias relevantes."""
            )
            
            return jsonify({
                'response': response.text,
                'session_id': session_id,
                'status': 'success'
            })

        except Exception as e:
            logger.error(f"Error en la búsqueda web: {str(e)}")
            return jsonify({
                'error': 'Error al realizar la búsqueda web',
                'details': str(e),
                'status': 'error'
            }), 500

    except Exception as e:
        logger.error(f"Error en la ruta /api/search: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/reset', methods=['POST'])
@login_required
def reset_chat():
    try:
        data = request.get_json()
        session_id = data.get('session_id', 'default')
        
        if session_id in chat_sessions:
            del chat_sessions[session_id]
        
        return jsonify({
            'status': 'success',
            'message': 'Chat session reset successfully'
        })
    except Exception as e:
        logger.error(f"Error resetting chat: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/test_api')
def test_api():
    try:
        # Verificar y usar la API key del entorno
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY no está configurada en el archivo .env")
        genai.configure(api_key=api_key)
        
        # Intentar crear el modelo
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Hacer una prueba simple
        response = model.generate_content("Di hola y confirma que estás funcionando correctamente.")
        
        return jsonify({
            'status': 'success',
            'message': 'API configurada correctamente',
            'response': response.text
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al configurar la API: {str(e)}'
        }), 500

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            logger.info("Base de datos creada exitosamente")
        except Exception as e:
            logger.error(f"Error al crear la base de datos: {e}")
    
    # Configuración para entorno de desarrollo y producción
    port = int(os.environ.get('PORT', 5000)) # Changed default port to 5000
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    # En entorno local usamos socketio.run, en producción gunicorn maneja esto
    if os.environ.get('RENDER') or os.environ.get('PRODUCTION'):
        # En producción, gunicorn se encarga de ejecutar la app
        app.logger.info(f"Ejecutando en modo producción en puerto {port}")
    else:
        # En desarrollo local
        app.logger.info(f"Ejecutando en modo desarrollo en puerto {port}")
        # Use the modified port variable here
        socketio.run(app, debug=debug, host='0.0.0.0', port=port)
