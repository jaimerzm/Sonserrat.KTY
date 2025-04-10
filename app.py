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

 # Importar módulos para funcionalidades avanzadas
from vector_db import init_vector_db, get_vector_db
from conversation_summary import process_conversation_summary
from search_api import search_web, format_search_results_for_llm

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
    Guarda un mensaje en la base de datos relacional y en la base de datos vectorial.
    
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
        
        # Guardar en la base de datos vectorial si está disponible
        try:
            vector_db = get_vector_db()
            if vector_db:
                vector_db.add_message(
                    message_id=message.id,
                    conversation_id=conversation_id,
                    content=content,
                    role=role,
                    created_at=message.created_at
                )
                logger.debug(f"Mensaje {message.id} guardado en la base de datos vectorial")
        except Exception as vector_error:
            logger.error(f"Error guardando mensaje en la base de datos vectorial: {str(vector_error)}")
            # Continuar aunque falle el guardado en la base de datos vectorial
        
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
        model_name="gemini-1.5-pro",
        generation_config=generation_config,
        safety_settings=safety_settings
    )
    
    # No inicializar chat como variable global
    # Cada conversación debe tener su propia instancia de chat
    logger.info("Google AI model configurado exitosamente")
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

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE  # 20MB max-limit

# Asegurarse de que el directorio instance existe
instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# Configuración básica
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())

# Configuración de base de datos
# En Render, usar PostgreSQL si DATABASE_URL está definido
database_url = os.getenv('DATABASE_URL')
is_render = os.environ.get('RENDER', False) or os.environ.get('RENDER_SERVICE_ID', False)

if database_url and is_render:
    # Render proporciona URLs de PostgreSQL que comienzan con postgres://
    # SQLAlchemy 1.4+ requiere postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    logger.info("Usando PostgreSQL en Render")
