/**
 * clipboard.js
 * Funcionalidad para añadir botones de copiar al portapapeles en los mensajes del asistente
 */

document.addEventListener('DOMContentLoaded', () => {
    // Función para añadir botones de copiar a los mensajes existentes
    function addCopyButtonsToExistingMessages() {
        const assistantMessages = document.querySelectorAll('.assistant-message .message-bubble');
        
        assistantMessages.forEach(messageBubble => {
            // Verificar si ya tiene un botón de copiar
            if (!messageBubble.querySelector('.copy-button')) {
                addCopyButton(messageBubble);
            }
        });
    }

    // Función para añadir un botón de copiar a un mensaje
    function addCopyButton(messageBubble) {
        const copyButton = document.createElement('button');
        copyButton.className = 'copy-button';
        copyButton.innerHTML = '<i class="fas fa-copy"></i>';
        copyButton.title = 'Copiar al portapapeles';
        copyButton.setAttribute('aria-label', 'Copiar al portapapeles');
        
        copyButton.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Obtener el texto del mensaje (excluyendo el botón)
            const messageText = messageBubble.querySelector('.message-text');
            if (messageText) {
                // Crear un elemento temporal para obtener el texto sin formato
                const tempElement = document.createElement('div');
                tempElement.innerHTML = messageText.innerHTML;
                
                // Eliminar los elementos de animación y obtener el texto plano
                const spans = tempElement.querySelectorAll('span.char');
                spans.forEach(span => {
                    span.parentNode.replaceChild(document.createTextNode(span.textContent), span);
                });
                
                // Manejar elementos Markdown específicos para preservar formato en texto plano
                // Convertir encabezados a texto con formato
                tempElement.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(heading => {
                    const level = parseInt(heading.tagName.substring(1));
                    const prefix = '#'.repeat(level) + ' ';
                    heading.prepend(document.createTextNode(prefix));
                });
                
                // Convertir listas a texto con formato
                tempElement.querySelectorAll('ul li, ol li').forEach(item => {
                    const isOrdered = item.parentNode.tagName.toLowerCase() === 'ol';
                    const prefix = isOrdered ? '1. ' : '- ';
                    item.prepend(document.createTextNode(prefix));
                });
                
                // Convertir bloques de código a texto con formato
                tempElement.querySelectorAll('pre code').forEach(code => {
                    const codeText = code.textContent;
                    code.textContent = '```\n' + codeText + '\n```';
                });
                
                // Preservar enlaces
                tempElement.querySelectorAll('a').forEach(link => {
                    const href = link.getAttribute('href');
                    if (href && href !== link.textContent) {
                        link.textContent = `${link.textContent} (${href})`;
                    }
                });
                
                const textToCopy = tempElement.textContent;
                
                // Copiar al portapapeles
                navigator.clipboard.writeText(textToCopy)
                    .then(() => {
                        // Mostrar feedback visual
                        copyButton.innerHTML = '<i class="fas fa-check"></i>';
                        copyButton.classList.add('copied');
                        
                        // Restaurar el icono después de 2 segundos
                        setTimeout(() => {
                            copyButton.innerHTML = '<i class="fas fa-copy"></i>';
                            copyButton.classList.remove('copied');
                        }, 2000);
                    })
                    .catch(err => {
                        console.error('Error al copiar texto: ', err);
                        copyButton.innerHTML = '<i class="fas fa-times"></i>';
                        copyButton.classList.add('error');
                        
                        setTimeout(() => {
                            copyButton.innerHTML = '<i class="fas fa-copy"></i>';
                            copyButton.classList.remove('error');
                        }, 2000);
                    });
            }
        });
        
        messageBubble.appendChild(copyButton);
    }

    // Observador de mutaciones para detectar nuevos mensajes
    const messagesContainer = document.getElementById('chat-messages');
    if (messagesContainer) {
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1 && node.classList.contains('assistant-message')) {
                            const messageBubble = node.querySelector('.message-bubble');
                            if (messageBubble && !messageBubble.querySelector('.copy-button')) {
                                addCopyButton(messageBubble);
                            }
                        }
                    });
                }
            });
        });

        observer.observe(messagesContainer, { childList: true, subtree: true });
    }

    // Añadir botones a los mensajes existentes al cargar la página
    addCopyButtonsToExistingMessages();
});