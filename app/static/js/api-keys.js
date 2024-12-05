function deleteAPIKey(api_key_id) {
    makeAuthenticatedRequest(`/api/v1/api_keys/${api_key_id}`, 'DELETE')
        .then(async response => {
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.msg || 'Failed to delete API key');
            }
            flash('API key deleted successfully', 'success');
            location.reload();
        })
        .catch(error => {
            console.error('Error deleting API key:', error);
            flash('Failed to delete API key: ' + error.message, 'error');
        });
}
