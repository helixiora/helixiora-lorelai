// Initialize variables
let lastNotificationCount = 0;
let notificationsDropdown = null;
let logoContainer = null;
let fetchPromise = null;

const NotificationActions = {
    markAsRead: async function(notificationId) {
        try {
            const response = await makeAuthenticatedRequest(`/api/v1/notifications/${notificationId}/read`, 'POST');
            if (response.ok) {
                console.log('Notification marked as read:', notificationId);
                return await response.json();
            }
            throw new Error('Failed to mark notification as read');
        } catch (error) {
            console.error('Error marking notification as read:', error);
            throw error;
        }
    },

    markAllRead: async function() {
        try {
            const response = await makeAuthenticatedRequest('/api/v1/notifications/bulk/read', 'POST', {
                ids: document.querySelectorAll('.list-group-item').length > 0
                    ? Array.from(document.querySelectorAll('.list-group-item')).map(item => item.dataset.notificationId)
                    : []
            });
            if (response.ok) {
                console.log('All notifications marked as read');
                return await response.json();
            }
            throw new Error('Failed to mark all notifications as read');
        } catch (error) {
            console.error('Error marking all notifications as read:', error);
            throw error;
        }
    },

    dismiss: async function(notificationId) {
        try {
            const response = await makeAuthenticatedRequest(`/api/v1/notifications/${notificationId}/dismiss`, 'POST');
            if (response.ok) {
                console.log('Notification dismissed:', notificationId);
                return await response.json();
            }
            throw new Error('Failed to dismiss notification');
        } catch (error) {
            console.error('Error dismissing notification:', error);
            throw error;
        }
    },

    updateBadgeCount: function(count) {
        console.log('Updating badge count:', {
            newCount: count,
            lastCount: lastNotificationCount
        });

        const logoContainer = document.getElementById('logoContainer');
        if (!logoContainer) {
            console.warn('Logo container not found for badge update');
            return;
        }

        let badge = logoContainer.querySelector('.notification-badge');
        const shouldPulse = count > lastNotificationCount;

        if (count <= 0) {
            if (badge) {
                console.log('Removing badge as count is zero');
                badge.remove();
            }
            lastNotificationCount = 0;
            return;
        }

        if (!badge) {
            console.log('Creating new badge element');
            badge = document.createElement('span');
            badge.className = 'notification-badge';
            logoContainer.appendChild(badge);
        }

        console.log(`Badge count changing from ${lastNotificationCount} to ${count}`);
        badge.textContent = count;
        badge.setAttribute('aria-label', `${count} unread notifications`);

        // Add pulse animation if count increased
        if (shouldPulse) {
            badge.classList.add('badge-pulse');
            setTimeout(() => badge.classList.remove('badge-pulse'), 1000);
        }

        lastNotificationCount = count;
    }
};

// Function to fetch notifications
async function fetchNotifications() {
    // If there's an ongoing fetch, return that promise
    if (fetchPromise) {
        console.log('Fetch already in progress, returning existing promise');
        return fetchPromise;
    }

    console.log('Starting fetchNotifications...');

    try {
        console.log('Making API request to /api/v1/notifications');
        fetchPromise = makeAuthenticatedRequest('/api/v1/notifications?include_counts=true', 'GET');
        const response = await fetchPromise;

        // Parse the response body as JSON
        const data = await response.json();
        console.log('Received notifications data:', {
            total: data.notifications?.length,
            notifications: data.notifications?.slice(0, 2), // Show first 2 for brevity
            hasMore: data.notifications?.length > 2 ? '...' : ''
        });

        if (!data || !data.notifications) {
            console.error('Invalid response data:', data);
            return;
        }

        // For the badge: unread and not dismissed notifications
        const unreadActiveCount = data.notifications.filter(n => !n.read && !n.dismissed).length;

        // For the popover: all not dismissed notifications, sorted by date
        const activeNotifications = data.notifications
            .filter(n => !n.dismissed)
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        console.log('Notification counts:', {
            total: data.notifications.length,
            activeTotal: activeNotifications.length,
            unreadActive: unreadActiveCount
        });

        // Update badge count with unread active notifications
        console.log('Updating badge count to:', unreadActiveCount);
        NotificationActions.updateBadgeCount(unreadActiveCount);

        // Update notification list with all active notifications
        console.log('Updating notification list with active notifications');
        updateNotificationList(activeNotifications);

    } catch (error) {
        console.error('Error in fetchNotifications:', error);
        handleFetchError();
    } finally {
        fetchPromise = null;
    }
}

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize logo container
    logoContainer = document.getElementById('logoContainer');
    if (!logoContainer) {
        console.warn('Logo container not found');
        return;
    }

    // Create and set up the dropdown structure
    setupNotificationsDropdown();

    // Fetch notifications immediately for initial badge count
    fetchNotifications();

    // Set up periodic refresh every 30 seconds
    setInterval(fetchNotifications, 30000);
});

