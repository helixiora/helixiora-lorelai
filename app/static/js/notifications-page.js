// Initialize variables
let notificationsTable = null;
let lastFetchTime = 0;
let isRefreshing = false;
let fetchInterval = null;

// Function to handle mark as read action
async function markNotificationAsRead(notificationId, row) {
    try {
        await window.NotificationActions.markAsRead(notificationId);

        // Update the row UI
        const $row = $(row);

        // Update the title and message columns to remove bold
        $row.find('td:nth-child(4), td:nth-child(5)').removeClass('fw-bold');

        // Remove the mark as read button
        $row.find('.mark-read').remove();

        // Update the status badge
        $row.find('td:nth-child(6) .badge')
            .removeClass('bg-primary')
            .addClass('bg-success')
            .text('Read');

        // Refresh the table to ensure proper sorting/filtering
        notificationsTable.draw(false);

        // Update notification counts
        updateNotificationCounts();
    } catch (error) {
        console.error('Error marking notification as read:', error);
        showError('Failed to mark notification as read. Please try again.');
        throw error;
    }
}

// Function to handle dismiss action
async function dismissNotification(notificationId, row) {
    try {
        await window.NotificationActions.dismiss(notificationId);

        // Update the row UI
        const $row = $(row);

        // Remove action buttons
        $row.find('.btn-group').empty();

        // Update the status badge
        $row.find('td:nth-child(6) .badge')
            .removeClass('bg-primary bg-success')
            .addClass('bg-secondary')
            .text('Dismissed');

        // Refresh the table to ensure proper sorting/filtering
        notificationsTable.draw(false);

        // Update notification counts
        updateNotificationCounts();
    } catch (error) {
        console.error('Error dismissing notification:', error);
        showError('Failed to dismiss notification. Please try again.');
        throw error;
    }
}

// Function to update notification counts
async function updateNotificationCounts() {
    try {
        const response = await makeAuthenticatedRequest('/api/v1/notifications/counts', 'GET');
        if (!response.ok) return;

        const data = await response.json();
        window.NotificationActions.updateBadgeCount(data.unread);
    } catch (error) {
        console.error('Error updating notification counts:', error);
    }
}

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize DataTable
    notificationsTable = $('#notificationsTable').DataTable({
        order: [[1, 'desc']], // Sort by created_at by default
        pageLength: 25,
        responsive: true,
        columns: [
            {
                data: null,
                orderable: false,
                render: function(data, type, row) {
                    return `<input type="checkbox" class="form-check-input notification-checkbox"
                            data-notification-id="${row.id}" aria-label="Select notification">`;
                }
            },
            {
                data: 'created_at',
                render: function(data) {
                    return new Date(data).toLocaleString();
                }
            },
            { data: 'type' },
            {
                data: 'title',
                render: function(data, type, row) {
                    return `<span class="${!row.read_at ? 'fw-bold' : ''}">${data}</span>`;
                }
            },
            {
                data: 'message',
                render: function(data, type, row) {
                    return `<span class="${!row.read_at ? 'fw-bold' : ''}">${data}</span>`;
                }
            },
            {
                data: null,
                render: function(data) {
                    let badgeClass = 'bg-primary';
                    let status = 'Unread';

                    if (data.dismissed_at) {
                        badgeClass = 'bg-secondary';
                        status = 'Dismissed';
                    } else if (data.read_at) {
                        badgeClass = 'bg-success';
                        status = 'Read';
                    }

                    return `<span class="badge ${badgeClass}">${status}</span>`;
                }
            },
            {
                data: null,
                orderable: false,
                render: function(data, type, row) {
                    const buttons = [];

                    if (!row.read_at) {
                        buttons.push(`
                            <button class="btn btn-sm btn-outline-success mark-read"
                                    data-notification-id="${row.id}"
                                    aria-label="Mark as read">
                                <i class="bi bi-check2"></i>
                            </button>
                        `);
                    }

                    if (!row.dismissed_at) {
                        buttons.push(`
                            <button class="btn btn-sm btn-outline-secondary dismiss-notification"
                                    data-notification-id="${row.id}"
                                    aria-label="Dismiss notification">
                                <i class="bi bi-x"></i>
                            </button>
                        `);
                    }

                    if (row.url) {
                        buttons.push(`
                            <a href="${row.url}" class="btn btn-sm btn-outline-primary"
                               aria-label="View details">
                                <i class="bi bi-box-arrow-up-right"></i>
                            </a>
                        `);
                    }

                    return `<div class="btn-group">${buttons.join('')}</div>`;
                }
            }
        ]
    });

    // Handle mark as read
    $('#notificationsTable').on('click', '.mark-read', async function(e) {
        e.preventDefault();
        e.stopPropagation();
        const button = this;
        const notificationId = $(button).data('notification-id');
        const row = $(button).closest('tr');

        try {
            await markNotificationAsRead(notificationId, row);
        } catch (error) {
            // Error is already handled in markNotificationAsRead
        }
    });

    // Handle dismiss
    $('#notificationsTable').on('click', '.dismiss-notification', async function(e) {
        e.preventDefault();
        e.stopPropagation();
        const button = this;
        const notificationId = $(button).data('notification-id');
        const row = $(button).closest('tr');

        try {
            await dismissNotification(notificationId, row);
        } catch (error) {
            // Error is already handled in dismissNotification
        }
    });

    // Initial fetch
    fetchNotifications();

    // Set up periodic refresh
    fetchInterval = setInterval(fetchNotifications, 30000);

    // Set up filter handlers
    setupFilters();

    // Set up bulk action handlers
    setupBulkActions();
});

