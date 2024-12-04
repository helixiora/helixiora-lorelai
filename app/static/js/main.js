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

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Add this new utility function for handling API requests with token refresh
async function makeAuthenticatedRequest(url, options = {}) {
    // Ensure headers exist
    options.headers = options.headers || {};

    // Add default headers
    options.headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
        ...options.headers
    };

    try {
        // Make initial request
        let response = await fetch(url, options);

        // Check if token is expired
        if (response.status === 401) {
            const responseData = await response.json();

            if (responseData.msg?.startsWith("Expired token")) {
                // Try to refresh the token
                const refreshResponse = await fetch('/api/v1/token/refresh', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                });

                if (refreshResponse.ok) {
                    // Retry the original request after token refresh
                    response = await fetch(url, options);
                } else {
                    throw new Error('Token refresh failed');
                }
            } else {
                throw new Error('Unauthorized');
            }
        }

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response;
    } catch (error) {
        console.error('Request failed:', error);
        throw error;
    }
}
