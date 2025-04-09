document.addEventListener('DOMContentLoaded', function() {
    // Get the modal element
    const modal = document.getElementById('guest-modal');
    
    // Get the button that opens the modal
    const btn = document.getElementById('guest-login-btn');
    
    // Get the <span> element that closes the modal
    const span = document.querySelector('.close');
    
    // When the user clicks the button, open the modal
    if (btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            modal.style.display = 'block';
        });
    }
    
    // When the user clicks on <span> (x), close the modal
    if (span) {
        span.addEventListener('click', function() {
            modal.style.display = 'none';
        });
    }
    
    // When the user clicks anywhere outside of the modal, close it
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
});