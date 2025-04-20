Generar imágenes

La API de Gemini admite la generación de imágenes con Gemini 2.0 Flash Experimental y con Imagen 3. Esta guía te ayuda a comenzar a usar ambos modelos.

Antes de comenzar
Antes de llamar a la API de Gemini, asegúrate de tener instalado el SDK que elijas y de que una clave de API de Gemini esté configurada y lista para usar.

Genera imágenes con Gemini
Gemini 2.0 Flash Experimental admite la capacidad de generar texto y líneas de imágenes. Esto te permite usar Gemini para editar imágenes de forma conversacional o generar resultados con texto entretejido (por ejemplo, generar una entrada de blog con texto e imágenes en una sola vuelta). Todas las imágenes generadas incluyen una marca de agua de SynthID, y las imágenes de Google AI Studio también incluyen una marca de agua visible.

Nota: Asegúrate de incluir responseModalities: ["TEXT", "IMAGE"] en la configuración de generación para la salida de texto e imagen con gemini-2.0-flash-exp-image-generation. No se permite solo la imagen.
En el siguiente ejemplo, se muestra cómo usar Gemini 2.0 para generar resultados de texto y de imagen:

Python
JavaScript
REST

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64

client = genai.Client()

contents = ('Hi, can you create a 3d rendered image of a pig '
            'with wings and a top hat flying over a happy '
            'futuristic scifi city with lots of greenery?')

response = client.models.generate_content(
    model="gemini-2.0-flash-exp-image-generation",
    contents=contents,
    config=types.GenerateContentConfig(
      response_modalities=['TEXT', 'IMAGE']
    )
)

for part in response.candidates[0].content.parts:
  if part.text is not None:
    print(part.text)
  elif part.inline_data is not None:
    image = Image.open(BytesIO((part.inline_data.data)))
    image.save('gemini-native-image.png')
    image.show()
Imagen generada por IA de un cerdo volador fantástico
Imagen generada por IA de un cerdo volador fantástico
Según la instrucción y el contexto, Gemini generará contenido en diferentes modos (texto a imagen, texto a imagen y texto, etcétera). Estos son algunos ejemplos:

Texto a imagen
Ejemplo de instrucción: “Genera una imagen de la Torre Eiffel con fuegos artificiales en el fondo”.
Texto a imágenes y texto (intercalado)
Ejemplo de instrucción: "Genera una receta ilustrada de una paella".
De imágenes y texto a imágenes y texto (intercalados)
Ejemplo de instrucción: (Con una imagen de una habitación amueblada) “¿Qué otros colores de sofás funcionarían en mi espacio? ¿Puedes actualizar la imagen?”
Edición de imágenes (texto e imagen a imagen)
Ejemplo de instrucción: “Edita esta imagen para que parezca un dibujo animado”.
Ejemplo de instrucción: [imagen de un gato] + [imagen de una almohada] + “Crea un bordado de mi gato en esta almohada”.
Edición de imágenes de varios turnos (chat)
Ejemplos de instrucciones: [Sube una imagen de un auto azul.] "Convierte este auto en un convertible". “Ahora cambia el color a amarillo”.
Edición de imágenes con Gemini
Para editar una imagen, agrega una como entrada. En el siguiente ejemplo, se muestra cómo subir imágenes codificadas en base64. Para varias imágenes y cargas útiles más grandes, consulta la sección entrada de imagen.

Python
JavaScript
REST

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

import PIL.Image

image = PIL.Image.open('/path/to/image.png')

client = genai.Client()

text_input = ('Hi, This is a picture of me.'
            'Can you add a llama next to me?',)

response = client.models.generate_content(
    model="gemini-2.0-flash-exp-image-generation",
    contents=[text_input, image],
    config=types.GenerateContentConfig(
      response_modalities=['TEXT', 'IMAGE']
    )
)

for part in response.candidates[0].content.parts:
  if part.text is not None:
    print(part.text)
  elif part.inline_data is not None:
    image = Image.open(BytesIO(part.inline_data.data))
    image.show()
