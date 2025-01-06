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
 * Refreshes the JWT access token using the refresh token
 * @returns {Promise<string>} - The new access token
 */
async function refreshToken() {
    if (!tokenRefreshPromise) {
        tokenRefreshPromise = (async () => {
            const storedRefreshToken = localStorage.getItem('lorelai_jwt_refresh_token');
            if (!storedRefreshToken) {
                throw new Error('No refresh token available');
            }

            const refreshResponse = await fetch('/api/v1/token/refresh', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${storedRefreshToken}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!refreshResponse.ok) {
                throw new Error('Token refresh failed');
            }

            const data = await refreshResponse.json();
            localStorage.setItem('lorelai_jwt_access_token', data.access_token);
            localStorage.setItem('lorelai_jwt_refresh_token', data.refresh_token);
            tokenRefreshPromise = null;
            return data.access_token;
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
        const storedAccessToken = localStorage.getItem('lorelai_jwt_access_token');
        if (storedAccessToken) {
            
            // Check if token is expired before using it
            if (isTokenExpired(storedAccessToken)) {
                try {
                    const newToken = await refreshToken();
                    return newToken;
                } catch (error) {
                    console.error('[Auth Request] Token refresh failed:', error);
                    throw error;
                }
            }
            
            return storedAccessToken;
        }
        if (retries >= MAX_RETRIES) {
            console.error('[Auth Request] No access token after max retries');
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

        try {
            const response = await fetch(url, {
                method: method,
                headers: headers,
                ...(body && { body: JSON.stringify(body) })
            });

            // Log response details for debugging

            return response;
        } catch (error) {
            // Ignore certificate errors and other network-related issues if the request actually succeeded
            if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                console.log('[Auth Request] Ignoring certificate/network warning, checking response');
                return error;
            }
            throw error;
        }
    };

    try {
        let token = await waitForTokens();
        let response = await makeRequest(token);

        // If we got a TypeError but the request might have succeeded, try to proceed
        if (response instanceof Error) {
            return response;
        }

        if (response.status === 401) {
            console.log('[Auth Request] Got 401, attempting token refresh');
            try {
                token = await refreshToken();
                response = await makeRequest(token);
                
                if (response.status === 401) {
                    console.error('[Auth Request] Still getting 401 after refresh');
                    localStorage.removeItem('lorelai_jwt_access_token');
                    localStorage.removeItem('lorelai_jwt_refresh_token');
                    throw new Error('Authentication failed after token refresh');
                }
            } catch (refreshError) {
                console.error('[Auth Request] Token refresh failed:', refreshError);
                localStorage.removeItem('lorelai_jwt_access_token');
                localStorage.removeItem('lorelai_jwt_refresh_token');
                throw refreshError;
            }
        }

        // Only throw if we actually got an error status
        if (!response.ok && response.status !== 404) {
            console.error('[Auth Request] Request failed with status:', response.status);
            throw new Error(`Request failed with status ${response.status}`);
        }

        return response;
    } catch (error) {
        // Only log and rethrow if it's a real error, not just a failed fetch
        if (error.name !== 'TypeError' || !error.message.includes('Failed to fetch')) {
            console.error('[Auth Request] Request failed:', error);
            throw error;
        }
        return error;
    }
}

/**
 * Checks the validity of the access token and refreshes it if expired.
 * @returns {Promise<boolean>} - Returns true if token is valid or was refreshed successfully
 */
async function checkAndRefreshToken() {
    const currentAccessToken = localStorage.getItem('lorelai_jwt_access_token');
    if (!currentAccessToken) {
        console.warn('No access token found.');
        return false;
    }

    try {
        // Decode the token to check its expiration
        const tokenPayload = JSON.parse(atob(currentAccessToken.split('.')[1]));
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
