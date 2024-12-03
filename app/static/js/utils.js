getCookie = function(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

/**
 * Makes an authenticated request with automatic token refresh handling
 * @param {string} url - The URL to make the request to
 * @param {string} method - The HTTP method to use
 * @param {Object} [body] - Optional request body
 * @param {Object} [additionalHeaders] - Optional additional headers
 * @returns {Promise<Response>} - The fetch response
 */
async function makeAuthenticatedRequest(url, method, body = null, additionalHeaders = {}) {
    try {
        // Check if we have an access token
        const accessToken = localStorage.getItem('lorelai_jwt_access_token');
        if (!accessToken) {
            throw new Error('You are not logged in. Please log in to continue.');
        }

        // Prepare headers
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`,
            ...additionalHeaders
        };

        // Make the request
        let response = await fetch(url, {
            method: method,
            headers: headers,
            ...(body && { body: JSON.stringify(body) })
        });

        // Handle 401 (Unauthorized)
        if (response.status === 401) {
            const responseData = await response.json();
            if (responseData.msg.startsWith("Expired token")) {
                // Token expired, try to refresh
                const refreshResponse = await fetch('/api/v1/token/refresh', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('lorelai_jwt_refresh_token')}`
                    }
                });

                if (refreshResponse.ok) {
                    const newTokens = await refreshResponse.json();
                    // Update stored tokens
                    localStorage.setItem('lorelai_jwt_access_token', newTokens.access_token);

                    // Retry original request with new token
                    response = await fetch(url, {
                        method: method,
                        headers: {
                            ...headers,
                            'Authorization': `Bearer ${newTokens.access_token}`
                        },
                        ...(body && { body: JSON.stringify(body) })
                    });
                } else {
                    throw new Error('Token refresh failed');
                }
            }
        }

        return response;

    } catch (error) {
        console.error('Request error:', error);
        throw error;
    }
}
