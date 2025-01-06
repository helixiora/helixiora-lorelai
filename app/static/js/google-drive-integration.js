const SCOPES = 'https://www.googleapis.com/auth/drive.file';

let codeClient;
let authorizationCode = null;
let pickerInited = false;
let gisInited = false;

// Note: window.accessToken is set by the template and contains the Google Drive access token
document.getElementById('authorize_button').disabled = true;

// Check button state when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    maybeEnableButtons();
});

async function gapiLoaded() {
    gapi.load('client:picker', initializePicker);
}

async function initializePicker() {
    await gapi.client.load('https://www.googleapis.com/discovery/v1/apis/drive/v3/rest');
    pickerInited = true;
    maybeEnableButtons();
}

async function gisLoaded() {
    // More info here: https://developers.google.com/identity/oauth2/web/reference/js-reference
    codeClient = google.accounts.oauth2.initCodeClient({
        client_id: CLIENT_ID,
        scope: 'openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive.file',
        ux_mode: 'redirect',
        error_callback: async (type) => {
            console.error('Error obtaining authorization code:', type);
        },
        redirect_uri: window.location.origin + '/google/drive/codeclientcallback',
        state: 'google_drive'
    });
    gisInited = true;
    maybeEnableButtons();
}

async function maybeEnableButtons() {
    if (pickerInited && gisInited) {
        document.getElementById('authorize_button').disabled = false;
        // Check if we have an access token in the page data
        console.log('Google Drive access token:', window.accessToken);
        const hasGoogleDriveAccess = window.accessToken &&
            window.accessToken !== 'null' &&
            window.accessToken !== 'None' &&
            window.accessToken !== '';

        if (hasGoogleDriveAccess) {
            document.getElementById('authorize_button').innerText = 'Refresh';
            document.getElementById('signout_button').classList.remove('d-none');
            document.getElementById('select_button').classList.remove('d-none');
        } else {
            document.getElementById('authorize_button').innerText = 'Authorize';
            document.getElementById('signout_button').classList.add('d-none');
            document.getElementById('select_button').classList.add('d-none');
        }
    }
}

// Function to handle sign-out
async function handleSignoutClick() {
    // Check if we have a Google Drive access token
    if (window.accessToken && window.accessToken !== 'null') {
        try {
            // Backend API call uses JWT token (handled by makeAuthenticatedRequest)
            const response = await makeAuthenticatedRequest('/api/v1/googledrive/revoke', 'POST');
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.msg || 'Revoke failed');
            }
            try {
                // Google API call uses Google Drive access token
                await google.accounts.oauth2.revoke(window.accessToken);
            } catch (e) {
                console.warn('Could not revoke token with Google:', e);
            }
            // Reset the Google Drive access token
            window.accessToken = null;
            // Update UI
            document.getElementById('authorize_button').innerText = 'Authorize';
            document.getElementById('signout_button').classList.add('d-none');
            document.getElementById('select_button').classList.add('d-none');
            // Reload page to reset state
            location.reload();
        } catch (error) {
            console.error('Signout error:', error);
            alert('Failed to sign out: ' + error.message);
        }
    } else {
        console.warn('No Google Drive access token available for sign out');
    }
}

async function createPicker() {
    // Verify we have a valid Google Drive access token
    if (!window.accessToken || window.accessToken === 'null') {
        console.error('No valid Google Drive access token available');
        return;
    }

    const shareddrivesview = new google.picker.DocsView(google.picker.ViewId.DOCS)
        .setEnableDrives(true)
        .setSelectFolderEnabled(true)
        .setOwnedByMe(false)
        .setIncludeFolders(true);

    const sharedwithmeview = new google.picker.DocsView(google.picker.ViewId.DOCS)
        .setSelectFolderEnabled(true)
        .setIncludeFolders(true)
        .setOwnedByMe(false);

    const mydriveview = new google.picker.DocsView(google.picker.ViewId.DOCS)
        .setSelectFolderEnabled(true)
        .setOwnedByMe(true)
        .setParent('root')
        .setIncludeFolders(true);

    const picker = new google.picker.PickerBuilder()
        .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
        .enableFeature(google.picker.Feature.SUPPORT_DRIVES)
        .disableFeature(google.picker.Feature.MINE_ONLY)
        .setDeveloperKey(API_KEY)
        .setAppId(APP_ID)
        .setOAuthToken(window.accessToken)  // Use Google Drive access token for picker
        .addView(shareddrivesview)
        .addView(sharedwithmeview)
        .addView(mydriveview)
        .setCallback(pickerCallback)
        .setOrigin(window.location.protocol + '//' + window.location.host)
        .setTitle('Select documents or folders')
        .build();
    picker.setVisible(true);
}

async function pickerCallback(data) {
    if (data.action === google.picker.Action.PICKED) {
        const documents = data[google.picker.Response.DOCUMENTS].map(doc => ({
            id: doc[google.picker.Document.ID],
            name: doc[google.picker.Document.NAME],
            mimeType: doc[google.picker.Document.MIME_TYPE],
            type: doc[google.picker.Document.TYPE],
            url: doc[google.picker.Document.URL],
            iconUrl: doc[google.picker.Document.ICON_URL],
            lastIndexedAt: doc.last_indexed_at || 'N/A'
        }));

        try {
            // Backend API call uses JWT token (handled by makeAuthenticatedRequest)
            const response = await makeAuthenticatedRequest(
                '/api/v1/googledrive/processfilepicker',
                'POST',
                documents
            );

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.msg || 'Failed to process file picker');
            }
            location.reload();
        } catch (error) {
            console.error('Error processing file picker:', error);
        }
    }
}

async function removeDocument(googleDriveId) {
    try {
        const response = await makeAuthenticatedRequest(
            '/api/v1/googledrive/removefile',
            'POST',
            { google_drive_id: googleDriveId }
        );

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.msg || 'Failed to remove document');
        }
        location.reload();
    } catch (error) {
        console.error('Error removing document:', error);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })
    maybeEnableButtons();
});
