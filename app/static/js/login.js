document.addEventListener('DOMContentLoaded', async function() {
    const g_id_signin = document.getElementById('g_id_signin');
    if (!g_id_signin) {
        return; // Not on the login page, skip initialization
    }

    try {
        // Just render the button, let data attributes handle the rest
        google.accounts.id.renderButton(
            g_id_signin,
            { theme: 'outline', size: 'large' }
        );

        // Also display the One Tap dialog
        google.accounts.id.prompt();
    } catch (error) {
        console.error('Error initializing Google Sign-In:', error);
    }
});
