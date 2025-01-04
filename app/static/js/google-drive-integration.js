const SCOPES = 'https://www.googleapis.com/auth/drive.file';

let codeClient;
let authorizationCode = null;
let pickerInited = false;
let gisInited = false;

document.getElementById('authorize_button').disabled = true;

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
        // Check if we have a google_drive_access_token in the page data
        const hasGoogleDriveAccess = typeof google_drive_access_token !== 'undefined' && google_drive_access_token !== null;

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

function handleSignoutClick() {
    if (accessToken) {
        makeAuthenticatedRequest('/api/v1/googledrive/revoke', 'POST')
            .then(async response => {
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.msg || 'Revoke failed');
                }
                google.accounts.oauth2.revoke(accessToken);
                accessToken = null;
                google_drive_access_token = null;
                maybeEnableButtons();
            })
            .catch(error => {
                console.error('Signout error:', error);
            });
    }
}

async function createPicker() {
    const shareddrivesview = new google.picker.DocsView(google.picker.ViewId.DOCS)
        .setEnableDrives(true)
        // .setMimeTypes('application/vnd.google-apps.document', 'application/vnd.google-apps.folder', 'application/vnd.google-apps.spreadsheet', 'application/vnd.google-apps.presentation')
        .setSelectFolderEnabled(true)
        .setOwnedByMe(false)
        .setIncludeFolders(true); // creates just the shared drives view

    const sharedwithmeview = new google.picker.DocsView(google.picker.ViewId.DOCS)
        // .setMimeTypes('application/vnd.google-apps.document', 'application/vnd.google-apps.folder', 'application/vnd.google-apps.spreadsheet', 'application/vnd.google-apps.presentation')
        .setSelectFolderEnabled(true)
        .setIncludeFolders(true)
        .setOwnedByMe(false); // creates just the shared with me view

    const mydriveview = new google.picker.DocsView(google.picker.ViewId.DOCS)
        // .setMimeTypes('application/vnd.google-apps.document', 'application/vnd.google-apps.folder', 'application/vnd.google-apps.spreadsheet', 'application/vnd.google-apps.presentation')
        .setSelectFolderEnabled(true)
        .setOwnedByMe(true)
        .setParent('root')
        .setIncludeFolders(true); // creates just the my drive view

    const picker = new google.picker.PickerBuilder()
        .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
        .enableFeature(google.picker.Feature.SUPPORT_DRIVES)
        .disableFeature(google.picker.Feature.MINE_ONLY)
        .setDeveloperKey(API_KEY)
        .setAppId(APP_ID)
        .setOAuthToken(accessToken)
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
