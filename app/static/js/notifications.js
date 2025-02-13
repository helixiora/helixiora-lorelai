// Initialize variables
let lastNotificationCount = 0;
let notificationsPopover = null;
let logoContainer = null;
let fetchPromise = null;
let updateInterval = null;
let abortController = null;
let isUpdating = false;
let lastUpdateTime = 0;
const UPDATE_THROTTLE = 5000; // 5 seconds

const NotificationActions = {
    async markAsRead(notificationId) {
        try {
            const response = await makeAuthenticatedRequest(`/api/v1/notifications/${notificationId}/read`, 'POST');
            if (response.ok) {
                await response.json();
                // Don't trigger a new fetch, just update the UI
                const notificationElement = document.getElementById(`notification-${notificationId}`);
                if (notificationElement) {
                    const title = notificationElement.querySelector('.notification-title');
                    const message = notificationElement.querySelector('.notification-message');
                    const markReadBtn = notificationElement.querySelector('.mark-read-btn');

                    if (title) title.classList.remove('fw-bold');
                    if (message) message.classList.add('text-muted');
                    if (markReadBtn) markReadBtn.remove();
                }
                return true;
            }
            throw new Error('Failed to mark notification as read');
        } catch (error) {
            throw error;
        }
    },

    markAllRead: async function() {
        try {
            const notificationIds = Array.from(document.querySelectorAll('.notification-item'))
                .filter(item => item.querySelector('.mark-read-btn'))
                .map(item => item.dataset.notificationId)
                .filter(id => id);

            if (notificationIds.length === 0) {
                return;
            }

            const response = await makeAuthenticatedRequest('/api/v1/notifications/bulk/read', 'POST', {
                ids: notificationIds
            });

            if (response.ok) {
                await response.json();
                // Update UI directly instead of fetching
                notificationIds.forEach(id => {
                    const notificationElement = document.getElementById(`notification-${id}`);
                    if (notificationElement) {
                        const title = notificationElement.querySelector('.notification-title');
                        const message = notificationElement.querySelector('.notification-message');
                        const markReadBtn = notificationElement.querySelector('.mark-read-btn');

                        if (title) title.classList.remove('fw-bold');
                        if (message) message.classList.add('text-muted');
                        if (markReadBtn) markReadBtn.remove();
                    }
                });
                return true;
            }
            throw new Error('Failed to mark all notifications as read');
        } catch (error) {
            throw error;
        }
    },

    async dismiss(notificationId) {
        try {
            const response = await makeAuthenticatedRequest(`/api/v1/notifications/${notificationId}/dismiss`, 'POST');
            if (response.ok) {
                await response.json();
                // Remove the notification from UI instead of fetching
                const notificationElement = document.getElementById(`notification-${notificationId}`);
                if (notificationElement) {
                    notificationElement.remove();
                }
                return true;
            }
            throw new Error('Failed to dismiss notification');
        } catch (error) {
            throw error;
        }
    },

    async updateBadgeCount(count) {
        const logoContainer = document.getElementById('logoContainer');
        if (!logoContainer) {
            return;
        }

        let badge = logoContainer.querySelector('.notification-badge');
        const shouldPulse = count > lastNotificationCount;

        if (count <= 0) {
            if (badge) {
                badge.remove();
            }
            lastNotificationCount = 0;
            return;
        }

        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'notification-badge';
            logoContainer.appendChild(badge);
        }

        badge.textContent = count;
        badge.setAttribute('aria-label', `${count} unread notifications`);

        if (shouldPulse) {
            badge.classList.add('badge-pulse');
            setTimeout(() => badge.classList.remove('badge-pulse'), 1000);
        }

        lastNotificationCount = count;
    }
};

