document.addEventListener('DOMContentLoaded', function() {
    const logoContainer = document.getElementById('logoContainer');
    const notificationBadge = document.getElementById('notificationBadge');
    const notificationPopover = document.getElementById('notificationPopover');
    const notificationList = document.getElementById('notificationList');

    // Function to fetch notifications
    function fetchNotifications() {
        fetch('/api/notifications')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(notifications => {
                updateNotificationBadge(notifications.length);
                updateNotificationList(notifications);
            })
            .catch(error => {
                console.error('Error fetching notifications:', error);
                handleFetchError();
            });
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
                const li = document.createElement('li');
                li.className = `notification-item ${notification.type}`;
                li.dataset.id = notification.id;

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

                const readBtn = document.createElement('button');
                readBtn.textContent = 'Mark as Read';
                readBtn.onclick = () => markAsRead(notification.id);
                actionDiv.appendChild(readBtn);

                const dismissBtn = document.createElement('button');
                dismissBtn.textContent = 'Dismiss';
                dismissBtn.onclick = () => dismissNotification(notification.id);
                actionDiv.appendChild(dismissBtn);

                li.appendChild(actionDiv);

                notificationList.appendChild(li);
            });
        }
    }

    // Function to handle fetch errors
    function handleFetchError() {
        updateNotificationBadge(0);
        notificationList.innerHTML = '<li class="text-danger">Unable to load notifications. Please try again later.</li>';
    }

    // Function to mark a notification as read
    async function markAsRead(notificationId) {
        try {
            const response = await fetch(`/api/notifications/${notificationId}/read`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    const notificationItem = document.querySelector(`.notification-item[data-id="${notificationId}"]`);
                    if (notificationItem) {
                        notificationItem.classList.add('read');
                    }
                    updateNotificationBadge(data.remaining_unread);
                    updateNotificationCounts(data);
                } else {
                    console.error('Failed to mark notification as read');
                }
            } else {
                console.error('Failed to mark notification as read');
            }
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }

    // Function to dismiss a notification
    async function dismissNotification(notificationId) {
        try {
            const response = await fetch(`/api/notifications/${notificationId}/dismiss`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    const notificationItem = document.querySelector(`.notification-item[data-id="${notificationId}"]`);
                    if (notificationItem) {
                        notificationItem.remove();
                    }
                    updateNotificationBadge(data.remaining_unread);
                    updateNotificationCounts(data);
                } else {
                    console.error('Failed to dismiss notification');
                }
            } else {
                console.error('Failed to dismiss notification');
            }
        } catch (error) {
            console.error('Error dismissing notification:', error);
        }
    }

    // New function to update notification counts
    function updateNotificationCounts(data) {
        // Update any UI elements that display notification counts
        // For example:
        document.getElementById('readCount').textContent = data.read;
        document.getElementById('undismissedCount').textContent = data.undismissed;
    }

    // Show/hide popover on hover
    logoContainer.addEventListener('mouseenter', () => {
        notificationPopover.style.display = 'block';
        fetchNotifications(); // Fetch notifications when hovering
    });

    logoContainer.addEventListener('mouseleave', () => {
        notificationPopover.style.display = 'none';
    });

    // Initial fetch of notifications
    fetchNotifications();

    // Set up periodic fetching (e.g., every 5 minutes)
    setInterval(fetchNotifications, 5000);

    // Add smooth scrolling to notification list if it exceeds the popover height
    notificationPopover.style.maxHeight = '300px';
    notificationPopover.style.overflowY = 'auto';
});
