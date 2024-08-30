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
                li.textContent = notification.message;
                li.className = 'notification-item';
                notificationList.appendChild(li);
            });
        }
    }

    // Function to handle fetch errors
    function handleFetchError() {
        updateNotificationBadge(0);
        notificationList.innerHTML = '<li class="text-danger">Unable to load notifications. Please try again later.</li>';
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
