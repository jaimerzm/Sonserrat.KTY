document.addEventListener('DOMContentLoaded', () => {
    // Función para establecer el tema
    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        updateThemeIcon(theme);
    }

    // Función para actualizar el icono del botón según el tema
    function updateThemeIcon(theme) {
        const themeIcon = document.getElementById('theme-icon');
        const themeToggle = document.getElementById('theme-toggle');
        
        if (themeIcon) {
            themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
        
        if (themeToggle) {
            themeToggle.setAttribute('title', theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
            
            // Actualizar el indicador de tema del sistema
            const systemIndicator = document.getElementById('system-theme-indicator');
            if (systemIndicator) {
                if (localStorage.getItem('theme')) {
                    systemIndicator.style.display = 'none';
                } else {
                    systemIndicator.style.display = 'block';
                }
            }
        }
        
        // Notificar a los usuarios sobre el cambio de tema con un mensaje sutil
        const themeNotification = document.createElement('div');
        themeNotification.className = 'theme-notification';
        themeNotification.textContent = theme === 'dark' ? 'Modo oscuro activado' : 'Modo claro activado';
        themeNotification.style.position = 'fixed';
        themeNotification.style.bottom = '20px';
        themeNotification.style.right = '20px';
        themeNotification.style.padding = '8px 16px';
        themeNotification.style.borderRadius = '4px';
        themeNotification.style.backgroundColor = 'var(--accent-color)';
        themeNotification.style.color = 'white';
        themeNotification.style.zIndex = '9999';
        themeNotification.style.opacity = '0';
        themeNotification.style.transition = 'opacity 0.3s ease';
        
        document.body.appendChild(themeNotification);
        
        // Mostrar y ocultar la notificación
        setTimeout(() => {
            themeNotification.style.opacity = '1';
        }, 100);
        
        setTimeout(() => {
            themeNotification.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(themeNotification);
            }, 300);
        }, 2000);
    }

    // Función para alternar entre temas
    function toggleTheme() {
        const currentTheme = localStorage.getItem('theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
    }

    // Detectar preferencia del sistema de manera más robusta
    function detectSystemTheme() {
        try {
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                return 'dark';
            }
            return 'light';
        } catch (error) {
            console.error('Error al detectar tema del sistema:', error);
            return 'light'; // Valor predeterminado en caso de error
        }
    }

    // Inicializar tema basado en preferencia guardada o sistema
    function initTheme() {
        const savedTheme = localStorage.getItem('theme');
        const theme = savedTheme || detectSystemTheme();
        setTheme(theme);

        // Escuchar cambios en la preferencia del sistema
        try {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            
            // Usar el método moderno addEventListener si está disponible
            if (mediaQuery.addEventListener) {
                mediaQuery.addEventListener('change', e => {
                    if (!localStorage.getItem('theme')) {
                        setTheme(e.matches ? 'dark' : 'light');
                        console.log('Tema del sistema cambiado a:', e.matches ? 'oscuro' : 'claro');
                    }
                });
            } else if (mediaQuery.addListener) {
                // Fallback para navegadores más antiguos
                mediaQuery.addListener(e => {
                    if (!localStorage.getItem('theme')) {
                        setTheme(e.matches ? 'dark' : 'light');
                        console.log('Tema del sistema cambiado a:', e.matches ? 'oscuro' : 'claro');
                    }
                });
            }
            
            // Mostrar en consola el tema actual del sistema
            console.log('Tema del sistema actual:', detectSystemTheme());
            console.log('Tema aplicado:', theme, savedTheme ? '(preferencia guardada)' : '(basado en sistema)');
            
        } catch (error) {
            console.error('Error al configurar detector de tema del sistema:', error);
        }
    }

    // Crear y añadir el botón de cambio de tema si no existe
    function createThemeToggle() {
        // Verificar si el botón ya existe
        const existingToggle = document.getElementById('theme-toggle');
        if (existingToggle) {
            // Añadir evento de clic al botón existente
            existingToggle.addEventListener('click', toggleTheme);
            return;
        }

        // Crear el botón
        const themeToggle = document.createElement('button');
        themeToggle.id = 'theme-toggle';
        themeToggle.className = 'theme-toggle action-button';
        
        // Determinar el tema actual para el título del botón
        const currentTheme = localStorage.getItem('theme') || detectSystemTheme();
        themeToggle.setAttribute('title', currentTheme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
        
        // Crear el icono
        const themeIcon = document.createElement('i');
        themeIcon.id = 'theme-icon';
        themeIcon.className = currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        
        // Añadir el icono al botón
        themeToggle.appendChild(themeIcon);
        
        // Añadir evento de clic
        themeToggle.addEventListener('click', toggleTheme);

        // Determinar dónde insertar el botón
        const headerActions = document.querySelector('.header-actions');
        if (headerActions) {
            // Insertar en la página principal antes del botón de reset
            const resetButton = document.getElementById('reset-chat');
            if (resetButton) {
                headerActions.insertBefore(themeToggle, resetButton);
            } else {
                headerActions.appendChild(themeToggle);
            }
        } else {
            // Para páginas de autenticación, añadir en otro lugar
            const authBox = document.querySelector('.auth-box');
            if (authBox) {
                const authHeader = authBox.querySelector('.auth-header');
                if (authHeader) {
                    themeToggle.style.position = 'absolute';
                    themeToggle.style.top = '20px';
                    themeToggle.style.right = '20px';
                    authHeader.style.position = 'relative';
                    authHeader.appendChild(themeToggle);
                }
            }
        }

        // Añadir un indicador de tema del sistema si corresponde
        if (!localStorage.getItem('theme')) {
            const systemThemeIndicator = document.createElement('span');
            systemThemeIndicator.id = 'system-theme-indicator';
            systemThemeIndicator.className = 'system-theme-indicator';
            systemThemeIndicator.textContent = 'Auto';
            systemThemeIndicator.style.fontSize = '0.6rem';
            systemThemeIndicator.style.position = 'absolute';
            systemThemeIndicator.style.bottom = '-12px';
            systemThemeIndicator.style.left = '50%';
            systemThemeIndicator.style.transform = 'translateX(-50%)';
            systemThemeIndicator.style.color = 'var(--text-secondary)';
            themeToggle.appendChild(systemThemeIndicator);
        }

        // Actualizar el icono según el tema actual
        updateThemeIcon(currentTheme);
    }

    // Inicializar
    initTheme();
    createThemeToggle();
});