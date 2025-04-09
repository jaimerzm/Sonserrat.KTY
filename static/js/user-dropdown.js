document.addEventListener('DOMContentLoaded', () => {
    const userInfoTrigger = document.getElementById('user-info-trigger');
    const userDropdown = document.getElementById('user-dropdown');

    if (!userInfoTrigger || !userDropdown) {
        console.error('User dropdown elements not found');
        return;
    }

    // Toggle dropdown when clicking on user info
    userInfoTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        userDropdown.classList.toggle('active');
        
        // Apply animation
        if (userDropdown.classList.contains('active')) {
            userDropdown.style.display = 'block';
        } else {
            setTimeout(() => {
                userDropdown.style.display = 'none';
            }, 200); // Match this with the CSS animation duration
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!userDropdown.contains(e.target) && !userInfoTrigger.contains(e.target)) {
            userDropdown.classList.remove('active');
            setTimeout(() => {
                userDropdown.style.display = 'none';
            }, 200);
        }
    });

    // Handle logout
    const logoutOption = document.querySelector('.logout-option');
    if (logoutOption) {
        logoutOption.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Logout clicked');
            
            // Show a brief feedback before redirecting
            const logoutText = logoutOption.querySelector('span');
            const originalText = logoutText.textContent;
            logoutText.textContent = 'Cerrando sesión...';
            
            setTimeout(() => {
                window.location.href = '/logout';
            }, 500);
        });
    } else {
        console.error('Logout option not found');
    }
});