function setupNotificationsDropdown() {
    // Remove any existing dropdown menu
    const existingDropdown = document.querySelector('.dropdown-menu');
    if (existingDropdown) {
        existingDropdown.remove();
    }

    // Create dropdown menu
    const dropdownMenu = document.createElement('div');
    dropdownMenu.className = 'dropdown-menu dropdown-menu-end shadow';
    dropdownMenu.style.cssText = `
        width: 400px;
        background-color: white;
        z-index: 1050;
        opacity: 1 !important;
        animation: none;
    `;
    dropdownMenu.setAttribute('aria-labelledby', 'logoContainer');

    // Create card structure
    dropdownMenu.innerHTML = `
        <div class="card border-0" style="height: 100%; background-color: white;">
            <div class="card-header d-flex justify-content-between align-items-center bg-light py-2" style="background-color: #f8f9fa !important;">
                <h6 class="mb-0">Notifications</h6>
                <div class="btn-group btn-group-sm">
                    <button type="button" class="btn btn-outline-success" id="markAllRead" data-bs-toggle="tooltip" title="Mark all as read">
                        <i class="bi bi-check2-all"></i>
                    </button>
                    <a href="/notifications" class="btn btn-outline-primary" aria-label="View all notifications">
                        View All
                    </a>
                </div>
            </div>
            <div class="card-body p-0" style="height: 400px; overflow-y: auto; background-color: white;">
                <!-- Notifications will be inserted here -->
            </div>
        </div>
    `;

    // Add dropdown menu to logo container
    logoContainer.appendChild(dropdownMenu);

    // Initialize Bootstrap dropdown
    if (notificationsDropdown) {
        notificationsDropdown.dispose();
    }
    notificationsDropdown = new bootstrap.Dropdown(logoContainer, {
        autoClose: 'outside'
    });

    // Store the dropdown instance
    logoContainer._dropdown = notificationsDropdown;

    // Add event listeners
    logoContainer.addEventListener('show.bs.dropdown', () => {
        console.log('Dropdown opening, fetching notifications...');
        fetchNotifications();
    });

    // Ensure dropdown stays opaque
    logoContainer.addEventListener('shown.bs.dropdown', () => {
        dropdownMenu.style.opacity = '1';
        dropdownMenu.style.backgroundColor = 'white';
    });

    // Set up mark all read button
    const markAllReadBtn = dropdownMenu.querySelector('#markAllRead');
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', async () => {
            try {
                await NotificationActions.markAllRead();
                fetchNotifications();
            } catch (error) {
                console.error('Failed to mark all notifications as read:', error);
            }
        });
    }
}

