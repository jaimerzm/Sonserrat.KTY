document.addEventListener('DOMContentLoaded', () => {
    // Crear el botón de hamburguesa y el overlay
    const appContainer = document.querySelector('.app-container');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    
    if (!appContainer || !sidebar || !mainContent) {
        console.error('Elementos necesarios no encontrados');
        return;
    }
    
    // Crear el botón de hamburguesa
    const hamburgerButton = document.createElement('button');
    hamburgerButton.className = 'hamburger-menu';
    hamburgerButton.innerHTML = `
        <div class="hamburger-icon">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    
    // Crear el overlay para cerrar el sidebar al tocar fuera
    const sidebarOverlay = document.createElement('div');
    sidebarOverlay.className = 'sidebar-overlay';
    
    // Añadir elementos al DOM
    document.body.appendChild(hamburgerButton);
    appContainer.appendChild(sidebarOverlay);
    
    // Función para alternar el sidebar
    function toggleSidebar() {
        sidebar.classList.toggle('active');
        hamburgerButton.classList.toggle('active');
        sidebarOverlay.classList.toggle('active');
        
        // Añadir/quitar clase para evitar scroll en el body cuando el sidebar está abierto
        document.body.classList.toggle('sidebar-open');
    }
    
    // Event listeners
    hamburgerButton.addEventListener('click', toggleSidebar);
    sidebarOverlay.addEventListener('click', toggleSidebar);
    
    // Cerrar sidebar al cambiar el tamaño de la ventana a desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768 && sidebar.classList.contains('active')) {
            toggleSidebar();
        }
    });
    
    // Cerrar sidebar al hacer clic en un elemento del sidebar (como un chat)
    // Usamos delegación de eventos para manejar los chats existentes y los que se crean dinámicamente
    document.addEventListener('click', (event) => {
        const chatItem = event.target.closest('.chat-item');
        if (chatItem && window.innerWidth <= 768 && sidebar.classList.contains('active')) {
            toggleSidebar();
        }
    });
    
    // Observamos cambios en el DOM para asegurarnos que los nuevos chats tengan el comportamiento correcto
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1 && node.classList && node.classList.contains('chat-item')) {
                        // No necesitamos agregar event listeners aquí gracias a la delegación de eventos
                    }
                });
            }
        });
    });
    
    // Observamos los contenedores de chats
    const recentChats = document.querySelector('.recent-chats');
    const starredChats = document.querySelector('.starred-chats');
    
    if (recentChats) {
        observer.observe(recentChats, { childList: true });
    }
    
    if (starredChats) {
        observer.observe(starredChats, { childList: true });
    }
});