Limitaciones
Para obtener el mejor rendimiento, usa los siguientes idiomas: EN, es-MX, ja-JP, zh-CN, hi-IN.
La generación de imágenes no admite entradas de audio ni video.
Es posible que la generación de imágenes no siempre active lo siguiente:
El modelo solo puede generar texto. Intenta solicitar resultados de imagen de forma explícita (p.ej., “genera una imagen”, “proporciona imágenes a medida que avanzas”, “actualiza la imagen”).
Es posible que el modelo deje de generar contenido a mitad del proceso. Vuelve a intentarlo o prueba con otra instrucción.
Cuando generas texto para una imagen, Gemini funciona mejor si primero generas el texto y, luego, le pides una imagen con el texto.
Elige un modelo
¿Qué modelo deberías usar para generar imágenes? Depende de tu caso de uso.

Gemini 2.0 es mejor para producir imágenes contextualmente relevantes, combinar texto y imágenes, incorporar el conocimiento del mundo y razonar sobre las imágenes. Puedes usarlo para crear imágenes precisas y contextualmente relevantes incorporadas en secuencias de texto largas. También puedes editar imágenes de forma conversacional, con lenguaje natural, y mantener el contexto durante la conversación.

Si la calidad de la imagen es tu prioridad, Imagen 3 es una mejor opción. La imagen 3 se destaca por su fotorrealismo, sus detalles artísticos y sus estilos artísticos específicos, como el impresionismo o el anime. Imagen 3 también es una buena opción para tareas especializadas de edición de imágenes, como actualizar los fondos de los productos, mejorar las imágenes y aplicar el desarrollo de la marca y el estilo a las imágenes. Puedes usar Imagen 3 para crear logotipos o cualquier otro diseño de producto de marca.

Genera imágenes con Imagen 3
La API de Gemini proporciona acceso a Imagen 3, el modelo de texto a imagen de mayor calidad de Google, que incluye varias funciones nuevas y mejoradas. Imagen 3 puede hacer lo siguiente:

Genera imágenes con mejores detalles, iluminación más rica y menos artefactos que distraen que los modelos anteriores.
Comprender instrucciones escritas en lenguaje natural
Genera imágenes en una amplia variedad de formatos y estilos
Renderiza el texto de forma más eficaz que los modelos anteriores.
Nota: Imagen 3 solo está disponible en el nivel pagado y siempre incluye una marca de agua de SynthID.
Python
JavaScript
REST

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client(api_key='GEMINI_API_KEY')

response = client.models.generate_images(
    model='imagen-3.0-generate-002',
    prompt='Robot holding a red skateboard',
    config=types.GenerateImagesConfig(
        number_of_images= 4,
    )
)
for generated_image in response.generated_images:
  image = Image.open(BytesIO(generated_image.image.image_bytes))
  image.show()
Imagen generada por IA de dos conejos peludos en la cocina
Imagen generada por IA de dos conejos peludos en la cocina
Por el momento, Imagen solo admite instrucciones en inglés y los siguientes parámetros:

Parámetros del modelo de Imagen
(Las convenciones de nombres varían según el lenguaje de programación).

numberOfImages: Es la cantidad de imágenes que se generarán, de 1 a 4 (inclusive). El valor predeterminado es 4.
aspectRatio: Cambia la relación de aspecto de la imagen generada. Los valores admitidos son "1:1", "3:4", "4:3", "9:16" y "16:9". El valor predeterminado es "1:1".
personGeneration: Permite que el modelo genere imágenes de personas. Se admiten los siguientes valores:
"DONT_ALLOW": Bloquea la generación de imágenes de personas.
"ALLOW_ADULT": Genera imágenes de adultos, pero no de niños. Es el valor predeterminado.
¿Qué sigue?
Si deseas obtener más información sobre cómo escribir instrucciones para Imagen, consulta la guía de instrucciones de Imagen.
Para obtener más información sobre los modelos de Gemini 2.0, consulta Modelos de Gemini y Modelos experimentales.
¿Te resultó útil?