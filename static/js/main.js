document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Responsive navbar collapse
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');

    if (navbarToggler && navbarCollapse) {
        navbarToggler.addEventListener('click', function() {
            navbarCollapse.classList.toggle('show');
        });
    }

    // Form validation for the sign-up button
    const signUpButton = document.querySelector('.cta .btn');
    if (signUpButton) {
        signUpButton.addEventListener('click', function(e) {
            e.preventDefault();
            alert('Sign up functionality coming soon!');
        });
    }

    // Lazy loading for images
    if ('loading' in HTMLImageElement.prototype) {
        const images = document.querySelectorAll('img[loading="lazy"]');
        images.forEach(img => {
            img.src = img.dataset.src;
        });
    } else {
        // Fallback for browsers that don't support lazy loading
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/lazysizes/5.3.2/lazysizes.min.js';
        document.body.appendChild(script);
    }

    // Check if Google Sign-In is available
    if (typeof google !== 'undefined' && google.accounts && google.accounts.id) {
        google.accounts.id.prompt();
        google.accounts.id.renderButton(
            document.getElementById('g_id_signin'),
            { theme: 'outline', size: 'large' }
        );
    }
});
