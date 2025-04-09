import google.generativeai as genai
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
from dotenv import load_dotenv
import os

# Configurar la API key
load_dotenv()
API_KEY = os.getenv('GOOGLE_API_KEY')
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY no está configurada en el archivo .env")
genai.configure(api_key=API_KEY)

try:
    logger.info("Intentando crear el modelo...")
    # Crear el modelo
    model = genai.GenerativeModel('gemini-pro')
    
    # Hacer una prueba
    logger.info("Enviando mensaje de prueba...")
    response = model.generate_content("Di hola y confirma que estás funcionando correctamente.")
    
    print("\nRespuesta de la API:")
    print(response.text)
    print("\nLa API está funcionando correctamente!")
    
except Exception as e:
    logger.error(f"Error al probar la API: {str(e)}", exc_info=True)
    print(f"\nError al probar la API: {str(e)}")
