const SCOPES = 'https://www.googleapis.com/auth/drive.file';


let codeClient;

let authorizationCode = null;
let pickerInited = false;
let gisInited = false;

document.getElementById('authorize_button').disabled = true;
document.getElementById('signout_button').disabled = true;
document.getElementById('select_button').disabled = true;

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
        if (accessToken) {
            document.getElementById('authorize_button').innerText = 'Refresh';
            document.getElementById('signout_button').disabled = false;
            document.getElementById('select_button').disabled = false;
        } else {
            document.getElementById('authorize_button').innerText = 'Authorize';
            document.getElementById('signout_button').disabled = true;
            document.getElementById('select_button').disabled = true;
        }
    }
}

function handleSignoutClick() {
    if (accessToken) {
        google.accounts.oauth2.revoke(accessToken);
        accessToken = null;
        maybeEnableButtons();
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
            lastIndexedAt: doc.last_indexed_at || 'N/A'  // Assuming last_indexed_at might not be available
        }));

        try {
            const response = await fetch('/google/drive/processfilepicker', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(documents),
            });

            if (response.ok) {
                // If the request is successful, reload the page
                location.reload();
            } else {
                console.error('Failed to process file picker:', response.statusText);
            }
        } catch (error) {
            console.error('Error processing file picker:', error);
        }
    }
}


async function removeDocument(googleDriveId) {
    await fetch('/google/drive/removefile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ google_drive_id: googleDriveId }),
    }).catch(console.error)
    .then(() => location.reload());
}

document.addEventListener('DOMContentLoaded', function () {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })
    maybeEnableButtons();
});
