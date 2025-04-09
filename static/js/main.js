document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    
    const modelName = document.getElementById('model-name');

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

    let currentConversationId = null;
    let isVideoMode = false;
    let isWebSearchMode = false;

    // Variables para manejar archivos
    let attachedFiles = new Map();

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
        fetch('/api/conversations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            currentConversationId = data.id;
            messagesContainer.innerHTML = '';
            loadConversations();
        })
        .catch(error => console.error('Error creando conversación:', error));
    });

    // Función para agregar un mensaje al contenedor con animación
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        
        // Verificar si el contenido incluye una imagen generada (formato especial)
        const hasGeneratedImage = !isUser && content.includes('[GENERATED_IMAGE:');
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

        // Si es un mensaje del asistente, animamos el texto
        if (!isUser && content.length > 0) {
            // Dividir el contenido en palabras manteniendo los espacios
            const words = content.split(/(\s+)/);
            let delay = 0;
            
            words.forEach((word) => {
                const wordSpan = document.createElement('span');
                wordSpan.style.display = 'inline-block';
                
                // Si es un espacio, lo agregamos directamente
                if (/^\s+$/.test(word)) {
                    wordSpan.textContent = word;
                    textDiv.appendChild(wordSpan);
                    return;
                }
                
                // Para cada carácter en la palabra
                Array.from(word).forEach((char) => {
                    const span = document.createElement('span');
                    span.textContent = char;
                    span.className = 'char';
                    span.style.animationDelay = `${delay}ms`;
                    
                    // Ajustar la velocidad de la animación según la longitud del mensaje
                    if (content.length < 50) {
                        span.classList.add('short');
                        delay += 30;
                    } else if (content.length < 200) {
                        span.classList.add('medium');
                        delay += 20;
                    } else {
                        span.classList.add('long');
                        delay += 10;
                    }
                    
                    wordSpan.appendChild(span);
                });
                
                textDiv.appendChild(wordSpan);
            });
        } else {
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
        
        // Ocultar el indicador de carga
        const loadingIndicator = document.querySelector('.loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }

        // Eliminar el contenedor de progreso si existe
        const progressContainer = document.querySelector('.progress-container');
        if (progressContainer) {
            progressContainer.remove();
        }

        // Crear contenedor principal del mensaje
        const messageContainerDiv = document.createElement('div');
        messageContainerDiv.className = 'message ' + (data.role === 'user' ? 'user-message' : 'assistant-message');

        // Crear la burbuja del mensaje
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';

        // --- Lógica para mostrar texto o imagen ---
        if (data.type === 'image_url' && data.content && data.role === 'assistant') {
            // Es una URL de imagen generada
            const imgContainer = document.createElement('div');
            imgContainer.className = 'image-container';
            
            // Crear indicador de carga para la imagen
            const loadingIndicator = document.createElement('div');
            loadingIndicator.className = 'image-loading-indicator';
            loadingIndicator.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cargando imagen...';
            imgContainer.appendChild(loadingIndicator);
            
            // Crear elemento de imagen
            const imgElement = document.createElement('img');
            imgElement.src = data.content; // La URL está en 'content'
            imgElement.alt = "Imagen generada por IA";
            imgElement.className = 'generated-image';
            imgElement.style.display = 'none'; // Ocultar hasta que cargue
            
            // Cuando la imagen carga correctamente
            imgElement.onload = () => {
                // Ocultar indicador de carga
                loadingIndicator.style.display = 'none';
                // Mostrar la imagen
                imgElement.style.display = 'block';
                // Hacer scroll
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            // Manejar error si la URL no carga
            imgElement.onerror = () => {
                loadingIndicator.style.display = 'none';
                const errorMsg = document.createElement('div');
                errorMsg.className = 'image-error-message';
                errorMsg.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error al cargar la imagen generada';
                imgContainer.appendChild(errorMsg);
            }
            
            imgContainer.appendChild(imgElement);
            bubbleDiv.appendChild(imgContainer);
        } else if (data.type === 'text' || !data.type || data.role === 'user') {
            // Es un mensaje de texto (del usuario o del asistente) o un error como texto
            if (data.role === 'assistant' && data.content) {
                // Usar la función existente de animación de escritura
                const textDiv = document.createElement('div');
                textDiv.className = 'message-text';
                
                // Dividir el contenido en palabras manteniendo los espacios
                const words = data.content.split(/(s+)/);
                let delay = 0;
                
                words.forEach((word) => {
                    const wordSpan = document.createElement('span');
                    wordSpan.style.display = 'inline-block';
                    
                    // Si es un espacio, lo agregamos directamente
                    if (/^\s+$/.test(word)) {
                        wordSpan.textContent = word;
                        textDiv.appendChild(wordSpan);
                        return;
                    }
                    
                    // Para cada carácter en la palabra
                    Array.from(word).forEach((char) => {
                        const span = document.createElement('span');
                        span.textContent = char;
                        span.className = 'char';
                        span.style.animationDelay = `${delay}ms`;
                        
                        // Ajustar la velocidad de la animación según la longitud del mensaje
                        if (data.content.length < 50) {
                            span.classList.add('short');
                            delay += 30;
                        } else if (data.content.length < 200) {
                            span.classList.add('medium');
                            delay += 20;
                        } else {
                            span.classList.add('long');
                            delay += 10;
                        }
                        
                        wordSpan.appendChild(span);
                    });
                    
                    textDiv.appendChild(wordSpan);
                });
                
                bubbleDiv.appendChild(textDiv);
            } else if (data.role === 'user' && data.content) {
                const textDiv = document.createElement('div');
                textDiv.className = 'message-text';
                textDiv.textContent = data.content;
                bubbleDiv.appendChild(textDiv);
            } else if (data.error) {
                const textDiv = document.createElement('div');
                textDiv.className = 'message-text';
                textDiv.textContent = data.error;
                bubbleDiv.appendChild(textDiv);
            } else {
                // Manejar caso de contenido vacío o inesperado
                const textDiv = document.createElement('div');
                textDiv.className = 'message-text';
                textDiv.textContent = "[Mensaje vacío o inesperado]";
                bubbleDiv.appendChild(textDiv);
                console.warn("Mensaje recibido sin contenido de texto:", data);
            }
        } else {
            // Tipo de mensaje no reconocido
            const textDiv = document.createElement('div');
            textDiv.className = 'message-text';
            textDiv.textContent = "[Tipo de mensaje no soportado]";
            bubbleDiv.appendChild(textDiv);
            console.error("Tipo de mensaje no reconocido:", data);
        }
        // --- Fin de la lógica ---

        messageContainerDiv.appendChild(bubbleDiv);
        messagesContainer.appendChild(messageContainerDiv);
        
        // Hacer scroll solo después de añadir el elemento
        // y potencialmente después de que la imagen cargue (ver onload de img)
        if (data.type !== 'image_url') { // Scroll inmediato para texto
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
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
            progressContainer.className = 'message assistant-message progress-container';
            
            const bubbleDiv = document.createElement('div');
            bubbleDiv.className = 'message-bubble';
            
            const textDiv = document.createElement('div');
            textDiv.className = 'message-text progress-text';
            textDiv.textContent = '';
            
            bubbleDiv.appendChild(textDiv);
            progressContainer.appendChild(bubbleDiv);
            messagesContainer.appendChild(progressContainer);
        }
        
        // Actualizar el contenido del contenedor de progreso
        const textDiv = progressContainer.querySelector('.progress-text');
        textDiv.textContent += data.content;
        
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

    async function sendMessage() {
        const message = userInput.value.trim();
        
        if (message === '' && attachedFiles.size === 0) return;
        
        try {
            // Convertir archivos a base64
            const base64Files = [];
            for (const [fileId, file] of attachedFiles) {
                const base64 = await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.readAsDataURL(file);
                });
                base64Files.push(base64);
            }

            // Crear y mostrar la vista previa del mensaje del usuario
            const messagePreview = createMessagePreview(message, attachedFiles);
            messagesContainer.appendChild(messagePreview);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            // Mostrar indicador de carga
            showLoadingIndicator();

            // Emitir el mensaje y los archivos
            // Get the current model from the selector element
            const modelSelector = document.getElementById('model-selector');
            const modelValue = modelSelector ? modelSelector.value : 'gemini';
            
            // Verificar si es una solicitud de generación o edición de imagen
            const isImageGeneration = modelValue === 'gemini-flash';
            
            // Determinar si es una solicitud de edición de imagen
            // (cuando hay archivos adjuntos y el modelo es gemini-flash)
            const isImageEdit = isImageGeneration && attachedFiles.size > 0;
            
            socket.emit('message', {
                message: message,
                conversationId: currentConversationId,
                videoMode: isVideoMode,
                webSearch: isWebSearchMode,
                hasAttachments: attachedFiles.size > 0,
                files: base64Files,
                model: modelValue,
                isImageGeneration: isImageGeneration,
                isImageEdit: isImageEdit
            });
            
            // Limpiar la entrada y los archivos adjuntos
            userInput.value = '';
            userInput.style.height = 'auto';
            attachedFiles.clear();
            attachmentsPreview.innerHTML = '';
            attachmentsPreview.style.display = 'none';
            
        } catch (error) {
            console.error('Error al enviar el mensaje:', error);
            const errorDiv = document.createElement('div');
            errorDiv.className = 'message system-message error';
            errorDiv.textContent = 'Error al enviar el mensaje. Por favor, intenta de nuevo.';
            messagesContainer.appendChild(errorDiv);
            
            // Ocultar el indicador de carga si hay error
            const loadingIndicator = document.querySelector('.loading-indicator');
            if (loadingIndicator) {
                loadingIndicator.remove();
            }
        }
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

