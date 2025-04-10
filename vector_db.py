import chromadb
import os
import logging
from sentence_transformers import SentenceTransformer
import numpy as np

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorDatabase:
    def __init__(self, persist_directory="./chroma_db"):
        """
        Inicializa la base de datos vectorial.
        
        Args:
            persist_directory: Directorio donde se almacenarán los datos de ChromaDB
        """
        self.persist_directory = persist_directory
        
        # Crear directorio si no existe
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory)
            
        # Inicializar cliente de ChromaDB
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Crear colección para mensajes si no existe
        try:
            self.collection = self.client.get_collection("messages")
            logger.info("Colección de mensajes cargada correctamente")
        except Exception:
            self.collection = self.client.create_collection(
                name="messages",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Colección de mensajes creada correctamente")
        
        # Inicializar modelo de embeddings
        try:
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("Modelo de embeddings cargado correctamente")
        except Exception as e:
            logger.error(f"Error al cargar el modelo de embeddings: {e}")
            raise
    
    def add_message(self, message_id, conversation_id, content, role, created_at):
        """
        Añade un mensaje a la base de datos vectorial.
        
        Args:
            message_id: ID único del mensaje
            conversation_id: ID de la conversación a la que pertenece
            content: Contenido del mensaje
            role: Rol del mensaje ('user' o 'assistant')
            created_at: Timestamp de creación
        """
        try:
            # Generar embedding del contenido del mensaje
            embedding = self.model.encode(content)
            
            # Añadir a la colección
            self.collection.add(
                ids=[str(message_id)],
                embeddings=[embedding.tolist()],
                metadatas=[{
                    "conversation_id": str(conversation_id),
                    "role": role,
                    "created_at": str(created_at)
                }],
                documents=[content]
            )
            logger.info(f"Mensaje {message_id} añadido a la base de datos vectorial")
            return True
        except Exception as e:
            logger.error(f"Error al añadir mensaje a la base de datos vectorial: {e}")
            return False
    
    def get_relevant_messages(self, query, conversation_id=None, limit=5):
        """
        Recupera los mensajes más relevantes para una consulta dada.
        
        Args:
            query: Texto de consulta
            conversation_id: ID de conversación para filtrar (opcional)
            limit: Número máximo de resultados
            
        Returns:
            Lista de mensajes relevantes
        """
        try:
            # Generar embedding de la consulta
            query_embedding = self.model.encode(query)
            
            # Preparar filtro por conversación si se proporciona
            where_filter = None
            if conversation_id:
                where_filter = {"conversation_id": str(conversation_id)}
            
            # Realizar búsqueda
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=limit,
                where=where_filter
            )
            
            # Formatear resultados
            messages = []
            if results and 'documents' in results and len(results['documents']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    messages.append({
                        "content": doc,
                        "role": results['metadatas'][0][i]['role'],
                        "conversation_id": results['metadatas'][0][i]['conversation_id'],
                        "created_at": results['metadatas'][0][i]['created_at'],
                        "id": results['ids'][0][i]
                    })
            
            return messages
        except Exception as e:
            logger.error(f"Error al recuperar mensajes relevantes: {e}")
            return []

# Instancia global de la base de datos vectorial
vector_db = None

def init_vector_db():
    """
    Inicializa la instancia global de la base de datos vectorial.
    """
    global vector_db
    try:
        vector_db = VectorDatabase()
        return True
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos vectorial: {e}")
        return False

def get_vector_db():
    """
    Obtiene la instancia global de la base de datos vectorial.
    """
    global vector_db
    if vector_db is None:
        init_vector_db()
    return vector_db