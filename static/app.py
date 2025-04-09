from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory, abort
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, login_required, current_user, login_user
from datetime import timedelta
from dotenv import load_dotenv
import google.generativeai as genai
import os
import time
import logging
from models import db, User, Conversation, Message
from auth import auth as auth_blueprint
import PIL.Image
import io

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configurar Google AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')
    vision_model = genai.GenerativeModel('gemini-1.5-pro-vision')
else:
    logger.warning("GOOGLE_API_KEY no está configurada")

# Configurar Groq AI
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    logger.warning("GROQ_API_KEY no está configurada")

def get_groq_response(message, images=None):
    try:
        if images:
            # Format message with images for Groq vision model
            content = []
            if message:
                content.append({
                    "type": "text",
                    "text": message
                })
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img['mime_type'],
                        "data": img['data']
                    }
                })
            if not message:
                content.append({
                    "type": "text",
                    "text": "Describe what you see in this image"
                })
            response = groq_client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[{"role": "user", "content": content}],
                max_tokens=2048,
                temperature=0.7
            )
        else:
            response = groq_client.chat.completions.create(
                model="llama-3.2-11b",
                messages=[{"role": "user", "content": message}],
                max_tokens=2048,
                temperature=0.7
            )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error en Groq API: {str(e)}")
        raise

# Configuración de carga de archivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB max-limit

# Asegurarse de que el directorio instance existe
instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# Configuración básica
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "db.sqlite")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de sesiones y cookies
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=31)
app.config['REMEMBER_COOKIE_SECURE'] = False  # Cambiar a True en producción
app.config['REMEMBER_COOKIE_HTTPONLY'] = True

# Inicializar extensiones
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
        logger.warning("Usuario no autenticado intentando conectar")
        return False
    logger.info(f"Usuario {current_user.username} conectado")

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        logger.info(f"Usuario {current_user.username} desconectado")

@app.route('/api/conversations')
@login_required
def get_conversations():
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()
    return jsonify({
        'conversations': [{
            'id': conv.id,
            'title': f'Conversación {conv.id}',
        } for conv in conversations]
    })

