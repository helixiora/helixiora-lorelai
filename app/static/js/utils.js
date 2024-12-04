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
            // Clone the response before reading it
            const responseClone = response.clone();
            const responseData = await responseClone.json();

            console.log('Auth error response:', responseData);

            if (responseData.msg && responseData.msg.startsWith("Expired token")) {
                console.log('Token expired, attempting refresh...');

                // Token expired, try to refresh
                const refreshToken = localStorage.getItem('lorelai_jwt_refresh_token');
                if (!refreshToken) {
                    throw new Error('No refresh token available');
                }

                const refreshResponse = await fetch('/api/v1/token/refresh', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${refreshToken}`
                    }
                });

                if (refreshResponse.ok) {
                    const newTokens = await refreshResponse.json();
                    console.log('Token refresh successful');

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
                    console.error('Token refresh failed:', await refreshResponse.text());
                    throw new Error('Token refresh failed');
                }
            } else {
                throw new Error(responseData.msg || 'Unauthorized');
            }
        }

        return response;

    } catch (error) {
        console.error('Request error:', error);
        throw error;
    }
}

/**
 * Checks the validity of the access token and refreshes it if expired.
 */
async function checkAndRefreshToken() {
    const accessToken = localStorage.getItem('lorelai_jwt_access_token');
    if (!accessToken) {
        console.warn('No access token found. User might not be logged in.');
        return;
    }

    // Decode the token to check its expiration
    const tokenPayload = JSON.parse(atob(accessToken.split('.')[1]));
    const isExpired = tokenPayload.exp * 1000 < Date.now();

    if (isExpired) {
        console.log('Access token expired. Attempting to refresh...');
        const refreshResponse = await fetch('/api/v1/token/refresh', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('lorelai_jwt_refresh_token')}`
            }
        });

        if (refreshResponse.ok) {
            const newTokens = await refreshResponse.json();
            localStorage.setItem('lorelai_jwt_access_token', newTokens.access_token);
            console.log('Access token refreshed successfully.');
        } else {
            console.error('Failed to refresh access token.');
        }
    } else {
        console.log('Access token is still valid.');
    }
}
