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

        // Update the title and message cells
        $row.find('.notification-title, .notification-message').removeClass('fw-bold');

        // Remove the mark as read button
        $row.find('.mark-read-btn').remove();

        // Update the status badge
        $row.find('.notification-status')
            .removeClass('notification-status-unread')
            .addClass('notification-status-read')
            .text('Read');

        // Refresh the table to ensure proper sorting/filtering
        notificationsTable.draw(false);

        // Update notification counts
        updateNotificationCounts();
    } catch (error) {
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
        $row.find('.notification-actions').empty();

        // Update the status badge
        $row.find('.notification-status')
            .removeClass('notification-status-unread notification-status-read')
            .addClass('notification-status-dismissed')
            .text('Dismissed');

        // Refresh the table to ensure proper sorting/filtering
        notificationsTable.draw(false);

        // Update notification counts
        updateNotificationCounts();
    } catch (error) {
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
        showError('Failed to update notification counts');
    }
}

// Initialize DataTable with common settings
function initializeNotificationsTable() {
    return $('#notificationsTable').DataTable({
        order: [[1, 'desc']], // Sort by created_at by default
        columnDefs: [
            {
                targets: [
                    { name: 'checkbox', index: 0 },
                    { name: 'created_at', index: 1 },
                    { name: 'type', index: 2 },
                    { name: 'title', index: 3 },
                    { name: 'message', index: 4 },
                    { name: 'status', index: 5 },
                    { name: 'actions', index: 6 }
                ],
                orderable: false,
                className: 'no-sort'
            }
        ],
        pageLength: 25,
        responsive: true,
        createdRow: function(row, data, dataIndex) {
            // Add data attributes for easier access
            $(row).attr('data-notification-id', data.id);
            $(row).addClass('notification-row');
        }
    });
}

// Quick date filter helper
function setQuickDateFilter(value) {
    const now = new Date();
    let start = null;
    let end = null;

    switch(value) {
        case 'today':
            start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
            break;
        case 'yesterday':
            start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
            end = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59);
            break;
        case 'last7days':
            start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6);
            end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
            break;
        case 'last30days':
            start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 29);
            end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
            break;
        case 'thisMonth':
            start = new Date(now.getFullYear(), now.getMonth(), 1);
            end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
            break;
        case 'lastMonth':
            start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            end = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59);
            break;
    }

    if (start && end) {
        $('#notificationStartDate').val(start.toISOString().split('T')[0]);
        $('#notificationEndDate').val(end.toISOString().split('T')[0]);
    } else {
        $('#notificationStartDate').val('');
        $('#notificationEndDate').val('');
    }
}

// Function to get current filter values
function getFilterValues() {
    const filters = {};

    // Get status filter value
    const statusFilter = document.getElementById('notificationStatusFilter')?.value;
    if (statusFilter === 'unread') {
        filters.show_read = false;
        filters.show_unread = true;
    } else if (statusFilter === 'read') {
        filters.show_read = true;
        filters.show_unread = false;
    }

    // Get type filter value
    const typeFilter = document.getElementById('notificationTypeFilter')?.value;
    if (typeFilter && typeFilter !== 'all') {
        filters.type = typeFilter;
    }

    // Get date range values
    const startDate = document.getElementById('notificationStartDate')?.value;
    const endDate = document.getElementById('notificationEndDate')?.value;
    if (startDate) filters.start_date = startDate;
    if (endDate) filters.end_date = endDate;

    return filters;
}

// Apply DataTable filters
function applyFilters(table) {
    const statusFilter = $('#notificationStatusFilter').val();
    const typeFilter = $('#notificationTypeFilter').val();
    const startDate = $('#notificationStartDate').val();
    const endDate = $('#notificationEndDate').val();
    const showDismissed = $('#showDismissedCheckbox').is(':checked');

    // Apply type filter
    table.column('type:name').search(typeFilter);

    // Custom filtering function for status and dismissed state
    $.fn.dataTable.ext.search.push(function(settings, searchData, index, rowData) {
        const $row = $(table.row(index).node());
        const status = $row.find('.notification-status').text().toLowerCase();

        // Filter out dismissed notifications unless explicitly shown
        if (!showDismissed && status.includes('dismissed')) {
            return false;
        }

        // Apply status filter if set
        if (statusFilter) {
            if (statusFilter === 'read' && !status.includes('read')) return false;
            if (statusFilter === 'unread' && !status.includes('unread')) return false;
        }

        return true;
    });

    // Date range filter
    if (startDate && endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        end.setHours(23, 59, 59);

        $.fn.dataTable.ext.search.push(function(settings, searchData, index, rowData) {
            const date = new Date($(table.cell(index, 'created_at:name').node()).text());
            return date >= start && date <= end;
        });
    }

    table.draw();

    // Clear custom filters after drawing
    $.fn.dataTable.ext.search.pop();
    if (startDate && endDate) {
        $.fn.dataTable.ext.search.pop();
    }
}