// Function to fetch notifications
async function fetchNotifications() {
    if (isRefreshing) return;

    const now = Date.now();
    if (now - lastFetchTime < 5000) return;

    isRefreshing = true;
    lastFetchTime = now;

    try {
        // Get filter values
        const filters = getFilterValues();
        const params = new URLSearchParams(filters);

        const response = await makeAuthenticatedRequest(`/api/v1/notifications/?${params.toString()}`, 'GET');

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (!data.notifications) {
            throw new Error('Invalid response format from server');
        }

        // Update the table
        notificationsTable.clear().rows.add(data.notifications).draw();

        // Update notification counts
        window.NotificationActions.updateBadgeCount(data.counts.unread);
    } catch (error) {
        console.error('Error fetching notifications:', error);
        showError('Failed to fetch notifications. Please try again.');
    } finally {
        isRefreshing = false;
    }
}

// Function to get current filter values
function getFilterValues() {
    return {
        status: $('#notificationStatusFilter').val(),
        type: $('#notificationTypeFilter').val(),
        start_date: $('#notificationStartDate').val(),
        end_date: $('#notificationEndDate').val()
    };
}

// Function to set up filter handlers
function setupFilters() {
    // Handle filter changes
    $('.form-select, #notificationStartDate, #notificationEndDate').on('change', function() {
        fetchNotifications();
    });

    // Handle quick date filter
    $('#notificationQuickDateFilter').on('change', function() {
        const value = $(this).val();
        const dates = getQuickFilterDates(value);
        if (dates) {
            $('#notificationStartDate').val(dates.start);
            $('#notificationEndDate').val(dates.end);
            fetchNotifications();
        }
    });
}

// Function to set up bulk action handlers
function setupBulkActions() {
    // Select all checkbox in header
    $('#selectAllCheckbox').on('change', function() {
        const isChecked = $(this).prop('checked');
        $('.notification-checkbox').prop('checked', isChecked);
        updateBulkActionButtons();
    });

    // Individual checkboxes
    $(document).on('change', '.notification-checkbox', function() {
        updateBulkActionButtons();
    });

    // Bulk mark as read
    $('#markSelectedRead').on('click', async function() {
        const ids = getSelectedNotificationIds();
        if (!ids.length) return;

        try {
            await makeAuthenticatedRequest('/api/v1/notifications/bulk/read', 'POST', {
                ids: ids
            });
            fetchNotifications();
        } catch (error) {
            console.error('Error marking notifications as read:', error);
            showError('Failed to mark notifications as read');
        }
    });

    // Bulk dismiss
    $('#dismissSelected').on('click', async function() {
        const ids = getSelectedNotificationIds();
        if (!ids.length) return;

        try {
            await makeAuthenticatedRequest('/api/v1/notifications/bulk/dismiss', 'POST', {
                ids: ids
            });
            fetchNotifications();
        } catch (error) {
            console.error('Error dismissing notifications:', error);
            showError('Failed to dismiss notifications');
        }
    });
}

// Function to get selected notification IDs
function getSelectedNotificationIds() {
    return $('.notification-checkbox:checked').map(function() {
        return $(this).data('notification-id');
    }).get();
}

// Function to update bulk action buttons
function updateBulkActionButtons() {
    const selectedCount = $('.notification-checkbox:checked').length;
    $('#markSelectedRead, #dismissSelected').prop('disabled', !selectedCount);
}

// Function to attach event listeners to action buttons
function attachEventListeners() {
    // Mark as read
    $('.mark-read').on('click', async function(e) {
        e.preventDefault();
        const id = $(this).data('notification-id');
        try {
            await makeAuthenticatedRequest(`/api/v1/notifications/${id}/read`, 'POST');
            fetchNotifications();
        } catch (error) {
            console.error('Error marking notification as read:', error);
            showError('Failed to mark notification as read');
        }
    });

    // Dismiss
    $('.dismiss-notification').on('click', async function(e) {
        e.preventDefault();
        const id = $(this).data('notification-id');
        try {
            await makeAuthenticatedRequest(`/api/v1/notifications/${id}/dismiss`, 'POST');
            fetchNotifications();
        } catch (error) {
            console.error('Error dismissing notification:', error);
            showError('Failed to dismiss notification');
        }
    });
}

// Helper function to show error messages
function showError(message) {
    // You can implement this based on your UI needs
    alert(message);
}

// Helper function to get dates for quick filter
function getQuickFilterDates(filter) {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    switch (filter) {
        case 'today':
            return {
                start: today.toISOString().split('T')[0],
                end: today.toISOString().split('T')[0]
            };
        case 'yesterday':
            return {
                start: yesterday.toISOString().split('T')[0],
                end: yesterday.toISOString().split('T')[0]
            };
        case 'last7days':
            const last7 = new Date(today);
            last7.setDate(last7.getDate() - 7);
            return {
                start: last7.toISOString().split('T')[0],
                end: today.toISOString().split('T')[0]
            };
        case 'last30days':
            const last30 = new Date(today);
            last30.setDate(last30.getDate() - 30);
            return {
                start: last30.toISOString().split('T')[0],
                end: today.toISOString().split('T')[0]
            };
        case 'thisMonth':
            return {
                start: new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0],
                end: today.toISOString().split('T')[0]
            };
        case 'lastMonth':
            const firstDayLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            const lastDayLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
            return {
                start: firstDayLastMonth.toISOString().split('T')[0],
                end: lastDayLastMonth.toISOString().split('T')[0]
            };
        default:
            return null;
    }
}
