# AI Chatbot con Google Gemini y Groq

Una aplicación web moderna y minimalista que implementa un chatbot utilizando los modelos de IA de Google Gemini y Groq. La aplicación cuenta con un diseño limpio inspirado en Apple con una interfaz responsive.

## Características

- Interfaz de chat en tiempo real con WebSockets
- Potenciado por Google Gemini AI y Groq
- Procesamiento de imágenes y generación de contenido visual
- Diseño moderno y responsive
- Interfaz de usuario limpia e intuitiva
- Entrada de texto autoexpandible
- Animaciones y transiciones suaves
- Autenticación de usuarios (incluido inicio de sesión con Google)

## Requisitos previos

- Python 3.12 o superior
- Clave API de Google Gemini
- Clave API de Groq (opcional)
- Navegador web moderno

## Instalación local

1. Clona el repositorio
2. Crea un entorno virtual:
   ```
   python -m venv venv
   ```
3. Activa el entorno virtual:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Instala las dependencias requeridas:
   ```
   pip install -r requirements.txt
   ```
5. Crea un archivo `.env` y añade tus claves API:
   ```
   GOOGLE_API_KEY=tu_clave_api_gemini_aquí
   GROQ_API_KEY=tu_clave_api_groq_aquí
   SECRET_KEY=clave_secreta_para_flask
   GOOGLE_CLIENT_ID=tu_id_cliente_google_oauth
   GOOGLE_CLIENT_SECRET=tu_secreto_cliente_google_oauth
   ```

## Ejecución local

1. Inicia el servidor Flask:
   ```
   python app.py
   ```
2. Abre tu navegador y navega a:
   ```
   http://localhost:5000
   ```

## Despliegue en Render.com

### Configuración para Render.com

La aplicación está lista para ser desplegada en Render.com. Los archivos de configuración necesarios ya están incluidos:

- **Procfile**: Configura el servidor web Gunicorn con soporte para WebSockets.
- **requirements.txt**: Lista todas las dependencias necesarias.
- **runtime.txt**: Especifica la versión de Python a utilizar.

### Pasos para desplegar en Render.com

1. Crea una cuenta en [Render.com](https://render.com) si aún no tienes una.
2. **PRIMERO**: Crea un servicio de base de datos PostgreSQL:
   - Ve a Dashboard > New > PostgreSQL
   - Configura un nombre para tu base de datos
   - Selecciona el plan gratuito
   - Haz clic en "Create Database"
   - Espera a que se aprovisione la base de datos (puede tardar unos minutos)
   - Guarda la "Internal Database URL" que aparece en el panel
3. Haz clic en "New" y selecciona "Web Service".
4. Conecta tu repositorio de GitHub o sube el código directamente.
5. Configura el servicio con los siguientes ajustes:
   - **Name**: Nombre de tu aplicación
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -c gunicorn_config.py wsgi:app`
   - **Plan**: Selecciona el plan gratuito (Free) que incluye 512MB de RAM
6. En la sección "Environment Variables", añade las siguientes variables:
   - `GOOGLE_API_KEY`: Tu clave de API de Google Gemini
   - `GROQ_API_KEY`: Tu clave de API de Groq
   - `SECRET_KEY`: Una clave secreta para Flask
   - `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`: Para autenticación con Google
   - `RENDER=true`: Para indicar que está en entorno de producción
   - `DATABASE_URL`: **OBLIGATORIO** - Pega aquí la URL interna de PostgreSQL del paso 2

## Estructura del proyecto

```
.
├── app.py              # Aplicación principal Flask
├── auth.py             # Gestión de autenticación
├── models.py           # Modelos de base de datos
├── requirements.txt    # Dependencias Python
├── Procfile            # Configuración para Render.com
├── runtime.txt         # Versión de Python para Render.com
├── .env                # Variables de entorno (no incluir en repositorio)
├── instance/           # Base de datos SQLite y archivos de instancia
├── uploads/            # Directorio para archivos subidos e imágenes generadas
├── templates/          # Plantillas HTML
└── static/
    ├── css/            # Hojas de estilo
    ├── js/             # JavaScript del frontend
    └── src/            # Código fuente para componentes frontend
```

## Notas de seguridad

- Nunca incluyas tu archivo `.env` o expongas tus claves API en el repositorio
- La aplicación utiliza protección CORS
- Todas las entradas de usuario son sanitizadas antes de procesarse
- En Render.com, utiliza variables de entorno para todas las claves y secretos

## Notas importantes para Render.com

- La aplicación está configurada para detectar automáticamente si está ejecutándose en Render.com
- En producción, Render gestionará el servidor Gunicorn según la configuración del Procfile
- El directorio `uploads/` debe tener permisos de escritura para almacenar imágenes generadas

### Configuración de PostgreSQL (OBLIGATORIO para producción)

SQLite no es adecuado para entornos de producción con múltiples workers. Para un funcionamiento correcto en Render:

1. Crea un servicio de base de datos PostgreSQL en Render:
   - Ve a Dashboard > New > PostgreSQL
   - Configura un nombre y selecciona el plan gratuito
   - Espera a que se aprovisione la base de datos

2. Obtén la URL interna de conexión desde el panel de la base de datos

3. Añade esta URL como variable de entorno `DATABASE_URL` en tu servicio web

### Optimizaciones de memoria para Render Free Tier (512MB)

- La aplicación está configurada para limitar el uso de memoria a 480MB para evitar que Render mate los procesos
- Se utilizan mecanismos de recolección de basura periódica para mantener el uso de memoria bajo control
- El parámetro `max_requests` está configurado para reiniciar los workers después de procesar 200 solicitudes

## Licencia

MIT License
