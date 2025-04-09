import os
from dotenv import load_dotenv
from groq import Groq
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
print(f'GROQ_API_KEY encontrada: {GROQ_API_KEY is not None}')
print(f'Primeros 5 caracteres de GROQ_API_KEY: {GROQ_API_KEY[:5] if GROQ_API_KEY else "No disponible"}')

if GROQ_API_KEY:
    try:
        print('Intentando inicializar el cliente Groq...')
        groq_client = Groq(api_key=GROQ_API_KEY)
        print('Cliente Groq inicializado correctamente')
        
        # Intentar una llamada simple a la API
        print('Intentando hacer una llamada a la API de Groq...')
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Hola, ¿cómo estás?"}],
            max_tokens=10
        )
        print('Respuesta de Groq:', completion.choices[0].message.content)
        print('La API de Groq está funcionando correctamente')
    except Exception as e:
        print(f'Error al inicializar o usar el cliente Groq: {str(e)}')
        logger.error(f'Error detallado: {str(e)}', exc_info=True)
else:
    print('GROQ_API_KEY no está configurada en el archivo .env')