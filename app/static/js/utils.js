getCookie = function(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

// Token refresh queue to prevent multiple simultaneous refreshes
let tokenRefreshPromise = null;

/**
 * Handles a complete session reset by clearing cookies and redirecting to login
 */
function resetSession() {
    window.location.href = '/logout';
}

/**
 * Refreshes the JWT access token using the refresh token
 * @returns {Promise<boolean>} - True if refresh was successful
 */
async function refreshToken() {
    if (!tokenRefreshPromise) {
        tokenRefreshPromise = (async () => {
            try {
                const refreshResponse = await fetch('/api/v1/token/refresh', {
                    method: 'POST',
                    credentials: 'include', // Important: needed to include cookies
                });

                if (!refreshResponse.ok) {
                    throw new Error('Token refresh failed');
                }

                const data = await refreshResponse.json();
                if (data.status === 'success') {
                    tokenRefreshPromise = null;
                    return true;
                } else {
                    console.error('[Token Refresh]', data.message);
                    throw new Error(data.message || 'Token refresh failed');
                }
            } catch (error) {
                console.error('[Token Refresh] Error:', error);
                tokenRefreshPromise = null;
                return false;
            }
        })();
    }
    return tokenRefreshPromise;
}

/**
 * Checks if a JWT token is expired
 * @param {string} token - The JWT token to check
 * @returns {boolean} - True if token is expired
 */
function isTokenExpired(token) {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const currentTime = Math.floor(Date.now() / 1000); // Convert to seconds to match server
        const isExpired = currentTime >= payload.exp;

        return isExpired;
    } catch (error) {
        console.error('[Token Check] Error checking token expiration:', error);
        return true; // Assume expired if we can't check
    }
}

/**
 * Makes an authenticated request to the API
 * @param {string} url - The URL to make the request to
 * @param {string} method - The HTTP method to use
 * @param {object} [body] - Optional body for POST/PUT requests
 * @returns {Promise<Response>} - The fetch response
 * @throws {Error} - With status code if request fails
 */
async function makeAuthenticatedRequest(url, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
    };

    // Add CSRF token for non-GET requests
    if (method !== 'GET') {
        const csrf_token = getCookie('csrf_access_token');
        if (csrf_token) {
            headers['X-CSRF-TOKEN'] = csrf_token;
        }
    }

    const options = {
        method,
        headers,
        credentials: 'include', // Important: needed to include cookies
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    try {
        let response = await fetch(url, options);

        // If we get a 401, try to refresh the token once
        if (response.status === 401) {
            const refreshSuccess = await refreshToken();
            if (refreshSuccess) {
                // Get new CSRF token after refresh for non-GET requests
                if (method !== 'GET') {
                    const csrf_token = getCookie('csrf_access_token');
                    if (csrf_token) {
                        options.headers['X-CSRF-TOKEN'] = csrf_token;
                    }
                }
                // Retry the original request
                response = await fetch(url, options);
                if (!response.ok) {
                    throw new Error(`Request failed after token refresh: ${response.status}`);
                }
                return response;
            }
            // If refresh failed, throw error with status
            throw new Error('401');
        }

        if (!response.ok) {
            throw new Error(`${response.status}`);
        }

        return response;
    } catch (error) {
        console.error('Request failed:', error);
        throw error;
    }
}

/**
 * Checks if we need to refresh the token
 * @returns {Promise<boolean>} - Returns true if token is valid or was refreshed successfully
 */
async function checkAndRefreshToken() {
    try {
        const response = await fetch('/api/v1/token/check', {
            credentials: 'include',
        });

        if (response.status === 401) {
            console.log('Token expired. Attempting to refresh...');
            return await refreshToken();
        }
        return true;
    } catch (error) {
        console.error('Error checking token:', error);
        return false;
    }
}
