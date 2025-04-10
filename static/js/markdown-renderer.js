/**
 * markdown-renderer.js
 * Funcionalidad para renderizar Markdown en los mensajes del asistente
 */

document.addEventListener('DOMContentLoaded', () => {
    // Configurar marked.js con opciones seguras
    marked.setOptions({
        breaks: true, // Convertir saltos de línea en <br>
        gfm: true,    // GitHub Flavored Markdown
        headerIds: false, // No generar IDs para los encabezados
        sanitize: false, // La sanitización está obsoleta en marked
        smartLists: true,
        smartypants: true,
        highlight: function(code, lang) {
            // Función mejorada para resaltar código
            // Añadir clases para mejor estilizado
            return `<div class="code-highlight">${code}</div>`;
        }
    });

    // Función para renderizar Markdown en mensajes existentes
    function renderMarkdownInExistingMessages() {
        const assistantMessages = document.querySelectorAll('.assistant-message .message-text');
        
        assistantMessages.forEach(messageText => {
            // Verificar si ya ha sido procesado
            if (!messageText.classList.contains('markdown-content')) {
                renderMarkdown(messageText);
            }
        });
    }

    // Función para renderizar Markdown en un elemento
    function renderMarkdown(messageElement) {
        // Obtener el texto original
        const originalText = messageElement.textContent;
        
        // Verificar si hay contenido para renderizar
        if (originalText && originalText.trim()) {
            // Convertir el texto a HTML con Markdown
            const renderedHtml = marked.parse(originalText);
            
            // Aplicar el HTML renderizado
            messageElement.innerHTML = renderedHtml;
            
            // Añadir clase para aplicar estilos
            messageElement.classList.add('markdown-content');
            
            // Aplicar estilos específicos a bloques de código
            const codeBlocks = messageElement.querySelectorAll('pre code');
            codeBlocks.forEach(codeBlock => {
                // Añadir clases para estilizar
                codeBlock.parentNode.classList.add('code-block-wrapper');
            });
        }
    }

    // Observador de mutaciones para detectar nuevos mensajes
    const messagesContainer = document.getElementById('chat-messages');
    if (messagesContainer) {
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1) {
                            // Si es un mensaje del asistente
                            if (node.classList.contains('assistant-message')) {
                                const messageText = node.querySelector('.message-text');
                                if (messageText && !messageText.classList.contains('markdown-content')) {
                                    // Esperar a que el contenido esté completo (para mensajes en streaming)
                                    setTimeout(() => {
                                        renderMarkdown(messageText);
                                    }, 100);
                                }
                            }
                            // Si es un contenedor de progreso (para streaming)
                            else if (node.classList.contains('progress-container')) {
                                const progressText = node.querySelector('.progress-text');
                                if (progressText) {
                                    // Observar cambios en el texto de progreso
                                    const textObserver = new MutationObserver(() => {
                                        // No renderizar mientras está en progreso para evitar parpadeos
                                        // Solo añadir la clase para aplicar estilos básicos
                                        progressText.classList.add('markdown-content');
                                    });
                                    
                                    textObserver.observe(progressText, { 
                                        childList: true, 
                                        characterData: true,
                                        subtree: true 
                                    });
                                }
                            }
                        }
                    });
                }
            });
        });

        observer.observe(messagesContainer, { childList: true, subtree: true });
    }

    // Renderizar Markdown en mensajes existentes al cargar la página
    renderMarkdownInExistingMessages();

    // Función para renderizar Markdown en mensajes completos después del streaming
    function renderMarkdownAfterStreaming() {
        // Buscar el contenedor de progreso que ya no está en progreso
        const completedProgressContainers = document.querySelectorAll('.progress-container:not(.in-progress)');
        
        completedProgressContainers.forEach(container => {
            const messageText = container.querySelector('.progress-text');
            if (messageText && !messageText.classList.contains('rendered')) {
                renderMarkdown(messageText);
                messageText.classList.add('rendered');
            }
        });
    }

    // Escuchar eventos de socket para saber cuándo se completa un mensaje
    if (typeof socket !== 'undefined') {
        socket.on('message', (data) => {
            if (data.done) {
                // Cuando un mensaje está completo, renderizar Markdown
                setTimeout(renderMarkdownAfterStreaming, 200);
            }
        });
    }
});