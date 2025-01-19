// Initialize variables
let lastNotificationCount = 0;
let notificationsDropdown = null;
let logoContainer = null;

const NotificationActions = {
    markAsRead: async function(notificationId) {
        try {
            const response = await makeAuthenticatedRequest(`/api/v1/notifications/${notificationId}/read`, 'POST');
            if (response.success) {
                console.log('Notification marked as read:', notificationId);
                return response;
            }
            throw new Error('Failed to mark notification as read');
        } catch (error) {
            console.error('Error marking notification as read:', error);
            throw error;
        }
    },

    dismiss: async function(notificationId) {
        try {
            const response = await makeAuthenticatedRequest(`/api/v1/notifications/${notificationId}/dismiss`, 'POST');
            if (response.success) {
                console.log('Notification dismissed:', notificationId);
                return response;
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

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Skip initialization if we're on the notifications page
    if (window.location.pathname === '/notifications') {
        return;
    }

    // Initialize logo container
    logoContainer = document.getElementById('logoContainer');

    if (!logoContainer) {
        console.warn('Logo container not found');
        return;
    }

    // Initialize dropdown
    const dropdown = new bootstrap.Dropdown(logoContainer);

    // Fetch notifications immediately
    fetchNotifications();

    // Set up periodic refresh every 30 seconds
    setInterval(fetchNotifications, 30000);
});

// Function to fetch notifications
async function fetchNotifications() {
    try {
        console.log('Fetching notifications...');
        const response = await makeAuthenticatedRequest('/api/v1/notifications?include_counts=true', 'GET');

        // Parse the response body as JSON
        const data = await response.json();
        console.log('Received notifications data:', data);

        if (!data || !data.notifications) {
            console.error('Invalid response data:', data);
            return;
        }

        const activeNotifications = data.notifications.filter(n => !n.dismissed);
        const unreadCount = activeNotifications.filter(n => !n.read).length;
        const recentNotifications = activeNotifications.slice(0, 10);

        console.log(`Found ${unreadCount} unread notifications out of ${activeNotifications.length} active notifications`);

        // Update badge count with calculated unread count
        NotificationActions.updateBadgeCount(unreadCount);

        // Update notification list
        updateNotificationList(recentNotifications);

    } catch (error) {
        console.error('Error fetching notifications:', error);
        handleFetchError();
    }
}

// Function to handle fetch errors
function handleFetchError() {
    const notificationList = document.querySelector('.notifications-carousel');
    if (notificationList) {
        notificationList.innerHTML = `
            <div class="text-center py-4" role="alert">
                <i class="bi bi-exclamation-circle text-danger" style="font-size: 2rem;" aria-hidden="true"></i>
                <p class="mb-0 mt-2">Failed to load notifications</p>
            </div>
        `;
    }
}

// Function to update notification list
function updateNotificationList(notifications) {
    const notificationList = document.querySelector('.notifications-carousel');
    if (!notificationList) {
        console.warn('Notification list container not found');
        return;
    }

    if (!notifications || notifications.length === 0) {
        notificationList.innerHTML = `
            <div class="text-center py-4" role="alert">
                <i class="bi bi-bell-slash text-muted" style="font-size: 2rem;" aria-hidden="true"></i>
                <p class="mb-0 mt-2">No notifications</p>
            </div>
        `;
        return;
    }

    // Create carousel structure
    let carouselHtml = `
        <div class="position-relative">
            ${notifications.length > 1 ? `
                <button class="btn btn-sm btn-light position-absolute top-50 start-0 translate-middle-y ms-2 nav-prev"
                        style="z-index: 1000;" aria-label="Previous notification">
                    <i class="bi bi-chevron-left" aria-hidden="true"></i>
                </button>
                <button class="btn btn-sm btn-light position-absolute top-50 end-0 translate-middle-y me-2 nav-next"
                        style="z-index: 1000;" aria-label="Next notification">
                    <i class="bi bi-chevron-right" aria-hidden="true"></i>
                </button>
            ` : ''}
            <div class="notifications-cards">
                ${notifications.map((notification, index) => `
                    <div class="notification-card ${index === 0 ? 'active' : index === 1 ? 'next' : ''}"
                         role="listitem" data-notification-id="${notification.id}">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <h6 class="mb-1 fw-bold" id="notification-title-${notification.id}">
                                ${notification.title}
                            </h6>
                            <small class="text-muted" id="notification-date-${notification.id}">
                                ${new Date(notification.created_at).toLocaleString()}
                            </small>
                        </div>
                        <p class="mb-2 fw-bold" id="notification-message-${notification.id}">
                            ${notification.message}
                        </p>
                        ${notification.data ? `
                            <div class="notification-data small text-muted mb-2" id="notification-data-${notification.id}">
                                ${Object.entries(notification.data).map(([key, value]) =>
                                    `<div><strong>${key}:</strong> ${value}</div>`
                                ).join('')}
                            </div>
                        ` : ''}
                        <div class="d-flex justify-content-between align-items-center">
                            ${notification.url ? `
                                <a href="${notification.url}" class="btn btn-sm btn-link"
                                   id="notification-link-${notification.id}"
                                   aria-label="View details for ${notification.title}">
                                    View Details
                                </a>
                            ` : '<div></div>'}
                            <div class="btn-group">
                                <button class="btn btn-sm btn-outline-success mark-read"
                                        data-notification-id="${notification.id}"
                                        id="mark-read-${notification.id}"
                                        aria-label="Mark ${notification.title} as read">
                                    <i class="bi bi-check2" aria-hidden="true"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-secondary dismiss-notification"
                                        data-notification-id="${notification.id}"
                                        id="dismiss-${notification.id}"
                                        aria-label="Dismiss ${notification.title}">
                                    <i class="bi bi-x" aria-hidden="true"></i>
                                </button>
                            </div>
                        </div>
                        ${index === 0 ? `
                            <div class="text-center mt-2">
                                <small class="text-muted">Showing most recent notifications (${notifications.length} of ${notifications.length})</small>
                            </div>
                        ` : ''}
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    notificationList.innerHTML = carouselHtml;

    // Set up carousel navigation if there are multiple notifications
    if (notifications.length > 1) {
        setupCarouselNavigation();
    }

    // Set up notification action handlers
    setupNotificationActions();
}

// Function to set up carousel navigation
function setupCarouselNavigation() {
    const prevButton = document.querySelector('.nav-prev');
    const nextButton = document.querySelector('.nav-next');
    const cards = document.querySelectorAll('.notification-card');
    let currentIndex = 0;

    if (!prevButton || !nextButton || !cards.length) return;

    function updateButtons() {
        prevButton.disabled = currentIndex === 0;
        nextButton.disabled = currentIndex === cards.length - 1;
    }

    function showCard(index) {
        cards.forEach((card, i) => {
            card.className = 'notification-card';
            if (i === index) card.classList.add('active');
            else if (i === index + 1) card.classList.add('next');
            else if (i === index - 1) card.classList.add('prev');
        });
        currentIndex = index;
        updateButtons();
    }

    prevButton.addEventListener('click', () => {
        if (currentIndex > 0) showCard(currentIndex - 1);
    });

    nextButton.addEventListener('click', () => {
        if (currentIndex < cards.length - 1) showCard(currentIndex + 1);
    });

    updateButtons();
}

// Function to set up notification action handlers
function setupNotificationActions() {
    // Handle mark as read
    document.querySelectorAll('.mark-read').forEach(button => {
        button.addEventListener('click', async (e) => {
            const notificationId = e.currentTarget.dataset.notificationId;
            try {
                await NotificationActions.markAsRead(notificationId);
                const card = e.currentTarget.closest('.notification-card');
                if (card) {
                    // Remove bold from title and message
                    const title = card.querySelector(`#notification-title-${notificationId}`);
                    const message = card.querySelector(`#notification-message-${notificationId}`);
                    if (title) title.classList.remove('fw-bold');
                    if (message) message.classList.remove('fw-bold');
                    // Remove the mark as read button
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
                const card = e.currentTarget.closest('.notification-card');
                if (card) {
                    // If this is the only card, update the entire list
                    if (document.querySelectorAll('.notification-card').length === 1) {
                        fetchNotifications();
                    } else {
                        // Otherwise, just remove this card and update the navigation
                        card.remove();
                        setupCarouselNavigation();
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