// Function to format timestamp
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) {
        return 'Just now';
    } else if (diffMins < 60) {
        return `${diffMins}m ago`;
    } else if (diffHours < 24) {
        return `${diffHours}h ago`;
    } else if (diffDays < 7) {
        return `${diffDays}d ago`;
    } else {
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${date.toLocaleDateString()} ${hours}:${minutes}`;
    }
}

// Function to create popover content
function createPopoverContent(notifications) {
    const content = document.createElement('div');
    content.className = 'notifications-content';

    const header = document.createElement('div');
    header.className = 'card-header';
    header.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <h6 class="mb-0">Notifications</h6>
            <div class="btn-group">
                <button type="button" class="btn" id="markAllAsRead">Mark all as read</button>
                <button type="button" class="btn" onclick="window.location.href='/notifications'">View all</button>
            </div>
        </div>
    `;

    const body = document.createElement('div');
    body.className = 'card-body';

    const list = document.createElement('div');
    list.className = 'list-group list-group-flush';
    list.id = 'notificationsList';

    if (!notifications || notifications.length === 0) {
        list.innerHTML = `
            <div class="list-group-item text-center text-muted">
                <p class="mb-0">No notifications</p>
            </div>
        `;
    } else {
        list.innerHTML = notifications.map(notification => `
            <div class="list-group-item" id="notification-${notification.id}" data-notification-id="${notification.id}">
                <div class="d-flex flex-column">
                    <div class="notification-title ${notification.read ? '' : 'fw-bold'}">${notification.title}</div>
                    <div class="notification-message ${notification.read ? 'text-muted' : ''}">${notification.message}</div>
                    <div class="notification-time">${formatTimestamp(notification.created_at)}</div>
                    <div class="notification-actions">
                        ${!notification.read ? `
                            <button type="button" class="btn mark-read-btn" id="markRead-${notification.id}">
                                Mark as read
                            </button>
                        ` : ''}
                        <button type="button" class="btn dismiss-btn" id="dismiss-${notification.id}">
                            Dismiss
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    body.appendChild(list);
    content.appendChild(header);
    content.appendChild(body);

    return content;
}

// Function to update notifications
async function updateNotifications(force = false) {
    const now = Date.now();
    // Prevent updates too close together unless forced
    if (!force && now - lastUpdateTime < UPDATE_THROTTLE) {
        return;
    }

    if (isUpdating && !force) {
        return;
    }

    isUpdating = true;
    lastUpdateTime = now;

    try {
        // If there's an ongoing fetch and it's not forced, return the existing promise
        if (fetchPromise && !force) {
            return fetchPromise;
        }

        // Cancel any ongoing fetch
        if (abortController) {
            abortController.abort();
        }

        // Create new abort controller
        abortController = new AbortController();

        fetchPromise = makeAuthenticatedRequest('/api/v1/notifications?include_counts=true');
        const response = await fetchPromise;
        const data = await response.json();

        if (!data || !data.notifications) {
            console.warn('No notifications data received');
            return;
        }

        const unreadActiveCount = data.notifications.filter(n => !n.read && !n.dismissed).length;
        const activeNotifications = data.notifications
            .filter(n => !n.dismissed)
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        NotificationActions.updateBadgeCount(unreadActiveCount);

        // Update content regardless of popover visibility
        if (notificationsPopover) {
            const content = createPopoverContent(activeNotifications);
            notificationsPopover.setContent({ '.popover-body': content });

            // If popover is visible, attach listeners
            const popoverElement = document.querySelector('.popover.notifications-popover.show');
            if (popoverElement) {
                attachNotificationListeners(activeNotifications);
            }
            return activeNotifications;
        }
    } catch (error) {
        console.error('Error updating notifications:', error);

        if (error.name === 'AbortError') {
            return; // Ignore aborted requests
        }

        // If the error message indicates authentication failure, let makeAuthenticatedRequest handle the redirect
        if (error.message.includes('Authentication failed') || error.message.includes('Token expired')) {
            return;
        }

        if (notificationsPopover) {
            const errorContent = document.createElement('div');
            errorContent.className = 'text-center text-danger';
            errorContent.innerHTML = `
                <i class="fas fa-exclamation-circle"></i>
                <p class="mb-0">Failed to load notifications</p>
                <small class="text-muted">${error.message}</small>
            `;
            notificationsPopover.setContent({ '.popover-body': errorContent });
        }
    } finally {
        fetchPromise = null;
        abortController = null;
        isUpdating = false;
    }
}

// Function to attach notification listeners (modified to prevent duplicates)
function attachNotificationListeners(notifications) {
    // Remove existing listeners first
    const existingButtons = document.querySelectorAll('.mark-read-btn, .dismiss-btn, #markAllAsRead');
    existingButtons.forEach(button => {
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
    });

    // Attach new listeners
    notifications.forEach(notification => {
        const markReadBtn = document.getElementById(`markRead-${notification.id}`);
        if (markReadBtn) {
            markReadBtn.addEventListener('click', async (event) => {
                event.stopPropagation();
                try {
                    await NotificationActions.markAsRead(notification.id);
                    // Update badge count
                    const unreadCount = document.querySelectorAll('.notification-title.fw-bold').length - 1;
                    NotificationActions.updateBadgeCount(unreadCount);
                } catch (error) {
                    // Error handling
                }
            });
        }

        const dismissBtn = document.getElementById(`dismiss-${notification.id}`);
        if (dismissBtn) {
            dismissBtn.addEventListener('click', async (event) => {
                event.stopPropagation();
                try {
                    await NotificationActions.dismiss(notification.id);
                    // Update badge count if needed
                    if (!notification.read) {
                        const unreadCount = document.querySelectorAll('.notification-title.fw-bold').length - 1;
                        NotificationActions.updateBadgeCount(unreadCount);
                    }
                } catch (error) {
                    // Error handling
                }
            });
        }
    });

    const markAllAsReadBtn = document.getElementById('markAllAsRead');
    if (markAllAsReadBtn) {
        markAllAsReadBtn.addEventListener('click', async (event) => {
            event.stopPropagation();
            try {
                await NotificationActions.markAllRead();
                // Update badge count
                NotificationActions.updateBadgeCount(0);
            } catch (error) {
                // Error handling
            }
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    logoContainer = document.getElementById('logoContainer');
    if (!logoContainer) {
        return;
    }

    // Cleanup any existing popover and interval
    if (notificationsPopover) {
        notificationsPopover.dispose();
    }
    if (updateInterval) {
        clearInterval(updateInterval);
    }

    // Initialize popover with empty content first
    notificationsPopover = new bootstrap.Popover(logoContainer, {
        html: true,
        content: createPopoverContent([]),
        placement: 'bottom',
        trigger: 'manual',
        container: 'body',
        customClass: 'notifications-popover',
        animation: false,
        sanitize: false
    });

    // Add ARIA attributes to logo container
    logoContainer.setAttribute('aria-haspopup', 'true');
    logoContainer.setAttribute('aria-expanded', 'false');
    logoContainer.setAttribute('tabindex', '0');

    let isPopoverVisible = false;

    // Handle click on logo container to toggle popover
    logoContainer.addEventListener('click', async (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (isPopoverVisible) {
            notificationsPopover.hide();
            isPopoverVisible = false;
        } else {
            try {
                // Force update notifications and get the notifications data
                const notifications = await updateNotifications(true);

                // Show the popover
                notificationsPopover.show();
                isPopoverVisible = true;

                // Attach listeners after popover is shown
                if (notifications) {
                    attachNotificationListeners(notifications);
                }
            } catch (error) {
                console.error('Error showing notifications:', error);
            }
        }
    });

    // Close popover when clicking outside
    document.addEventListener('click', (event) => {
        if (isPopoverVisible) {
            const popoverElement = document.querySelector('.popover.notifications-popover');
            const isClickInsidePopover = popoverElement && popoverElement.contains(event.target);
            const isClickOnLogo = logoContainer.contains(event.target);

            if (!isClickInsidePopover && !isClickOnLogo) {
                notificationsPopover.hide();
                isPopoverVisible = false;
            }
        }
    });

    // Add event listeners for popover events
    logoContainer.addEventListener('show.bs.popover', () => {
        logoContainer.setAttribute('aria-expanded', 'true');
    });

    logoContainer.addEventListener('shown.bs.popover', () => {
        const popoverElement = document.querySelector('.popover.notifications-popover');
        if (popoverElement) {
            popoverElement.addEventListener('click', (event) => {
                event.stopPropagation();
            });
        }
    });

    logoContainer.addEventListener('hidden.bs.popover', () => {
        logoContainer.setAttribute('aria-expanded', 'false');
        isPopoverVisible = false;
    });

    // Initial fetch
    updateNotifications();

    // Set up periodic refresh only when popover is not visible
    updateInterval = setInterval(() => {
        const popoverElement = document.querySelector('.popover.notifications-popover.show');
        if (!popoverElement) {
            updateNotifications();
        }
    }, 30000);
});

// Clean up on page unload
window.addEventListener('unload', () => {
    if (notificationsPopover) {
        notificationsPopover.dispose();
    }
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    if (abortController) {
        abortController.abort();
    }
});

// Export NotificationActions for use in other files
window.NotificationActions = NotificationActions;

// Listen for token expiration events
window.addEventListener('tokenExpired', function(event) {
    const message = event.detail.message;
    let notice = document.getElementById('token-expiration-notice');
    if (!notice) {
        notice = document.createElement('div');
        notice.id = 'token-expiration-notice';
        document.body.appendChild(notice);
    }

    notice.innerHTML = `
        <div class="token-expiration-message">${message}</div>
        <button onclick="resetSession()" class="token-expiration-button">Return to Login</button>
    `;
});

// Add event listener for the view all link
document.addEventListener('click', function(event) {
    if (event.target.matches('.view-all-link') || event.target.closest('.view-all-link')) {
        event.stopPropagation();
        window.location.href = '/notifications';
    }
});
