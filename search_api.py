import requests
import os
import json
import logging
from dotenv import load_dotenv

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Claves de API
SERPER_API_KEY = os.getenv('SERPER_API_KEY')
GOOGLE_SEARCH_API_KEY = os.getenv('GOOGLE_SEARCH_API_KEY')
GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID')

def search_with_serper(query, num_results=5):
    """
    Realiza una búsqueda web utilizando la API de Serper.
    
    Args:
        query: Consulta de búsqueda
        num_results: Número de resultados a devolver
        
    Returns:
        dict: Resultados de la búsqueda formateados
    """
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY no está configurada")
        return {"error": "API key no configurada", "results": []}
    
    try:
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query,
            "num": num_results
        })
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }
        
        response = requests.request("POST", url, headers=headers, data=payload)
        data = response.json()
        
        # Formatear resultados
        formatted_results = []
        
        # Procesar resultados orgánicos
        if 'organic' in data:
            for result in data['organic'][:num_results]:
                formatted_results.append({
                    "title": result.get('title', ''),
                    "link": result.get('link', ''),
                    "snippet": result.get('snippet', ''),
                    "source": "organic"
                })
        
        # Procesar resultados destacados si existen
        if 'answerBox' in data and len(formatted_results) < num_results:
            answer_box = data['answerBox']
            formatted_results.append({
                "title": answer_box.get('title', 'Resultado destacado'),
                "link": answer_box.get('link', ''),
                "snippet": answer_box.get('snippet', answer_box.get('answer', '')),
                "source": "answerBox"
            })
        
        return {
            "query": query,
            "results": formatted_results
        }
    except Exception as e:
        logger.error(f"Error en búsqueda con Serper: {e}")
        return {"error": str(e), "results": []}

def search_with_google_api(query, num_results=5):
    """
    Realiza una búsqueda web utilizando la API de Google Custom Search.
    
    Args:
        query: Consulta de búsqueda
        num_results: Número de resultados a devolver
        
    Returns:
        dict: Resultados de la búsqueda formateados
    """
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        logger.error("GOOGLE_SEARCH_API_KEY o GOOGLE_SEARCH_ENGINE_ID no están configurados")
        return {"error": "API key o Engine ID no configurados", "results": []}
    
    try:
        url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_SEARCH_API_KEY}&cx={GOOGLE_SEARCH_ENGINE_ID}&q={query}&num={num_results}"
        
        response = requests.get(url)
        data = response.json()
        
        # Formatear resultados
        formatted_results = []
        
        if 'items' in data:
            for item in data['items']:
                formatted_results.append({
                    "title": item.get('title', ''),
                    "link": item.get('link', ''),
                    "snippet": item.get('snippet', ''),
                    "source": "google"
                })
        
        return {
            "query": query,
            "results": formatted_results
        }
    except Exception as e:
        logger.error(f"Error en búsqueda con Google API: {e}")
        return {"error": str(e), "results": []}

def search_web(query, search_provider="serper", num_results=5):
    """
    Función principal para realizar búsquedas web utilizando el proveedor especificado.
    
    Args:
        query: Consulta de búsqueda
        search_provider: Proveedor de búsqueda ('serper' o 'google')
        num_results: Número de resultados a devolver
        
    Returns:
        dict: Resultados de la búsqueda formateados
    """
    if not query:
        return {"error": "Consulta vacía", "results": []}
    
    # Seleccionar proveedor de búsqueda
    if search_provider.lower() == "google":
        return search_with_google_api(query, num_results)
    else:  # Por defecto usar Serper
        return search_with_serper(query, num_results)

def format_search_results_for_llm(search_results):
    """
    Formatea los resultados de búsqueda para ser utilizados como contexto por el modelo de IA.
    
    Args:
        search_results: Resultados de la búsqueda
        
    Returns:
        str: Texto formateado con los resultados de búsqueda
    """
    if not search_results or "results" not in search_results or not search_results["results"]:
        return "No se encontraron resultados relevantes."
    
    formatted_text = f"Resultados de búsqueda para: '{search_results.get('query', '')}'"
    
    for i, result in enumerate(search_results["results"], 1):
        formatted_text += f"\n\n[{i}] {result.get('title', 'Sin título')}"
        formatted_text += f"\nURL: {result.get('link', '')}"
        formatted_text += f"\nResumen: {result.get('snippet', 'No disponible')}"
    
    return formatted_text