else:
    # En desarrollo local, usar SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "db.sqlite")}'
    logger.info("Usando SQLite en desarrollo local")

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
        
        # Configurar la API key para el modelo de edición de imágenes
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Usar el modelo correcto para edición de imágenes
        model_name = "gemini-2.0-flash-exp-image-generation"
        
        # Crear el modelo generativo
        image_model = genai.GenerativeModel(model_name)
        
        # Preparar la imagen para la API
        img = PIL.Image.open(processed_image)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Preparar la solicitud para editar imagen
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
        
        # Realizar la llamada al modelo para edición de imágenes
        response = image_model.generate_content(
            content,
            generation_config=generation_config
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
        
        # Configurar la API key para el modelo de generación de imágenes
        genai.configure(api_key=GOOGLE_API_KEY)
        

        # Usar el modelo correcto para generación de imágenes
        model_name = "gemini-1.5-flash-latest"
        
        # Crear el modelo generativo
        image_model = genai.GenerativeModel(model_name)
        
        # Configuración de generación específica para imágenes
        generation_config = {
            "temperature": 1.0,
            "top_p": 1.0,
            "top_k": 32,
            "max_output_tokens": 8192,
        }
        
        # Configuración de seguridad
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # Asegurarse de que el directorio de imágenes generadas exista
        generated_images_dir = os.path.join(UPLOAD_FOLDER)
        if not os.path.exists(generated_images_dir):
            os.makedirs(generated_images_dir)
            logger.info(f"Directorio creado: {generated_images_dir}")
        
        # Realizar la llamada al modelo para generación de imágenes
        response = image_model.generate_content(
            prompt_text,
            generation_config=generation_config,
            safety_settings=safety_settings,
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
            model_name="gemini-1.5-pro",
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

@socketio.on('message')
def handle_message(data):
    try:
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversationId')
        files = data.get('files', [])
        model_type = data.get('model', 'gemini')  # Default to gemini if not specified
        is_image_generation = data.get('isImageGeneration', False)  # Check if this is an image generation request
        is_image_edit = data.get('isImageEdit', False)  # Check if this is an image editing request
        
        # Si no hay ID de conversación, crear uno nuevo
        if not conversation_id:
            conversation = Conversation()
            # Asignar user_id solo si el usuario está autenticado
            if current_user.is_authenticated:
                conversation.user_id = current_user.id
            conversation.model_name = model_type
            conversation.title = "Nueva Conversación"
            db.session.add(conversation)
            db.session.commit()
            conversation_id = conversation.id
            logger.debug(f"Creada nueva conversación con ID: {conversation_id}")
        
        logger.debug(f"Recibido mensaje - ID: {conversation_id}, Texto: {user_message}, Archivos: {len(files)}, Modelo: {model_type}, Es edición de imagen: {is_image_edit}")
        
        # Procesar imágenes si hay
        processed_images = []
        if files:
            logger.debug(f"Procesando {len(files)} archivos")
            for file_data in files:
                if not file_data:
                    logger.error("Datos de archivo vacíos recibidos")
                    continue
                
                try:
                    # Decodificar la imagen base64
                    if isinstance(file_data, str):
                        if ',' in file_data:
                            header, encoded = file_data.split(',', 1)
                            logger.debug(f"Tipo de imagen detectado: {header}")
                        else:
                            encoded = file_data
                        
                        try:
                            image_data = base64.b64decode(encoded.strip())
                            logger.debug(f"Imagen decodificada correctamente")
                            processed_images.append({
                                'mime_type': 'image/jpeg',
                                'data': encoded.strip()
                            })
                        except Exception as decode_error:
                            logger.error(f"Error decodificando base64: {decode_error}")
                            continue
                except Exception as e:
                    logger.error(f"Error general procesando imagen: {str(e)}")
                    continue

            if len(processed_images) == 0 and files:
                error_msg = "No se pudo procesar ninguna imagen. Formatos permitidos: png, jpg, gif, webp, jpeg. Tamaño máximo: 20MB"
                logger.error(error_msg)
                emit('message', {'role': 'assistant', 'content': error_msg})
                return

        try:
            # Guardar mensaje del usuario primero
            if user_message:  # Solo guardar si hay mensaje de texto
                save_message_to_db(conversation_id, user_message, 'user')
            
            # Obtener historial de mensajes de la conversación
            previous_messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()
            conversation_history_text = []
            for msg in previous_messages:
                conversation_history_text.append({"role": msg.role, "content": msg.content})

            # Generate title if this is the first message
            conversation = Conversation.query.get(conversation_id)
            if conversation and conversation.title == "Nueva Conversación" and user_message:
                title_prompt = f"Generate a short, descriptive title (max 3-4 words) for a conversation that starts with: {user_message}"
                if model_type == 'gemini':
                    title_response = model.generate_content(title_prompt)
                    conversation.title = title_response.text[:200]  # Limit title length
                elif model_type == 'groq' and groq_client:
                    title_completion = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": title_prompt}],
                        max_tokens=10
                    )
                    conversation.title = title_completion.choices[0].message.content[:200]
                db.session.commit()
                # Emit title update to frontend
                emit('conversation_update', {
                    'id': conversation_id,
                    'title': conversation.title
                })

            # Verificar si es una solicitud de edición de imagen
            if is_image_edit and processed_images:
                try:
                    logger.info("Procesando solicitud de edición de imagen")
                    
                    # Tomar la primera imagen procesada para editar
                    input_image = processed_images[0]['data']
                    
                    # Llamar a la función de edición de imagen
                    edit_result = generate_image_edit_from_upload(input_image, user_message)
                    
                    # Emitir la respuesta con el tipo correcto
                    if '[GENERATED_IMAGE:' in edit_result:
                        # Extraer la URL de la imagen
                        img_match = edit_result.strip().split('[GENERATED_IMAGE:')[1].split(']')[0]
                        emit('message', {
                            'role': 'assistant',
                            'type': 'image_url',
                            'content': img_match,
                            'done': True
                        })
                    else:
                        emit('message', {
                            'role': 'assistant',
                            'type': 'text',
                            'content': edit_result,
                            'done': True
                        })
                    
                    # Guardar la respuesta del asistente
                    save_message_to_db(conversation_id, edit_result, 'assistant')
                    
                except Exception as edit_error:
                    logger.error(f"Error al editar imagen: {str(edit_error)}")
                    error_msg = f"Error al editar la imagen: {str(edit_error)}"
                    emit('message', {
                        'role': 'assistant',
                        'content': error_msg,
                        'done': True
                    })
            
            # Verificar si es una solicitud de generación de imagen a partir de texto
            elif is_image_generation:
                try:
                    logger.info("Procesando solicitud de generación de imagen a partir de texto")
                    
                    # Llamar a la función de generación de imagen
                    generation_result = generate_image_from_text(user_message)
                    
                    # Emitir la respuesta con el tipo correcto
                    if '[GENERATED_IMAGE:' in generation_result:
                        # Extraer la URL de la imagen
                        img_match = generation_result.strip().split('[GENERATED_IMAGE:')[1].split(']')[0]
                        emit('message', {
                            'role': 'assistant',
                            'type': 'image_url',
                            'content': img_match,
                            'done': True
                        })
                    else:
                        emit('message', {
                            'role': 'assistant',
                            'type': 'text',
                            'content': generation_result,
                            'done': True
                        })
                    
                    # Guardar la respuesta del asistente
                    save_message_to_db(conversation_id, generation_result, 'assistant')
                    
                except Exception as gen_error:
                    logger.error(f"Error al generar imagen a partir de texto: {str(gen_error)}")
                    error_msg = f"Error al generar la imagen: {str(gen_error)}"
                    emit('message', {
                        'role': 'assistant',
                        'content': error_msg,
                        'done': True
                    })
                    
            # Verificar si el modo de búsqueda web está activado
            elif data.get('webSearch', False) and user_message:
                try:
                    logger.info(f"Realizando búsqueda web para: {user_message}")
                    
                    # Realizar la búsqueda web
                    search_results = search_web(user_message, search_provider="serper", num_results=5)
                    
                    # Formatear los resultados para el modelo
                    search_context = format_search_results_for_llm(search_results)
                    logger.info(f"Resultados de búsqueda obtenidos: {len(search_results.get('results', []))} resultados")
                    
                    # Crear un prompt enriquecido con los resultados de búsqueda
                    enriched_prompt = f"""Basándote en los siguientes resultados de búsqueda web:

{search_context}

Responde a la siguiente consulta del usuario: {user_message}

Utiliza la información de los resultados de búsqueda para proporcionar una respuesta precisa y actualizada. Cita las fuentes cuando sea apropiado."""
                    
                    # Determinar qué modelo usar para procesar la respuesta
                    if model_type == 'groq' and groq_client:
                        # Usar Groq para procesar la respuesta con streaming
                        common_params = {
                            "temperature": 0.7,
                            "max_tokens": 2048,
                            "top_p": 1,
                            "stream": True,
                            "stop": None
                        }
                        
                        # Crear la solicitud a la API de Groq
                        messages = [{"role": "user", "content": enriched_prompt}]
                        completion = groq_client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=messages,
                            **common_params
                        )
                        
                        # Procesar la respuesta en streaming
                        accumulated_response = ""
                        buffer = ""
                        buffer_size_threshold = 50
                        
                        for chunk in completion:
                            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                chunk_content = chunk.choices[0].delta.content
                                accumulated_response += chunk_content
                                buffer += chunk_content
                                
                                if len(buffer) >= buffer_size_threshold:
                                    emit('message_progress', {
                                        'content': buffer,
                                        'conversation_id': conversation_id
                                    })
                                    buffer = ""
                        
                        # Emitir respuesta final completa
                        emit('message', {
                            'role': 'assistant',
                            'type': 'text',
                            'content': accumulated_response,
                            'done': True
                        })
                        
                        # Guardar la respuesta del asistente
                        save_message_to_db(conversation_id, accumulated_response, 'assistant')
                    else:
                        # Usar Gemini para procesar la respuesta con streaming
                        # Crear una instancia de chat específica para esta conversación
                        chat = model.start_chat()
                        
                        # Implementar streaming para Gemini
                        response = chat.send_message(enriched_prompt, stream=True)
                        
                        # Procesar la respuesta en streaming
                        accumulated_response = ""
                        buffer = ""
                        buffer_size_threshold = 50
                        
                        try:
                            for chunk in response:
                                if hasattr(chunk, 'text') and chunk.text:
                                    chunk_content = chunk.text
                                    accumulated_response += chunk_content
                                    buffer += chunk_content
                                    
                                    if len(buffer) >= buffer_size_threshold:
                                        emit('message_progress', {
                                            'content': buffer,
                                            'conversation_id': conversation_id
                                        })
                                        buffer = ""
                            
                            # Emitir cualquier contenido restante en el buffer
                            if buffer:
                                emit('message_progress', {
                                    'content': buffer,
                                    'conversation_id': conversation_id
                                })
                            
                            # Emitir respuesta final completa
                            emit('message', {
                                'role': 'assistant',
                                'type': 'text',
                                'content': accumulated_response,
                                'done': True
                            })
                            
                            # Guardar la respuesta del asistente
                            save_message_to_db(conversation_id, accumulated_response, 'assistant')
                            
                        except Exception as stream_error:
                            logger.error(f"Error en streaming de Gemini con búsqueda web: {str(stream_error)}")
                            error_msg = f"Error al procesar la respuesta con búsqueda web: {str(stream_error)}"
                            emit('message', {
                                'role': 'assistant',
                                'content': error_msg,
                                'done': True
                            })
                except Exception as search_error:
                    logger.error(f"Error en búsqueda web: {str(search_error)}")
                    error_msg = f"Error al realizar la búsqueda web: {str(search_error)}"
                    emit('message', {
                        'role': 'assistant',
                        'content': error_msg,
                        'done': True
                    })
            
            # Generate response based on model type
            elif model_type == 'gemini-flash':
                # Generar imagen con Gemini 2.0 Flash
                try:
                    logger.info("Generando imagen con Gemini 2.0 Flash")
                    
                    # Configurar la API key para el modelo de generación de imágenes
                    genai.configure(api_key=GOOGLE_API_KEY)
                    
                    # Usar el modelo correcto para generación de imágenes
                    model_name = "gemini-2.0-flash-exp-image-generation"
                    
                    # Crear el modelo generativo
                    image_model = genai.GenerativeModel(model_name)
                    
                    # Preparar la solicitud para generar imagen
                    prompt = user_message if user_message else "Genera una imagen creativa"
                    
                    # Configurar para generar imagen
                    generation_config = {
                        "temperature": 0.7,
                        "top_p": 1.0,
                        "top_k": 32,
                        "max_output_tokens": 2048,
                    }
                    
                    # Configurar el tipo de respuesta que queremos (imagen)
                    response_types = ["image", "text"]
                    
                    # Procesar la respuesta
                    text_response = ""
                    image_url = ""
                    
                    # Realizar la llamada al modelo para generación de imágenes
                    response = image_model.generate_content(
                        prompt,
                        generation_config=generation_config
                    )
                    
                    # Procesar la respuesta completa
                    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                        # Procesar texto si hay
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'text') and part.text:
                                text_response += part.text
                            
                            # Procesar imagen
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
                                    logger.info(f"Imagen generada guardada en: {filepath}")
                                except Exception as img_save_error:
                                    logger.error(f"Error al guardar la imagen generada: {str(img_save_error)}")
                                    # Continuar con el proceso aunque falle el guardado de la imagen
                    
                    # Formatear la respuesta final con la imagen
                    final_response = text_response
                    if image_url:
                        final_response += f"\n[GENERATED_IMAGE:{image_url}]"
                    
                    # Emitir la respuesta con el tipo correcto
                    if '[GENERATED_IMAGE:' in final_response:
                        # Extraer la URL de la imagen
                        img_match = final_response.strip().split('[GENERATED_IMAGE:')[1].split(']')[0]
                        emit('message', {
                            'role': 'assistant',
                            'type': 'image_url',
                            'content': img_match,
                            'done': True
                        })
                    else:
                        emit('message', {
                            'role': 'assistant',
                            'type': 'text',
                            'content': final_response,
                            'done': True
                        })
                    
                    # Guardar la respuesta del asistente
                    save_message_to_db(conversation_id, final_response, 'assistant')
                    
                except Exception as img_error:
                    logger.error(f"Error al generar imagen: {str(img_error)}")
                    error_msg = f"Error al generar la imagen: {str(img_error)}"
                    emit('message', {
                        'role': 'assistant',
                        'content': error_msg,
                        'done': True
                    })
                    
            elif model_type == 'groq':
                if not groq_client:
                    raise Exception("Groq API no está configurada. Por favor, configure GROQ_API_KEY en el archivo .env")

                # Configuración común para todas las llamadas
                common_params = {
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "top_p": 1,
                    "stream": True,
                    "stop": None
                }

                # Preparar el contenido del mensaje para Groq
                # Groq no soporta el formato de contenido mixto de la misma manera que Gemini
                # Simplificamos para usar solo texto para Groq
                if user_message:
                    user_content = user_message
                    if processed_images:
                        user_content += "\n[Nota: El usuario también ha adjuntado imágenes que no se pueden procesar directamente con este modelo]"
                else:
                    user_content = "Describe lo que ves en esta imagen" if processed_images else ""
                
                # Crear la solicitud a la API de Groq con el historial de la conversación
                messages = conversation_history_text + [{"role": "user", "content": user_content}]
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    **common_params
                )

                # Procesar la respuesta en streaming
                accumulated_response = ""
                buffer = ""
                buffer_size_threshold = 50  # Enviar actualizaciones cada 50 caracteres
                
                for chunk in completion:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        chunk_content = chunk.choices[0].delta.content
                        accumulated_response += chunk_content
                        buffer += chunk_content
                        
                        # Solo emitir actualizaciones de progreso cuando el buffer alcance cierto tamaño
                        if len(buffer) >= buffer_size_threshold:
                            emit('message_progress', {
                                'content': buffer,
                                'conversation_id': conversation_id
                            })
                            buffer = ""
                
                # Emitir respuesta final completa (no fragmentada)
                emit('message', {
                    'role': 'assistant',
                    'type': 'text',
                    'content': accumulated_response,
                    'done': True
                })
                
                # Guardar la respuesta del asistente en la base de datos
                save_message_to_db(conversation_id, accumulated_response, 'assistant')
            else:  # default to gemini
                # Preparar el mensaje para Gemini
                parts = []
                if user_message:
                    parts.append({"text": user_message})
                
                if processed_images:
                    for img in processed_images:
                        parts.append({
                            "inline_data": {
                                "mime_type": img['mime_type'],
                                "data": img['data']
                            }
                        })
                    if not user_message:
                        parts.append({"text": "Describe lo que ves en esta imagen"})
                
                # Crear una instancia de chat específica para esta conversación
                # Preparar el historial de la conversación para el modelo
                chat_history = []
                for msg in previous_messages:
                    chat_history.append({"role": msg.role, "parts": [{"text": msg.content}]})
                
                # Iniciar chat con historial específico de esta conversación
                chat = model.start_chat(history=chat_history)
                
                # Verificar si hay búsqueda web activada pero no se procesó en la sección anterior
                # (esto puede ocurrir si hay imágenes adjuntas junto con la búsqueda web)
                if data.get('webSearch', False) and user_message:
                    try:
                        # Realizar la búsqueda web
                        search_results = search_web(user_message, search_provider="serper", num_results=5)
                        
                        # Formatear los resultados para el modelo
                        search_context = format_search_results_for_llm(search_results)
                        logger.info(f"Resultados de búsqueda obtenidos: {len(search_results.get('results', []))} resultados")
                        
                        # Añadir contexto de búsqueda al mensaje del usuario
                        enriched_message = f"""Basándote en los siguientes resultados de búsqueda web:

{search_context}

Responde a la siguiente consulta del usuario: {user_message}

Utiliza la información de los resultados de búsqueda para proporcionar una respuesta precisa y actualizada. Cita las fuentes cuando sea apropiado."""
                        
                        # Reemplazar las partes de texto con el mensaje enriquecido
                        new_parts = []
                        for part in parts:
                            if part.get('text'):
                                new_parts.append({"text": enriched_message})
                            else:
                                new_parts.append(part)
                        parts = new_parts
                    except Exception as search_error:
                        logger.error(f"Error al enriquecer mensaje con búsqueda web: {str(search_error)}")
                        # Continuar con el mensaje original si falla la búsqueda
                
                # Implementar streaming para Gemini
                response = chat.send_message(parts, stream=True)
                
                # Procesar la respuesta en streaming
                accumulated_response = ""
                buffer = ""
                buffer_size_threshold = 50  # Enviar actualizaciones cada 50 caracteres
                
                try:
                    for chunk in response:
                        if hasattr(chunk, 'text') and chunk.text:
                            chunk_content = chunk.text
                            accumulated_response += chunk_content
                            buffer += chunk_content
                            
                            # Solo emitir actualizaciones de progreso cuando el buffer alcance cierto tamaño
                            if len(buffer) >= buffer_size_threshold:
                                emit('message_progress', {
                                    'content': buffer,
                                    'conversation_id': conversation_id
                                })
                                buffer = ""
                    
                    # Emitir cualquier contenido restante en el buffer
                    if buffer:
                        emit('message_progress', {
                            'content': buffer,
                            'conversation_id': conversation_id
                        })
                    
                    # Emitir respuesta final completa
                    emit('message', {
                        'role': 'assistant',
                        'type': 'text',
                        'content': accumulated_response,
                        'done': True
                    })
                    
                    # Guardar la respuesta del asistente
                    save_message_to_db(conversation_id, accumulated_response, 'assistant')
                    
                except Exception as stream_error:
                    logger.error(f"Error en streaming de Gemini: {str(stream_error)}")
                    error_msg = f"Error al procesar la respuesta: {str(stream_error)}"
                    emit('message', {
                        'role': 'assistant',
                        'content': error_msg,
                        'done': True
                    })
                    
        except Exception as api_error:
            logger.error(f"Error al generar respuesta: {str(api_error)}")
            if "429" in str(api_error):
                error_msg = "Lo siento, hemos alcanzado el límite de la API. Por favor, intenta de nuevo más tarde."
            else:
                error_msg = f"Error al procesar el mensaje: {str(api_error)}"
            
            emit('message', {
                'role': 'assistant',
                'content': error_msg,
                'done': True
            })
            
    except Exception as e:
        error_msg = f"Error al procesar el mensaje: {str(e)}"
        logger.error(error_msg)
        emit('message', {
            'role': 'assistant',
            'content': error_msg
        })

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
        search_provider = data.get('provider', 'serper')  # Por defecto usar Serper

        if not query:
            return jsonify({
                'error': 'No se proporcionó consulta de búsqueda',
                'status': 'error'
            }), 400

        # Realizar búsqueda web con la API real
        search_results = search_web(query, search_provider=search_provider)
        
        # Si hay un error en la búsqueda, intentar con el método alternativo
        if 'error' in search_results and not search_results['results']:
            logger.warning(f"Error en búsqueda con {search_provider}: {search_results['error']}")
            # Intentar con el método alternativo
            alt_provider = 'google' if search_provider == 'serper' else 'serper'
            search_results = search_web(query, search_provider=alt_provider)
        
        # Si aún hay error o no hay resultados, usar el método de respuesta simulada
        if 'error' in search_results and not search_results['results']:
            logger.warning("Fallback a respuesta simulada de búsqueda")
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
        model = genai.GenerativeModel('gemini-pro')
        
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
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    # En entorno local usamos socketio.run, en producción gunicorn maneja esto
    if os.environ.get('RENDER') or os.environ.get('PRODUCTION'):
        # En producción, gunicorn se encarga de ejecutar la app
        app.logger.info(f"Ejecutando en modo producción en puerto {port}")
    else:
        # En desarrollo local
        app.logger.info(f"Ejecutando en modo desarrollo en puerto {port}")
        socketio.run(app, debug=debug, host='0.0.0.0', port=port)