@socketio.on('message')
def handle_message(data):
    if not current_user.is_authenticated:
        return

    try:
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversationId')
        has_attachments = data.get('hasAttachments', False)
        files = request.files.getlist('files[]') if has_attachments else []
        
        # Procesar archivos adjuntos
        images = []
        if files:
            for file in files:
                if file.filename:
                    temp_filename = os.path.join(app.config['UPLOAD_FOLDER'], 
                                              str(time.time()) + '_' + file.filename)
                    file.save(temp_filename)
                    
                    if file.content_type.startswith('image/'):
                        try:
                            image = PIL.Image.open(temp_filename)
                            img_byte_arr = io.BytesIO()
                            image.save(img_byte_arr, format=image.format or 'PNG')
                            img_byte_arr = img_byte_arr.getvalue()
                            
                            images.append({
                                'mime_type': file.content_type,
                                'data': img_byte_arr
                            })
                        except Exception as e:
                            logger.error(f"Error procesando imagen {file.filename}: {str(e)}")
                        finally:
                            if os.path.exists(temp_filename):
                                os.remove(temp_filename)

        # Obtener o crear conversación
        if conversation_id:
            conversation = Conversation.query.get(conversation_id)
            if not conversation or conversation.user_id != current_user.id:
                conversation = None
        else:
            conversation = None
        
        if not conversation:
            conversation = Conversation(user_id=current_user.id)
            conversation.title = "Nueva Conversación"
            db.session.add(conversation)
            db.session.commit()
            
        # We'll generate the title along with the response in a single API call

        # Guardar mensaje del usuario
        user_msg = Message(
            conversation_id=conversation.id,
            content=user_message,
            role='user'
        )
        db.session.add(user_msg)
        db.session.commit()

        # Generar respuesta y título según el modelo seleccionado en un solo llamado
        try:
            # Preparar el prompt para solicitar respuesta y título en formato JSON
            json_prompt = """Assistant, you are a helpful AI assistant. The user has sent the following message:

{}

Please generate a response to the user's message and a title that summarizes the conversation so far.

Your output should be a JSON object with two keys: 'response' and 'title'.

So, your output should look like this:

{{ "response": "Your response to the user", "title": "Summary title" }}
""".format(user_message)
            
            if conversation.model_name == 'groq':
                # Modificar la función get_groq_response para manejar el nuevo formato
                json_response_text = get_groq_response(json_prompt, images if images else None)
                try:
                    # Intentar parsear la respuesta como JSON
                    json_data = json.loads(json_response_text)
                    assistant_response = json_data.get('response', 'No se pudo generar una respuesta')
                    
                    # Actualizar el título si es una nueva conversación
                    if conversation.title == "Nueva Conversación":
                        conversation.title = json_data.get('title', f"Chat {conversation.id}")[:200]
                        db.session.commit()
                        # Emitir actualización del título
                        emit('conversation_update', {
                            'id': conversation.id,
                            'title': conversation.title
                        })
                except json.JSONDecodeError:
                    # Si no es JSON válido, usar la respuesta completa
                    assistant_response = json_response_text
                    if conversation.title == "Nueva Conversación":
                        conversation.title = f"Chat {conversation.id}"
                        db.session.commit()
            else:  # default to gemini
                if images:
                    # Para imágenes, primero obtener descripción y luego generar título
                    prompt = [user_message] if user_message else ["Describe what you see in this image"]
                    prompt.extend(images)
                    response = vision_model.generate_content(prompt)
                    assistant_response = response.text
                    
                    # Si es nueva conversación, generar título basado en la respuesta
                    if conversation.title == "Nueva Conversación":
                        title_prompt = f"Generate a short, descriptive title (max 3-4 words) based on this conversation:\nUser: {user_message}\nAssistant: {assistant_response}"
                        title_response = model.generate_content(title_prompt)
                        conversation.title = title_response.text[:200]
                        db.session.commit()
                        emit('conversation_update', {
                            'id': conversation.id,
                            'title': conversation.title
                        })
                else:
                    # Para texto, usar el prompt JSON
                    response = model.generate_content(json_prompt)
                    response_text = response.text
                    
                    try:
                        # Intentar parsear la respuesta como JSON
                        json_data = json.loads(response_text)
                        assistant_response = json_data.get('response', 'No se pudo generar una respuesta')
                        
                        # Actualizar el título si es una nueva conversación
                        if conversation.title == "Nueva Conversación":
                            conversation.title = json_data.get('title', f"Chat {conversation.id}")[:200]
                            db.session.commit()
                            # Emitir actualización del título
                            emit('conversation_update', {
                                'id': conversation.id,
                                'title': conversation.title
                            })
                    except json.JSONDecodeError:
                        # Si no es JSON válido, usar la respuesta completa
                        assistant_response = response_text
                        if conversation.title == "Nueva Conversación":
                            conversation.title = f"Chat {conversation.id}"
                            db.session.commit()

            # Guardar respuesta del asistente
            assistant_msg = Message(
                conversation_id=conversation.id,
                content=assistant_response,
                role='assistant'
            )
            db.session.add(assistant_msg)
            db.session.commit()

            # Enviar respuesta
            emit('response', {
                'response': assistant_response,
                'conversationId': conversation.id
            })

        except Exception as e:
            logger.error(f"Error en la generación de respuesta: {str(e)}")
            emit('response', {
                'error': True,
                'response': "Lo siento, ha ocurrido un error al procesar tu mensaje. Por favor, intenta de nuevo."
            })

    except Exception as e:
        logger.error(f"Error general en handle_message: {str(e)}")
        emit('response', {
            'error': True,
            'response': "Lo siento, ha ocurrido un error al procesar tu mensaje. Por favor, intenta de nuevo."
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
    
    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()
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

@app.route('/')
def home():
    return send_from_directory('static', 'index.html')

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
            response = search_client.generate_content(
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

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            logger.info("Base de datos creada exitosamente")
        except Exception as e:
            logger.error(f"Error al crear la base de datos: {e}")
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)
