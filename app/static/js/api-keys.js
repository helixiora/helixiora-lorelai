// Function to show flash messages
function showMessage(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    // Find or create the flash message container
    let flashContainer = document.getElementById('flash-messages');
    if (!flashContainer) {
        flashContainer = document.createElement('div');
        flashContainer.id = 'flash-messages';
        flashContainer.className = 'container mt-3';
        document.body.insertBefore(flashContainer, document.body.firstChild);
    }

    flashContainer.appendChild(alertDiv);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function deleteAPIKey(api_key_id) {
    if (!confirm('Are you sure you want to delete this API key?')) {
        return;
    }

    makeAuthenticatedRequest(`/api/v1/api_keys/${api_key_id}`, 'DELETE')
        .then(async response => {
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to delete API key');
            }
            showMessage('API key deleted successfully', 'success');
            location.reload();
        })
        .catch(error => {
            console.error('Error deleting API key:', error);
            showMessage('Failed to delete API key: ' + error.message, 'danger');
        });
}
