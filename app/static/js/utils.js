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
                const csrf_token = getCookie('csrf_refresh_token');
                const headers = {
                    'Content-Type': 'application/json',
                };
                if (csrf_token) {
                    headers['X-CSRF-TOKEN'] = csrf_token;
                }

                const refreshResponse = await fetch('/api/v1/token/refresh', {
                    method: 'POST',
                    headers: headers,
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
                resetSession(); // Redirect to login if refresh fails
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
            console.log('Token expired, attempting refresh...');
            const refreshSuccess = await refreshToken();
            if (refreshSuccess) {
                console.log('Token refresh successful, retrying request...');
                // Get new CSRF token after refresh for non-GET requests
                if (method !== 'GET') {
                    const csrf_token = getCookie('csrf_access_token');
                    if (csrf_token) {
                        options.headers['X-CSRF-TOKEN'] = csrf_token;
                    }
                }
                // Retry the original request
                response = await fetch(url, options);
            } else {
                console.log('Token refresh failed, redirecting to login...');
                resetSession();
                throw new Error('Authentication failed - please log in again');
            }
        }

        if (!response.ok) {
            const errorData = await response.text();
            let errorMessage;
            try {
                const jsonError = JSON.parse(errorData);
                errorMessage = jsonError.message || jsonError.error || `Server error (${response.status})`;
            } catch (e) {
                errorMessage = errorData || `Request failed with status: ${response.status}`;
            }

            // Handle 500 errors with user-friendly message
            if (response.status === 500) {
                console.error('Server error details:', errorMessage);

                // Show user-friendly error toast/notification
                showErrorNotification(
                    'System Error',
                    'Sorry, something went wrong on our end. Please try again later. If the problem persists, please contact support.'
                );

                // Optional: Report to error tracking service
                if (window.Sentry) {
                    Sentry.captureException(new Error(`500 Error: ${errorMessage}`));
                }

                // Reset session if it's an authentication-related 500
                if (errorMessage.toLowerCase().includes('auth') ||
                    errorMessage.toLowerCase().includes('token') ||
                    errorMessage.toLowerCase().includes('session')) {
                    console.log('Authentication-related server error, redirecting to login...');
                    resetSession();
                }
            }

            throw new Error(errorMessage);
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

/**
 * Initialize a DataTable with common settings
 * @param {string} selector - The table selector
 * @param {Object} options - Additional DataTable options
 * @returns {DataTable} The initialized DataTable instance
 */
function initializeDataTable(selector, options = {}) {
    const defaultOptions = {
        order: [[0, 'desc']],
        pageLength: 25,
        columnDefs: [
            {
                targets: 'no-sort',
                orderable: false
            }
        ]
    };

    return $(selector).DataTable({
        ...defaultOptions,
        ...options
    });
}

/**
 * Animate a table row update
 * @param {jQuery} $row - The jQuery row element
 * @param {string} action - The action type ('read', 'dismiss', etc.)
 * @param {DataTable} table - The DataTable instance
 */
function animateTableRow($row, action, table) {
    if (!$row || !$row.length) {
        console.warn('No row element provided for animation');
        return;
    }

    if (action === 'dismiss') {
        // First update the status badge if it exists
        const $badge = $row.find('.badge');
        if ($badge.length) {
            $badge.removeClass('bg-primary bg-success').addClass('bg-secondary').text('Dismissed');
        }

        // Then fade out the row and remove it from the DataTable
        $row.animate({ opacity: 0 }, 400, function() {
            try {
                if (table && typeof table.row === 'function') {
                    const rowData = table.row($row);
                    if (rowData) {
                        rowData.remove().draw(false);
                    }
                }
            } catch (error) {
                console.warn('Error removing row from DataTable:', error);
                $row.remove(); // Fallback to simple DOM removal
            }
        });
    } else if (action === 'read') {
        // Safely animate the transition from unread to read
        $row.find('.fw-bold').removeClass('fw-bold');

        const $badge = $row.find('.badge.bg-primary');
        if ($badge.length) {
            $badge.fadeOut(200, function() {
                $(this).removeClass('bg-primary').addClass('bg-success')
                    .text('Read').fadeIn(200);
            });
        }

        // Safely remove the "Mark Read" button with animation
        const $markReadBtn = $row.find('.mark-read');
        if ($markReadBtn.length) {
            $markReadBtn.fadeOut(400, function() {
                $(this).remove();
            });
        }
    }
}

/**
 * Update bulk action buttons state based on selection
 * @param {string} checkboxSelector - Selector for checkboxes
 * @param {string} buttonSelector - Selector for bulk action buttons
 */
function updateBulkActionButtons(checkboxSelector = '.notification-checkbox', buttonSelector = '[id$="Selected"]') {
    const selectedCount = $(checkboxSelector + ':checked').length;
    $(buttonSelector).prop('disabled', selectedCount === 0);
}

/**
 * Handle select/deselect all functionality
 * @param {string} mainCheckboxSelector - Selector for the "select all" checkbox
 * @param {string} itemCheckboxSelector - Selector for individual item checkboxes
 */
function setupSelectAllFunctionality(mainCheckboxSelector = '#selectAllCheckbox', itemCheckboxSelector = '.notification-checkbox') {
    $(mainCheckboxSelector).on('change', function() {
        const isChecked = $(this).prop('checked');
        $(itemCheckboxSelector + ':visible').prop('checked', isChecked);
        updateBulkActionButtons(itemCheckboxSelector);
    });

    $(document).on('change', itemCheckboxSelector, function() {
        updateBulkActionButtons(itemCheckboxSelector);
    });
}

/**
 * Apply filters to a DataTable
 * @param {DataTable} table - The DataTable instance
 * @param {Object} filters - Object containing filter configurations
 */
function applyDataTableFilters(table, filters) {
    // Clear existing search functions
    $.fn.dataTable.ext.search.pop();

    // Apply column filters
    Object.entries(filters.columns || {}).forEach(([column, value]) => {
        if (value) {
            table.column(column).search(value);
        }
    });

    // Apply date range filter if present
    const { startDate, endDate } = filters.dateRange || {};
    if (startDate || endDate) {
        $.fn.dataTable.ext.search.push(function(settings, data, dataIndex) {
            const date = new Date(data[filters.dateColumn || 1]); // Default to second column for dates
            const start = startDate ? new Date(startDate) : null;
            const end = endDate ? new Date(endDate + 'T23:59:59') : null;

            if (start && date < start) return false;
            if (end && date > end) return false;
            return true;
        });
    }

    table.draw();
}

// Helper function to show error notifications
function showErrorNotification(title, message) {
    // If using Toastify
    if (window.Toastify) {
        Toastify({
            text: `${title}\n${message}`,
            duration: 5000,
            close: true,
            gravity: "top",
            position: "right",
            style: {
                background: "var(--bs-danger)",
            }
        }).showToast();
    }
    // Fallback to alert if no notification library
    else {
        alert(`${title}\n\n${message}`);
    }
}
