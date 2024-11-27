function deleteAPIKey(api_key_id) {
    makeAuthenticatedRequest(`/api/v1/api_keys/${api_key_id}`, {
        method: 'DELETE',
    }).then(response => {
        console.log(response);
        flash('API key deleted successfully', 'success');
        location.reload();
    }).catch(error => {
        console.error(error);
        flash('Failed to delete API key', 'error');
    });
}
