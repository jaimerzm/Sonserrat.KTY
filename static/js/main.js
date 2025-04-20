document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    
    const modelSelector = document.getElementById('model-selector'); // Get the hidden select
    const modelNameElements = document.querySelectorAll('#model-name'); // Get all elements displaying the model name

    // Model selection is handled by model-selector-enhanced.js
    const messagesContainer = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const chatForm = document.getElementById('chat-form');
    const newChatButton = document.getElementById('new-chat');
    const recentChats = document.querySelector('.recent-chats');
    const starredChats = document.querySelector('.starred-chats');
    const videoButton = document.getElementById('video-button');
    const webSearchButton = document.getElementById('web-search');
    const fileInput = document.getElementById('file-input');
    const attachmentsPreview = document.getElementById('attachments-preview');
    const userInfoTrigger = document.getElementById('user-info-trigger');
    const userDropdown = document.getElementById('user-dropdown');
    const logoutButtonDiscrete = document.querySelector('.logout-button-discrete');

    // Video options elements
    const videoOptionsContainer = document.getElementById('video-options');
    const videoDurationSlider = document.getElementById('video-duration');
    const durationValueSpan = document.getElementById('duration-value');
    const videoCountSlider = document.getElementById('video-count');
    const countValueSpan = document.getElementById('count-value');
    // Nuevos controles de video
    const videoControlsDiv = document.querySelector('.video-controls');
    const videoDurationSelect = document.getElementById('video-duration');
    const videoAspectSelect = document.getElementById('video-aspect');
    const videoCountInput = document.getElementById('video-count');

    let currentConversationId = null;
    let isVideoMode = false;
    let isWebSearchMode = false;

    // Variables para manejar archivos
    let attachedFiles = new Map();

    // --- Video Options Logic Start ---
    function updateVideoOptionsVisibility() {
        const selectedModel = modelSelector.value;
        if (selectedModel === 'kkty2-video') {
            videoOptionsContainer.style.display = 'flex';
        } else {
            videoOptionsContainer.style.display = 'none';
        }
    }

    if (videoDurationSlider && durationValueSpan) {
        videoDurationSlider.addEventListener('input', () => {
            durationValueSpan.textContent = `${videoDurationSlider.value}s`;
        });
        // Set initial value display
        durationValueSpan.textContent = `${videoDurationSlider.value}s`;
    }

    if (videoCountSlider && countValueSpan) {
        videoCountSlider.addEventListener('input', () => {
            countValueSpan.textContent = videoCountSlider.value;
        });
        // Set initial value display
        countValueSpan.textContent = videoCountSlider.value;
    }

    // Listen for changes on the hidden model selector
    modelSelector.addEventListener('change', updateVideoOptionsVisibility);

    // Initial check on page load
    updateVideoOptionsVisibility();
    // --- Video Options Logic End ---

    // --- Visibilidad de Controles de Video (NUEVO) ---
    function updateVideoControlsVisibility() {
        const selectedModel = modelSelector.value;
        if (selectedModel === 'kkty2-video') {
            videoControlsDiv.classList.add('visible');
        } else {
            videoControlsDiv.classList.remove('visible');
        }
    }

    // Escuchar cambios en el selector de modelo
    modelSelector.addEventListener('change', updateVideoControlsVisibility);

    // Comprobación inicial al cargar la página
    updateVideoControlsVisibility();
    // --- Fin Visibilidad Controles ---

    // Toggle user dropdown menu
    userInfoTrigger.addEventListener('click', () => {
        userDropdown.classList.toggle('active');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (event) => {
        if (!userInfoTrigger.contains(event.target) && !userDropdown.contains(event.target)) {
            userDropdown.classList.remove('active');
        }
    });

    // Handle header logout button click
    if (logoutButtonDiscrete) {
        logoutButtonDiscrete.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Header logout button clicked');
            window.location.href = '/logout';
        });
    }

    // Cargar conversaciones al inicio
    function loadConversations() {
        fetch('/api/conversations')
            .then(response => response.json())
            .then(data => {
                recentChats.innerHTML = '';
                starredChats.innerHTML = '';
                
                data.conversations.forEach(conv => {
                    const chatItem = document.createElement('div');
                    chatItem.className = 'chat-item';
                    
                    const chatTitle = document.createElement('span');
                    chatTitle.textContent = conv.title || 'Nueva conversación';
                    chatItem.appendChild(chatTitle);
                    
                    const starButton = document.createElement('button');
                    starButton.className = `star-btn ${conv.starred ? 'starred' : ''}`;
                    starButton.innerHTML = '<i class="fas fa-star"></i>';
                    
                    // Improved star button click handler
                    starButton.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        toggleStar(conv.id, !conv.starred);
                        
                        // Update visual feedback immediately
                        starButton.classList.toggle('starred');
                    };
                    
                    chatItem.appendChild(starButton);
                    chatItem.dataset.id = conv.id;
                    chatItem.addEventListener('click', () => loadConversation(conv.id));
                    
                    // Move chat item to appropriate section
                    if (conv.starred) {
                        starredChats.appendChild(chatItem);
                    } else {
                        recentChats.appendChild(chatItem);
                    }
                });
            })
            .catch(error => console.error('Error cargando conversaciones:', error));
    }

    function toggleStar(conversationId, starred) {
        fetch(`/api/conversations/${conversationId}/star`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ starred })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Reload conversations to update the UI
                loadConversations();
            }
        })
        .catch(error => console.error('Error al cambiar estado destacado:', error));
    }
    // Cargar una conversación específica
    function loadConversation(conversationId) {
        fetch(`/api/conversations/${conversationId}`)
            .then(response => response.json())
            .then(data => {
                currentConversationId = conversationId;
                messagesContainer.innerHTML = '';
                data.messages.forEach(msg => {
                    addMessage(msg.content, msg.role === 'user');
                });
                highlightCurrentChat(conversationId);
            })
            .catch(error => console.error('Error cargando conversación:', error));
    }

    // Resaltar chat actual
    function highlightCurrentChat(conversationId) {
        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.id === conversationId) {
                item.classList.add('active');
            }
        });
    }

    // Nueva conversación
    newChatButton.addEventListener('click', () => {
        currentConversationId = null; // Reset conversation ID
        messagesContainer.innerHTML = ''; // Clear messages
        highlightCurrentChat(null); // Deselect any highlighted chat
        userInput.value = ''; // Clear input
        attachmentsPreview.innerHTML = ''; // Clear attachments
        attachmentsPreview.style.display = 'none';
        attachedFiles.clear();
        console.log('New chat started, conversation ID reset.');
        // The actual conversation record will be created by the backend
        // when the first message is sent with conversation_id = null.
    });

    // Función para agregar un mensaje al contenedor con animación
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        
        // Check for special markers (images, videos)
        const hasGeneratedImage = !isUser && content.includes('[GENERATED_IMAGE:');
        const hasGeneratedVideo = !isUser && content.includes('[GENERATED_VIDEO:');

        if (hasGeneratedImage) {
            // Extraer la URL de la imagen
            const imgMatch = content.match(/\[GENERATED_IMAGE:([^\]]+)\]/);
            if (imgMatch && imgMatch[1]) {
                const imgUrl = imgMatch[1];
                // Eliminar el marcador de la imagen del texto
                content = content.replace(imgMatch[0], '');
                
                // Crear contenedor para la imagen generada
                const imageContainer = document.createElement('div');
                imageContainer.className = 'generated-image';
                
                // Crear la imagen
                const img = document.createElement('img');
                img.src = imgUrl;
                img.alt = 'Imagen generada';
                img.loading = 'lazy';
                
                // Añadir la imagen al contenedor
                imageContainer.appendChild(img);
                bubbleDiv.appendChild(imageContainer);
            }
        }

        // Handle generated video display
        if (hasGeneratedVideo) {
            const videoMatch = content.match(/\[GENERATED_VIDEO:([^\)]+)\]/g);
            if (videoMatch) {
                content = content.replace(/\[GENERATED_VIDEO:[^\)]+\]/g, '').trim(); // Remove markers

                videoMatch.forEach(match => {
                    const videoUrl = match.slice('[GENERATED_VIDEO:'.length, -1);
                    const videoContainer = document.createElement('div');
                    videoContainer.className = 'generated-video';

                    const videoElement = document.createElement('video');
                    videoElement.src = videoUrl;
                    videoElement.controls = true;
                    videoElement.preload = 'metadata';
                    videoElement.style.maxWidth = '100%';
                    videoElement.style.borderRadius = '8px';
                    videoElement.style.marginTop = '10px';

                    videoContainer.appendChild(videoElement);
                    bubbleDiv.appendChild(videoContainer);
                });
            }
        }

        // Si es un mensaje del asistente, procesar Markdown y animar si es necesario
        if (!isUser && content.length > 0) {
            // Usar marked.parse para convertir Markdown a HTML
            const htmlContent = marked.parse(content);
            textDiv.innerHTML = htmlContent; // Usar innerHTML para renderizar el HTML
            // La animación de caracteres se elimina ya que interfiere con el HTML renderizado
            // Si se desea animación, se necesitaría un enfoque más complejo
        } else {
            // Para mensajes de usuario, simplemente asignar el texto
            textDiv.textContent = content;
        }
        
        bubbleDiv.appendChild(textDiv);
        messageDiv.appendChild(bubbleDiv);
        messagesContainer.appendChild(messageDiv);
        
        // Scroll al último mensaje
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Manejar subida de archivos
    fileInput.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files);
        
        // Validar el tamaño y tipo de archivo
        for (const file of files) {
            const fileId = Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            
            // Validar tipo de archivo
            if (!file.type.match(/^image\/(jpeg|png|gif|webp)$/)) {
                console.error(`Tipo de archivo no permitido: ${file.type}`);
                continue;
            }
            
            // Validar tamaño (20MB)
            if (file.size > 20 * 1024 * 1024) {
                console.error(`Archivo demasiado grande: ${file.size} bytes`);
                continue;
            }
            
            attachedFiles.set(fileId, file);
            
            const preview = document.createElement('div');
            preview.className = 'attachment-preview';
            preview.dataset.fileId = fileId;
            
            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                preview.appendChild(img);
            }
            
            const removeButton = document.createElement('button');
            removeButton.className = 'remove-attachment';
            removeButton.innerHTML = '×';
            removeButton.onclick = () => {
                attachedFiles.delete(fileId);
                preview.remove();
                if (attachedFiles.size === 0) {
                    attachmentsPreview.style.display = 'none';
                }
            };
            
            preview.appendChild(removeButton);
            attachmentsPreview.appendChild(preview);
        }
        
        if (attachedFiles.size > 0) {
            attachmentsPreview.style.display = 'flex';
        }
        
        // Limpiar el input para permitir seleccionar el mismo archivo nuevamente
        fileInput.value = '';
    });

    // Manejar el envío de mensajes
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage();
    });

    // Manejar tecla Enter
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Manejar modo video
    videoButton.addEventListener('click', () => {
        isVideoMode = !isVideoMode;
        document.getElementById('video-mode').classList.toggle('active', isVideoMode);
        videoButton.classList.toggle('active', isVideoMode);
    });

    // Manejar modo búsqueda web
    webSearchButton.addEventListener('click', () => {
        isWebSearchMode = !isWebSearchMode;
        document.getElementById('search-mode').classList.toggle('active', isWebSearchMode);
        webSearchButton.classList.toggle('active', isWebSearchMode);
    });

    // Manejar las respuestas del socket
    socket.on('message', (data) => {
        console.log("Mensaje recibido:", data); // Para depuración

        const loadingIndicator = document.querySelector('.loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }

        const progressContainer = document.querySelector('.progress-container');

        // Si es un mensaje final de streaming (done: true) y había un contenedor de progreso
        if (data.done && progressContainer) {
            // Finalizar el mensaje en progreso, no añadir uno nuevo si el contenido está vacío
            progressContainer.classList.remove('progress-container'); // Quitar clase de progreso
            // No hacer nada más si data.content está vacío, el contenido ya está en progressContainer
            if (data.content) { // Si el mensaje final tiene contenido (caso no-streaming o error)
                 progressContainer.remove(); // Eliminar el contenedor de progreso si existía
                 addMessage(data.content, false); // Añadir el contenido final como mensaje normal
            }
        } else if (data.role === 'assistant' && data.content) {
            // Mensaje normal (no streaming) o error con contenido
            if (progressContainer) {
                progressContainer.remove(); // Limpiar si había progreso anterior
            }
            addMessage(data.content, false);
        } else if (data.role === 'user' && data.content) {
            // Los mensajes del usuario ya se añaden en sendMessage
            // No hacer nada aquí para evitar duplicados
        } else if (data.error) {
            // Mostrar mensaje de error del sistema
            if (progressContainer) {
                progressContainer.remove();
            }
            addMessage(`Error del servidor: ${data.error}`, false);
        }

        // El scroll al último mensaje ya se maneja dentro de addMessage o al actualizar progreso
    });

    // Manejar actualizaciones de progreso para respuestas en streaming
    socket.on('message_progress', (data) => {
        let progressContainer = document.querySelector('.progress-container');
        
        // Si no existe el contenedor de progreso, crearlo
        if (!progressContainer) {
            // Eliminar el indicador de carga si existe
            const loadingIndicator = document.querySelector('.loading-indicator');
            if (loadingIndicator) {
                loadingIndicator.remove();
            }
            
            progressContainer = document.createElement('div');
            progressContainer.className = 'message assistant-message progress-container'; // Añadir clase progress-container
            
            const bubbleDiv = document.createElement('div');
            bubbleDiv.className = 'message-bubble';
            
            const textDiv = document.createElement('div');
            textDiv.className = 'message-text progress-text'; // Usar clase específica para el texto en progreso
            textDiv.textContent = ''; // Iniciar vacío
            
            bubbleDiv.appendChild(textDiv);
            progressContainer.appendChild(bubbleDiv);
            messagesContainer.appendChild(progressContainer);
        }
        
        // Actualizar el contenido del contenedor de progreso
        const textDiv = progressContainer.querySelector('.progress-text');
        if (textDiv) { // Asegurarse que textDiv existe
             textDiv.textContent += data.content;
        }
        
        // Scroll al final
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    });

    // Función para mostrar el indicador de carga
    function showLoadingIndicator() {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant-message loading-indicator';
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        
        const loadingText = document.createElement('div');
        loadingText.className = 'message-text';
        loadingText.textContent = 'Pensando...';
        
        bubbleDiv.appendChild(loadingText);
        loadingDiv.appendChild(bubbleDiv);
        messagesContainer.appendChild(loadingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Función para enviar mensajes
    function sendMessage() {
        const messageText = userInput.value.trim();
        const selectedModel = modelSelector.value;

        if (!messageText && attachedFiles.size === 0) return;

        // Mostrar mensaje del usuario inmediatamente
        addMessage(messageText, true);

        // Mostrar indicador de carga
        const loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'message assistant-message loading-indicator';
        loadingIndicator.innerHTML = `
            <div class="message-bubble">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        messagesContainer.appendChild(loadingIndicator);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // Preparar datos para enviar
        const formData = new FormData();
        formData.append('message', messageText);
        formData.append('model', selectedModel);
        formData.append('conversation_id', currentConversationId);
        formData.append('web_search', isWebSearchMode);

        // Añadir parámetros de video si el modelo es kkty2-video
        if (selectedModel === 'kkty2-video') {
            // Leer valores de los nuevos controles
            const duration = videoDurationSelect.value;
            const aspect = videoAspectSelect.value;
            const count = videoCountInput.value;

            formData.append('durationSeconds', duration);
            formData.append('numberOfVideos', count);
            formData.append('video_aspect_ratio', aspect); // Añadir aspect ratio
            console.log(`Enviando parámetros de video: Duración=${duration}s, Cantidad=${count}, Aspecto=${aspect}`);
        }

        // Añadir archivos adjuntos
        attachedFiles.forEach((file, fileId) => {
            formData.append('attachments', file, file.name);
        });

            .then(response => {
                if (!response.ok) {
                    // Intentar obtener el mensaje de error del cuerpo JSON
                    return response.json().then(errData => {
                        throw new Error(errData.message || `Error del servidor: ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log('Respuesta del servidor:', data); // Para depuración
                // Actualizar SIEMPRE el ID de la conversación actual
                if (data.conversation_id) {
                    currentConversationId = data.conversation_id;
                    highlightCurrentChat(currentConversationId);
                }
                // Recargar conversaciones SOLO si es una nueva conversación
                if (data.is_new_conversation === true) {
                    // Añadir un pequeño retraso para dar tiempo a la generación del título
                    setTimeout(() => {
                        loadConversations();
                    }, 500); // 500ms de retraso
                }
                // No añadir mensaje del usuario aquí, se añade al recibirlo por socket
                // addMessage(message, true);
                userInput.value = '';
                attachedFiles.clear();
                attachmentsPreview.innerHTML = '';
                attachmentsPreview.style.display = 'none';

                // Mostrar indicador de carga
                showLoadingIndicator();
            })
    }

    // Función para crear una vista previa del mensaje con imágenes
    function createMessagePreview(message, files) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.textContent = message;
        bubbleDiv.appendChild(textDiv);
        
        if (files && files.size > 0) {
            const attachmentsDiv = document.createElement('div');
            attachmentsDiv.className = 'message-attachments';
            
            for (const [fileId, file] of files) {
                const attachmentDiv = document.createElement('div');
                attachmentDiv.className = 'message-attachment';
                
                if (file.type.startsWith('image/')) {
                    const img = document.createElement('img');
                    img.src = URL.createObjectURL(file);
                    img.className = 'message-image';
                    attachmentDiv.appendChild(img);
                } else {
                    const icon = document.createElement('i');
                    icon.className = 'fas fa-file';
                    attachmentDiv.appendChild(icon);
                    const fileName = document.createElement('span');
                    fileName.textContent = file.name;
                    attachmentDiv.appendChild(fileName);
                }
                
                attachmentsDiv.appendChild(attachmentDiv);
            }
            
            bubbleDiv.appendChild(attachmentsDiv);
        }
        
        messageDiv.appendChild(bubbleDiv);
        return messageDiv;
    }

    // Auto-resize del textarea
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = Math.min(userInput.scrollHeight, 150) + 'px';
    });

    // Manejar errores de conexión
    socket.on('connect_error', (error) => {
        console.error('Error de conexión:', error);
        const loadingIndicator = messagesContainer.querySelector('.loading');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
        addMessage('Error de conexión con el servidor. Por favor, intenta de nuevo más tarde.');
    });
    
    // Manejar actualizaciones de título de conversación
    socket.on('conversation_update', (data) => {
        console.log('Actualización de conversación recibida:', data);
        const conversationId = data.id;
        const newTitle = data.title;
        
        // Actualizar el título en la barra lateral
        const conversationElement = document.querySelector(`.chat-item[data-id="${conversationId}"]`);
        if (conversationElement) {
            conversationElement.textContent = newTitle;
        } else {
            // Si el elemento no existe, podría ser una nueva conversación
            // Recargar la lista de conversaciones
            loadConversations();
        }
    });

    // Cargar conversaciones al inicio
    loadConversations();
});

