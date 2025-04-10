import logging
import time
from models import db, Conversation, Message

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes
SUMMARY_THRESHOLD = 10  # Número de mensajes después de los cuales se genera un resumen
SUMMARY_PREFIX = "[RESUMEN] "  # Prefijo para identificar mensajes de resumen

def should_generate_summary(conversation_id):
    """
    Determina si se debe generar un resumen para una conversación.
    
    Args:
        conversation_id: ID de la conversación
        
    Returns:
        bool: True si se debe generar un resumen, False en caso contrario
    """
    try:
        # Contar mensajes desde el último resumen
        last_summary = Message.query.filter_by(
            conversation_id=conversation_id,
            content=db.text(f"content LIKE '{SUMMARY_PREFIX}%'")
        ).order_by(Message.created_at.desc()).first()
        
        if last_summary:
            # Contar mensajes después del último resumen
            count = Message.query.filter_by(conversation_id=conversation_id)\
                .filter(Message.created_at > last_summary.created_at)\
                .count()
        else:
            # Si no hay resumen previo, contar todos los mensajes
            count = Message.query.filter_by(conversation_id=conversation_id).count()
        
        return count >= SUMMARY_THRESHOLD
    except Exception as e:
        logger.error(f"Error al verificar si se debe generar resumen: {e}")
        return False

def generate_conversation_summary(conversation_id, model):
    """
    Genera un resumen de la conversación utilizando el modelo de IA.
    
    Args:
        conversation_id: ID de la conversación
        model: Instancia del modelo de IA a utilizar
        
    Returns:
        str: Resumen generado o None si hay un error
    """
    try:
        # Obtener todos los mensajes de la conversación
        messages = Message.query.filter_by(conversation_id=conversation_id)\
            .order_by(Message.created_at).all()
        
        if not messages or len(messages) < SUMMARY_THRESHOLD:
            return None
        
        # Preparar el contexto para el modelo
        conversation_text = ""
        for msg in messages:
            # Excluir resúmenes anteriores
            if not msg.content.startswith(SUMMARY_PREFIX):
                conversation_text += f"{msg.role.capitalize()}: {msg.content}\n"
        
        # Prompt para generar el resumen
        prompt = f"""A continuación hay una conversación entre un usuario y un asistente de IA.
        Por favor, genera un resumen conciso (máximo 200 palabras) que capture los puntos clave 
        y el contexto esencial de esta conversación. El resumen debe ser informativo y útil 
        para continuar la conversación.
        
        Conversación:
        {conversation_text}
        
        Resumen:"""
        
        # Generar resumen con el modelo
        response = model.generate_content(prompt)
        summary = response.text.strip()
        
        # Añadir prefijo al resumen
        summary_with_prefix = f"{SUMMARY_PREFIX}{summary}"
        
        return summary_with_prefix
    except Exception as e:
        logger.error(f"Error al generar resumen de conversación: {e}")
        return None

def save_summary_to_db(conversation_id, summary):
    """
    Guarda el resumen generado en la base de datos como un mensaje especial.
    
    Args:
        conversation_id: ID de la conversación
        summary: Texto del resumen generado
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        if not summary:
            return False
        
        # Crear mensaje de resumen
        summary_message = Message(
            conversation_id=conversation_id,
            content=summary,
            role='system'  # Usar 'system' para diferenciar de mensajes de usuario y asistente
        )
        
        # Guardar en la base de datos
        db.session.add(summary_message)
        db.session.commit()
        
        logger.info(f"Resumen guardado para conversación {conversation_id}")
        return True
    except Exception as e:
        logger.error(f"Error al guardar resumen en la base de datos: {e}")
        db.session.rollback()
        return False

def process_conversation_summary(conversation_id, model):
    """
    Procesa una conversación para generar y guardar un resumen si es necesario.
    
    Args:
        conversation_id: ID de la conversación
        model: Instancia del modelo de IA a utilizar
        
    Returns:
        bool: True si se procesó correctamente, False en caso contrario
    """
    try:
        # Verificar si se debe generar un resumen
        if should_generate_summary(conversation_id):
            # Generar resumen
            summary = generate_conversation_summary(conversation_id, model)
            
            # Guardar resumen en la base de datos
            if summary:
                return save_summary_to_db(conversation_id, summary)
        
        return False  # No se necesitaba generar resumen
    except Exception as e:
        logger.error(f"Error al procesar resumen de conversación: {e}")
        return False