function updateNotificationList(notifications) {
    console.log('Updating notification list with:', notifications?.length, 'notifications');

    const cardBody = document.querySelector('.dropdown-menu .card-body');
    if (!cardBody) {
        console.error('Card body not found');
        return;
    }

    if (!notifications || notifications.length === 0) {
        cardBody.innerHTML = `
            <div class="text-center py-4">
                <p class="text-muted mb-0">No notifications to display</p>
            </div>
        `;
        return;
    }

    // Create notifications list
    const notificationsList = document.createElement('div');
    notificationsList.className = 'list-group list-group-flush';
    notificationsList.style.height = '100%';

    notifications.forEach((notification, index) => {
        const notificationItem = document.createElement('div');
        notificationItem.className = 'list-group-item border-bottom';
        notificationItem.dataset.notificationId = notification.id;

        notificationItem.innerHTML = `
            <div class="d-flex flex-column gap-2">
                <div class="d-flex justify-content-between align-items-start">
                    <h6 class="mb-0 ${!notification.read ? 'fw-bold' : ''}">${notification.title}</h6>
                    <small class="text-muted">${new Date(notification.created_at).toLocaleString()}</small>
                </div>
                <p class="mb-2 ${!notification.read ? 'fw-bold' : ''}">${notification.message}</p>
                ${notification.data ? `
                    <div class="small text-muted mb-2">
                        ${Object.entries(notification.data).map(([key, value]) =>
                            `<div><strong>${key}:</strong> ${value}</div>`
                        ).join('')}
                    </div>
                ` : ''}
                <div class="d-flex gap-2">
                    ${!notification.read ? `
                        <button class="btn btn-sm btn-outline-success mark-read"
                                data-notification-id="${notification.id}"
                                data-bs-toggle="tooltip"
                                title="Mark as read">
                            <i class="bi bi-check2"></i>
                            <span>Mark Read</span>
                        </button>
                    ` : ''}
                    <button class="btn btn-sm btn-outline-secondary dismiss-notification"
                            data-notification-id="${notification.id}"
                            data-bs-toggle="tooltip"
                            title="Dismiss">
                        <i class="bi bi-x"></i>
                        <span>Dismiss</span>
                    </button>
                    ${notification.url ? `
                        <a href="${notification.url}"
                           class="btn btn-sm btn-outline-primary"
                           data-bs-toggle="tooltip"
                           title="View details">
                            <i class="bi bi-box-arrow-up-right"></i>
                            <span>View</span>
                        </a>
                    ` : ''}
                </div>
            </div>
        `;

        notificationsList.appendChild(notificationItem);
    });

    // Clear and update card body
    cardBody.innerHTML = '';
    cardBody.appendChild(notificationsList);

    // Set up action handlers
    setupNotificationActions();
}

// Function to handle fetch errors
function handleFetchError() {
    const cardBody = document.querySelector('.dropdown-menu .card-body');
    if (cardBody) {
        cardBody.innerHTML = `
            <div class="text-center py-4" role="alert">
                <i class="bi bi-exclamation-circle text-danger" style="font-size: 2rem;" aria-hidden="true"></i>
                <p class="mb-0 mt-2">Failed to load notifications</p>
            </div>
        `;
    }
}

// Function to set up notification action handlers
function setupNotificationActions() {
    // Handle mark as read
    document.querySelectorAll('.mark-read').forEach(button => {
        button.addEventListener('click', async (e) => {
            const notificationId = e.currentTarget.dataset.notificationId;
            try {
                await NotificationActions.markAsRead(notificationId);
                // Handle list item
                const listItem = e.currentTarget.closest('.list-group-item');
                if (listItem) {
                    const title = listItem.querySelector('h6');
                    const message = listItem.querySelector('p');
                    if (title) title.classList.remove('fw-bold');
                    if (message) message.classList.remove('fw-bold');
                    e.currentTarget.remove();
                }
                // Fetch notifications to update counts and UI
                fetchNotifications();
            } catch (error) {
                console.error('Failed to mark notification as read:', error);
            }
        });
    });

    // Handle dismiss
    document.querySelectorAll('.dismiss-notification').forEach(button => {
        button.addEventListener('click', async (e) => {
            const notificationId = e.currentTarget.dataset.notificationId;
            try {
                await NotificationActions.dismiss(notificationId);
                // Handle list item
                const listItem = e.currentTarget.closest('.list-group-item');
                if (listItem) {
                    if (document.querySelectorAll('.list-group-item').length === 1) {
                        fetchNotifications();
                    } else {
                        listItem.remove();
                    }
                }
            } catch (error) {
                console.error('Failed to dismiss notification:', error);
            }
        });
    });
}

// Export NotificationActions for use in other files
window.NotificationActions = NotificationActions;

// Listen for token expiration events
window.addEventListener('tokenExpired', function(event) {
    const message = event.detail.message;

    // Create or update the expiration notice
    let notice = document.getElementById('token-expiration-notice');
    if (!notice) {
        notice = document.createElement('div');
        notice.id = 'token-expiration-notice';
        notice.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            z-index: 9999;
            max-width: 400px;
        `;
        document.body.appendChild(notice);
    }

    notice.innerHTML = `
        <div style="margin-bottom: 10px;">${message}</div>
        <button onclick="resetSession()" style="
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
        ">Return to Login</button>
    `;

    // Clear any existing notification fetch intervals
    if (fetchInterval) {
        clearInterval(fetchInterval);
    }
});
