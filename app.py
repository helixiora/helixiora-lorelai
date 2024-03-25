"""the main application file for the OAuth2 flow flask app
"""
import json
import os
import sqlite3
from flask import Flask, redirect, url_for, session, request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests

def get_db_connection():
    """returns a connection to the database

    Returns:
        conn: the connection to the database
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

app = Flask(__name__)
app.secret_key = 'your_very_secret_and_long_random_string_here'

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

with open('settings.json', encoding='utf-8') as f:
    secrets = json.load(f)['google']

client_config = {
    "web": {
        "client_id": secrets['client_id'],
        "project_id": secrets['project_id'],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": secrets['client_secret'],
        "redirect_uris": secrets['redirect_uris'],
    }
}

flow = Flow.from_client_config(
    client_config=client_config,
    scopes=["https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/drive.readonly",
            "openid"],
    redirect_uri="http://127.0.0.1:5000/oauth2callback"
    # redirect_uri="https://lorelai.helixiora.com"
)

# Database setup
DATABASE = './userdb.sqlite'

# Database schema
connection = get_db_connection()
cur = connection.cursor()

# make sure the organisation table exists
cur.execute('''CREATE TABLE IF NOT EXISTS organisations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)''')

# make sure the users table exists
cur.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER,
    name TEXT,
    email TEXT,
    access_token TEXT,
    refresh_token TEXT,
    expires_in INTEGER,
    token_type TEXT,
    scope TEXT
)''')

connection.commit()
cur.close()
connection.close()

# shows a link to lorelai if the user is logged in, otherwise shows a link to login
@app.route('/')
def index():
    """the index page

    Returns:
        string: the index page
    """
    if 'google_id' in session:
        name = session['name']
        return f"Hello, {name}. <a href=""lorelai.helixiora.com"">Go to Lorelai</a>"

    authorization_url, state = flow.authorization_url(access_type='offline',
                                                        include_granted_scopes='true')
    session['state'] = state
    return f'<a href="{authorization_url}">Login with Google</a>'

@app.route('/oauth2callback')
def callback():
    """the callback function for the OAuth2 flow

    Returns:
        redirect: redirects to the profile page
    """

    flow.fetch_token(authorization_response=request.url)

    if not session['state'] == request.args['state']:
        return 'State does not match!', 400

    credentials = flow.credentials
    request_session = google.auth.transport.requests.Request()
    id_info = id_token.verify_oauth2_token(
        id_token=credentials.id_token,
        request=request_session,
        audience=flow.client_config['client_id']
    )

    print(f"CREDS: {credentials}")
    print(f"ID: {id_info}")

    # Here, 'sub' is used as the user ID. Depending on your application, you might use a different
    # identifier
    # user_id = id_info.get('sub')
    username = id_info.get('name')
    user_email = id_info.get('email')
    organisation = id_info.get('email').split('@')[1]

    # Database insert/update
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"ORG: {organisation}")

    # create a new organisation if it doesn't exist
    # if it does exist, return it's id
    cursor.execute(("""
        INSERT INTO organisations (name)
        VALUES (?)
        ON CONFLICT (name)
        DO NOTHING;
    """), (organisation,))
    conn.commit()

    org_id = cursor.execute("SELECT id FROM organisations WHERE name = ?;", (organisation,)).fetchone()[0]
    conn.commit()

    cursor.execute(("""
        INSERT INTO users (
            org_id, 
            name,
            email,
            access_token,
            refresh_token,
            expires_in,
            token_type,
            scope)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """), (
        org_id,
        username,
        user_email,
        credentials.token,
        credentials.refresh_token,
        credentials.expiry,
        "Bearer",
        ' '.join(str(credentials.scopes))
    ))

    conn.commit()
    cursor.close()
    conn.close()

    session['google_id'] = id_info.get('sub')
    session['name'] = id_info.get('name')
    return redirect(url_for('profile'))

@app.route('/profile')
def profile():
    """the profile page

    Returns:
        string: the profile page
    """
    if 'google_id' in session:
        name = session['name']
        return f'Hello, {name}. <a href="lorelai.helixiora.com">Go to Lorelai</a>'
    else:
        return 'You are not logged in!'

if __name__ == '__main__':
    app.run('localhost', 5000)
