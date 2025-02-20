// Initialize Stripe
let stripe;

async function waitForStripe(maxAttempts = 10, interval = 100) {
    for (let i = 0; i < maxAttempts; i++) {
        if (typeof window.Stripe !== 'undefined') {
            return true;
        }
        await new Promise(resolve => setTimeout(resolve, interval));
    }
    return false;
}

async function initializeStripe() {
    try {
        // Wait for Stripe to be available
        const stripeLoaded = await waitForStripe();
        if (!stripeLoaded) {
            throw new Error('Stripe.js not loaded');
        }

        const response = await makeAuthenticatedRequest('/api/v1/stripe/config', 'GET');
        const data = await response.json();

        if (!data.publishableKey) {
            throw new Error('No publishable key received from server');
        }

        stripe = window.Stripe(data.publishableKey);
        console.log('Stripe initialized successfully');
    } catch (error) {
        console.error('Error initializing Stripe:', error);
        // Show error to user
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = 'Failed to initialize payment system. Please try again later.';
        document.getElementById('profile-container').prepend(errorDiv);
    }
}

async function handlePayment(planId) {
    try {
        if (!stripe) {
            // Try to initialize if not already initialized
            await initializeStripe();
            if (!stripe) {
                throw new Error('Stripe not initialized');
            }
        }

        // Create checkout session
        const response = await makeAuthenticatedRequest('/api/v1/stripe/create-checkout-session', 'POST', {
            plan_id: planId
        });

        const session = await response.json();

        if (session.error) {
            throw new Error(session.error);
        }

        // Redirect to Stripe checkout
        const result = await stripe.redirectToCheckout({
            sessionId: session.sessionId,
        });

        if (result.error) {
            throw new Error(result.error.message);
        }
    } catch (error) {
        console.error('Error handling payment:', error);
        // Show error to user
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = 'An error occurred while processing your payment. Please try again.';
        document.getElementById('profile-container').prepend(errorDiv);
    }
}

// Initialize Stripe when the window is fully loaded
window.addEventListener('load', initializeStripe);
