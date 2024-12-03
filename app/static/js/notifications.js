document.addEventListener('DOMContentLoaded', function() {
    const logoContainer = document.getElementById('logoContainer');
    const notificationBadge = document.getElementById('notificationBadge');
    const notificationPopover = document.getElementById('notificationPopover');
    const notificationList = document.getElementById('notificationList');

    let lastFetchTime = 0;
    let fetchInterval;

    // Function to fetch notifications
    async function fetchNotifications() {
        lastFetchTime = Date.now();
        try {
            // For the popup, we want unread and non-dismissed notifications
            const params = new URLSearchParams({
                show_read: 'false',     // Only show unread
                show_unread: 'true',    // Show unread
                show_dismissed: 'false'  // Don't show dismissed
            });

            const csrfToken = getCookie('csrf_token');
            const response = await fetch(`/api/v1/notifications?${params.toString()}`, {
                headers: {
                    'X-CSRF-TOKEN': csrfToken
                }
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const data = await response.json();
            updateNotificationBadge(data.counts.unread);
            updateNotificationList(data.notifications);
            updateNotificationCounts(data.counts);
        } catch (error) {
            console.error('Error fetching notifications:', error);
            handleFetchError();
        }
    }

    // Add a new function for fetching all notifications (for the full notifications page)
    async function fetchAllNotifications() {
        try {
            const params = new URLSearchParams({
                show_read: 'true',
                show_unread: 'true',
                show_dismissed: 'true'
            });

            const csrfToken = getCookie('csrf_token');
            const response = await fetch(`/api/v1/notifications?${params.toString()}`, {
                headers: {
                    'X-CSRF-TOKEN': csrfToken
                }
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching all notifications:', error);
            throw error;
        }
    }

    // Function to update notification badge
    function updateNotificationBadge(count) {
        if (count === 0) {
            notificationBadge.className = 'notification-badge empty';
            notificationBadge.textContent = '0';
        } else {
            notificationBadge.className = 'notification-badge has-notifications';
            notificationBadge.textContent = count > 9 ? '9+' : count.toString();
        }
    }

    // Function to update notification list
    function updateNotificationList(notifications) {
        notificationList.innerHTML = '';
        if (notifications.length === 0) {
            const li = document.createElement('li');
            li.textContent = 'No notifications';
            li.className = 'notification-item';
            notificationList.appendChild(li);
        } else {
            notifications.forEach(notification => {
                // Skip dismissed notifications
                if (notification.dismissed_at) return;

                const li = document.createElement('li');
                li.className = `notification-item ${notification.type}`;
                li.dataset.id = notification.id;

                // Add 'read' class if the notification is read
                if (notification.read_at) {
                    li.classList.add('read');
                } else {
                    li.style.fontWeight = 'bold'; // Make unread notifications bold
                }

                const title = document.createElement('strong');
                title.textContent = notification.title;
                li.appendChild(title);

                const message = document.createElement('p');
                message.textContent = notification.message;
                li.appendChild(message);

                const date = document.createElement('small');
                date.textContent = new Date(notification.created_at).toLocaleString();
                li.appendChild(date);

                if (notification.url) {
                    const link = document.createElement('a');
                    link.href = notification.url;
                    link.textContent = 'View';
                    li.appendChild(link);
                }

                const actionDiv = document.createElement('div');
                actionDiv.className = 'notification-actions';

                // Only show "Mark as Read" button if the notification is unread
                if (!notification.read_at) {
                    const readBtn = document.createElement('button');
                    readBtn.textContent = 'Mark as Read';
                    readBtn.classList.add('btn', 'btn-primary', 'btn-sm');
                    readBtn.onclick = () => markAsRead(notification.id);
                    actionDiv.appendChild(readBtn);
                }

                const dismissBtn = document.createElement('button');
                dismissBtn.textContent = 'Dismiss';
                dismissBtn.classList.add('btn', 'btn-primary', 'btn-sm');
                dismissBtn.onclick = () => dismissNotification(notification.id);
                actionDiv.appendChild(dismissBtn);

                li.appendChild(actionDiv);

                notificationList.appendChild(li);
            });
        }

        // Add summary section at the bottom
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'notification-summary';
        summaryDiv.innerHTML = `
            <div class="notification-counts">
                <span>Read: <span id="readCount">-</span></span>
                <span>Unread: <span id="unreadCount">-</span></span>
                <span>Dismissed: <span id="dismissedCount">-</span></span>
            </div>
            <a href="/notifications" class="view-all-link">View All Notifications</a>
        `;
        notificationList.appendChild(summaryDiv);
    }

    // Function to handle fetch errors
    function handleFetchError() {
        updateNotificationBadge(0);
        notificationList.innerHTML = '<li class="text-danger">Unable to load notifications. Please try again later.</li>';
    }

    // Function to mark a notification as read
    async function markAsRead(notificationId) {
        try {
            const csrfToken = getCookie('csrf_token');
            const response = await fetch(`/api/v1/notifications/${notificationId}/read`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfToken
                },
            });
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Fetch fresh notifications instead of manually updating the UI
                    fetchNotifications();
                } else {
                    console.error('Failed to mark notification as read:', data.error);
                }
            } else {
                console.error('Failed to mark notification as read:', response.statusText);
            }
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }

    // Function to dismiss a notification
    async function dismissNotification(notificationId) {
        try {
            const csrfToken = getCookie('csrf_token');
            const response = await fetch(`/api/v1/notifications/${notificationId}/dismiss`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfToken
                },
            });
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Fetch fresh notifications instead of manually updating the UI
                    fetchNotifications();
                } else {
                    console.error('Failed to dismiss notification:', data.error);
                }
            } else {
                console.error('Failed to dismiss notification:', response.statusText);
            }
        } catch (error) {
            console.error('Error dismissing notification:', error);
        }
    }

    // Function to update notification counts
    function updateNotificationCounts(counts) {
        const readCount = document.getElementById('readCount');
        const unreadCount = document.getElementById('unreadCount');
        const dismissedCount = document.getElementById('dismissedCount');

        if (readCount) readCount.textContent = counts.read;
        if (unreadCount) unreadCount.textContent = counts.unread;
        if (dismissedCount) dismissedCount.textContent = counts.dismissed;
    }

    // Show/hide popover on hover
    logoContainer.addEventListener('mouseenter', () => {
        notificationPopover.style.display = 'block';
        // Only fetch if we haven't fetched recently
        if (Date.now() - lastFetchTime > 5000) {
            fetchNotifications();
        }
    });

    logoContainer.addEventListener('mouseleave', () => {
        notificationPopover.style.display = 'none';
    });

    // Initial fetch of notifications
    fetchNotifications();

    // Set up periodic fetching (e.g., every 30 seconds)
    setInterval(fetchNotifications, 30000);

    // Add smooth scrolling to notification list if it exceeds the popover height
    notificationPopover.style.maxHeight = '300px';
    notificationPopover.style.overflowY = 'auto';
});
