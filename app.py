"""the main application file for the OAuth2 flow flask app
"""
import json
import os
from pprint import pprint
import sqlite3
from flask import Flask, redirect, url_for, session, request, render_template, flash

from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests

app = Flask(__name__)
app.secret_key = 'your_very_secret_and_long_random_string_here'

# Allow OAuthlib to use HTTP for local testing only
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Helper function for database connections
def get_db_connection() -> sqlite3.Connection | None:
    """Get a database connection

    Returns:
        conn: a connection to the database
    """
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection failed: {e}")
        return None

def get_user_details():
    """Fetches details of the currently logged-in user from the database.

    Returns:
        A dictionary with user details or None if not found.
    """
    if 'google_id' not in session:
        return None

    google_id = session['google_id']

    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
        else:
            raise Exception("Failed to connect to the database.")

        user_details = cursor.execute("""
            SELECT u.name, u.email, o.name AS org_name
            FROM users u
            INNER JOIN organisations o ON u.org_id = o.id
            WHERE u.google_id = ?
        """, (google_id,)).fetchone()

        if user_details:
            # Convert the row to a dictionary
            details = {
                'name': user_details['name'],
                'email': user_details['email'],
                'org_name': user_details['org_name']
            }
            return details
    except Exception as e:
        print(f"Failed to fetch user details: {e}")
        return None
    finally:
        if conn:
            conn.close()

# Load the Google OAuth2 secrets
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
if connection:
    cur = connection.cursor()
else:
    raise Exception("Failed to connect to the database.")

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

# Improved index route using render_template
@app.route('/')
def index():
    """the index page

    Returns:
        string: the index page
    """
    if 'google_id' in session:
        name = session['name']
        return render_template('index_logged_in.html', name=name)
    else:
        try:
            authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
            session['state'] = state
            return render_template('index.html', auth_url=authorization_url)
        except Exception as e:
            print(f"Error generating authorization URL: {e}")
            return render_template('error.html', error_message="Failed to generate login URL.")

@app.route('/profile')
def profile():
    if 'google_id' in session:
        # Example: Fetch user details from the database
        user = get_user_details()
        # Assume `get_user_details` returns a dict with user info and credentials
        return render_template('profile.html', user=user)
    else:
        return 'You are not logged in!'

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
        id_token=credentials.id_token, #pylint: disable=no-member
        request=request_session,
        audience=flow.client_config['client_id']
    )

    pprint(f"CREDS: {credentials}")
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

    sql = "SELECT id FROM organisations WHERE name = ?;"
    org_id = cursor.execute(sql, (organisation,)).fetchone()[0]

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
    return redirect(url_for('index'))

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('index'))

# Error handler for 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Error handler for 500
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run('localhost', 5000)