// Handle bulk actions
function setupBulkActions() {
    const $selectAll = $('#selectAll');
    const $deselectAll = $('#deselectAll');
    const $markSelectedRead = $('#markSelectedRead');
    const $dismissSelected = $('#dismissSelected');

    function updateBulkActionButtons() {
        const selectedCount = $('.notification-checkbox:checked').length;
        $markSelectedRead.prop('disabled', selectedCount === 0);
        $dismissSelected.prop('disabled', selectedCount === 0);
    }

    $selectAll.on('click', () => {
        $('.notification-checkbox').prop('checked', true);
        updateBulkActionButtons();
    });

    $deselectAll.on('click', () => {
        $('.notification-checkbox').prop('checked', false);
        updateBulkActionButtons();
    });

    $(document).on('change', '.notification-checkbox', updateBulkActionButtons);

    // Handle bulk mark as read
    $markSelectedRead.on('click', async () => {
        const selectedIds = $('.notification-checkbox:checked')
            .closest('.notification-row')
            .map((_, row) => $(row).data('notification-id'))
            .get();

        if (selectedIds.length === 0) return;

        try {
            const response = await makeAuthenticatedRequest('/api/v1/notifications/bulk/read', 'POST', {
                notification_ids: selectedIds
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Failed to mark notifications as read');
            }

            // Update UI without page reload
            for (const id of selectedIds) {
                const $row = $(`.notification-row[data-notification-id="${id}"]`);
                if ($row.length) {
                    $row.find('.notification-title, .notification-message').removeClass('fw-bold');
                    $row.find('.mark-read-btn').remove();
                    $row.find('.notification-status')
                        .removeClass('notification-status-unread')
                        .addClass('notification-status-read')
                        .text('Read');
                }
            }

            // Update notification counts
            updateNotificationCounts();

            // Refresh table display
            notificationsTable.draw(false);
        } catch (error) {
            showError(error.message || 'Failed to mark notifications as read');
        }
    });

    // Handle bulk dismiss
    $dismissSelected.on('click', async () => {
        const selectedIds = $('.notification-checkbox:checked')
            .closest('.notification-row')
            .map((_, row) => $(row).data('notification-id'))
            .get();

        if (selectedIds.length === 0) return;

        try {
            const response = await makeAuthenticatedRequest('/api/v1/notifications/bulk/dismiss', 'POST', {
                notification_ids: selectedIds
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Failed to dismiss notifications');
            }

            // Update UI without page reload
            for (const id of selectedIds) {
                const $row = $(`.notification-row[data-notification-id="${id}"]`);
                if ($row.length) {
                    $row.find('.notification-actions').empty();
                    $row.find('.notification-status')
                        .removeClass('notification-status-unread notification-status-read')
                        .addClass('notification-status-dismissed')
                        .text('Dismissed');
                }
            }

            // Update notification counts
            updateNotificationCounts();

            // Refresh table display
            notificationsTable.draw(false);
        } catch (error) {
            showError(error.message || 'Failed to dismiss notifications');
        }
    });
}

// Initialize everything when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Ensure dismissed notifications are hidden by default
    $('#showDismissedCheckbox').prop('checked', false);

    const table = initializeNotificationsTable();
    setupBulkActions();

    // Initial fetch with default filters (hiding dismissed)
    fetchNotifications();

    // Set up filter event handlers
    $('#notificationQuickDateFilter').on('change', function() {
        setQuickDateFilter($(this).val());
        applyFilters(table);
    });

    $('#notificationStatusFilter, #notificationTypeFilter, #notificationStartDate, #notificationEndDate, #showDismissedCheckbox')
        .on('change', () => applyFilters(table));

    // Handle individual notification actions
    $(document).on('click', '.mark-read', async function(e) {
        e.preventDefault();
        const notificationId = $(this).data('notification-id');
        try {
            await makeAuthenticatedRequest(`/api/v1/notifications/${notificationId}/read`, 'POST');
            window.location.reload();
        } catch (error) {
            console.error('Failed to mark notification as read:', error);
            alert('Failed to mark notification as read');
        }
    });

    $(document).on('click', '.dismiss-notification', async function(e) {
        e.preventDefault();
        const notificationId = $(this).data('notification-id');
        try {
            await makeAuthenticatedRequest(`/api/v1/notifications/${notificationId}/dismiss`, 'POST');
            window.location.reload();
        } catch (error) {
            console.error('Failed to dismiss notification:', error);
            alert('Failed to dismiss notification');
        }
    });
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

        const response = await makeAuthenticatedRequest(`/api/v1/notifications?${params.toString()}`, 'GET');
        if (!response.ok) {
            throw new Error('Failed to fetch notifications');
        }

        const data = await response.json();
        if (!data || !data.notifications) {
            throw new Error('Invalid response format');
        }

        // Calculate counts for different notification states
        const counts = {
            total: data.notifications.length,
            active: data.notifications.filter(n => !n.dismissed).length,
            unread: data.notifications.filter(n => !n.read && !n.dismissed).length,
            dismissed: data.notifications.filter(n => n.dismissed).length
        };

        // Update the table
        notificationsTable.clear().rows.add(data.notifications).draw();

        // Update counts display
        updateCountsDisplay(counts);

        // Update the badge in the navigation
        if (window.NotificationActions?.updateBadgeCount) {
            window.NotificationActions.updateBadgeCount(counts.unread);
        }

    } catch (error) {
        showError('Failed to load notifications. Please try again.');
    } finally {
        isRefreshing = false;
    }
}

// Function to update counts display
function updateCountsDisplay(counts) {
    const countDisplay = document.getElementById('notificationCounts');
    if (countDisplay) {
        countDisplay.innerHTML = `
            <span class="me-3">Total: ${counts.total}</span>
            <span class="me-3">Active: ${counts.active}</span>
            <span class="me-3">Unread: ${counts.unread}</span>
            <span>Dismissed: ${counts.dismissed}</span>
        `;
    }
}

// Function to show error messages
function showError(message) {
    const $errorAlert = $('#notificationErrorAlert');
    $errorAlert.text(message).removeClass('d-none');
    setTimeout(() => $errorAlert.addClass('d-none'), 5000);
}
