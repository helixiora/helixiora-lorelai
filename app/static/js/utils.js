getCookie = function(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

// Token refresh queue to prevent multiple simultaneous refreshes
let tokenRefreshPromise = null;

/**
 * Handles a complete session reset by clearing tokens and redirecting to login
 */
function resetSession() {
    // Clear all tokens
    localStorage.removeItem('lorelai_jwt_access_token');
    localStorage.removeItem('lorelai_jwt_refresh_token');

    // Redirect to home page which will show login if not authenticated
    window.location.href = '/logout';
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
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 500; // 500ms

    const waitForTokens = async (retries = 0) => {
        const accessToken = localStorage.getItem('lorelai_jwt_access_token');
        if (accessToken) {
            return accessToken;
        }
        if (retries >= MAX_RETRIES) {
            throw new Error('No access token available after retries');
        }
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
        return waitForTokens(retries + 1);
    };

    const makeRequest = async (token) => {
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...additionalHeaders
        };

        return fetch(url, {
            method: method,
            headers: headers,
            ...(body && { body: JSON.stringify(body) })
        });
    };

    const refreshToken = async () => {
        if (!tokenRefreshPromise) {
            tokenRefreshPromise = (async () => {
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

                if (!refreshResponse.ok) {
                    throw new Error('Failed to refresh token');
                }

                const newTokens = await refreshResponse.json();
                console.log('Token refresh successful');

                // Update stored tokens
                localStorage.setItem('lorelai_jwt_access_token', newTokens.access_token);
                if (newTokens.refresh_token) {
                    localStorage.setItem('lorelai_jwt_refresh_token', newTokens.refresh_token);
                }

                return newTokens.access_token;
            })();
        }

        try {
            const newToken = await tokenRefreshPromise;
            return newToken;
        } finally {
            tokenRefreshPromise = null;
        }
    };

    const handleTokenError = async () => {
        // Clear tokens but don't redirect
        localStorage.removeItem('lorelai_jwt_access_token');
        localStorage.removeItem('lorelai_jwt_refresh_token');

        // Dispatch an event that the UI can listen for to show a login prompt
        const event = new CustomEvent('tokenExpired', {
            detail: {
                message: 'Your session has expired. Please refresh the page to continue.'
            }
        });
        window.dispatchEvent(event);

        throw new Error('Session expired. Please refresh the page to continue.');
    };

    try {
        // Check if we have an access token, with retries
        let accessToken = await waitForTokens();
        if (!accessToken) {
            return handleTokenError();
        }

        // Make initial request
        let response = await makeRequest(accessToken);

        // Handle 401 (Unauthorized)
        if (response.status === 401) {
            let responseData;
            try {
                // Try to parse the response as JSON
                const responseClone = response.clone();
                responseData = await responseClone.json();
            } catch (parseError) {
                // If we can't parse the response, assume token is expired
                console.log('Could not parse 401 response, assuming token expired');
                responseData = { msg: "Token expired" };
            }

            if (responseData.msg && (
                responseData.msg.startsWith("Token expired") ||
                responseData.msg.startsWith("Expired token") ||
                responseData.msg === "Token has expired"
            )) {
                console.log('Token expired, attempting refresh...');
                try {
                    const newToken = await refreshToken();
                    // Retry the original request with new token
                    response = await makeRequest(newToken);

                    // If still unauthorized after refresh, then we have a real problem
                    if (response.status === 401) {
                        return handleTokenError();
                    }

                    return response;
                } catch (refreshError) {
                    console.error('Token refresh failed:', refreshError);
                    return handleTokenError();
                }
            } else {
                // For other unauthorized errors that aren't token related
                console.error('Non-token related auth error:', responseData.msg);
                return handleTokenError();
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
 * @returns {Promise<boolean>} - Returns true if token is valid or was refreshed successfully
 */
async function checkAndRefreshToken() {
    const accessToken = localStorage.getItem('lorelai_jwt_access_token');
    if (!accessToken) {
        console.warn('No access token found.');
        return false;
    }

    try {
        // Decode the token to check its expiration
        const tokenPayload = JSON.parse(atob(accessToken.split('.')[1]));
        const isExpired = tokenPayload.exp * 1000 < Date.now();

        if (isExpired) {
            console.log('Access token expired. Attempting to refresh...');
            try {
                await refreshToken();
                console.log('Access token refreshed successfully.');
                return true;
            } catch (error) {
                console.error('Failed to refresh access token:', error);
                return false;
            }
        }
        return true;
    } catch (error) {
        console.error('Error checking token:', error);
        return false;
    }
}
