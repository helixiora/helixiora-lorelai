import json
import sqlite3
from flask import blueprints, render_template, session, jsonify, request, redirect, url_for
import google.auth.transport.requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from app.utils import get_db_connection

auth_bp = blueprints.Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        email = session.get('oauth_data', {}).get('email')
        name = session.get('oauth_data', {}).get('name')
        
        return render_template('register.html', email=email, name=name)
    
    # Process the registration form submission
    registration_info = request.form

    # Combine OAuth data with registration form data
    oauth_data = session.pop('oauth_data', {})
    # complete_user_registration(oauth_data, registration_info)
    user_info = process_user(oauth_data, registration_info, credentials)

    logging.info(f"Creating user: {registration_info} / {oauth_data}")


    # Log the user in (pseudo code)
    login_user(oauth_data, registration_info)
    return redirect(url_for('index'))

@auth_bp.route('/oauth2callback')
def oauth_callback():
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
    )    
    
    flow.fetch_token(authorization_response=request.url)

    if not session['state'] == request.args['state']:
        return 'State does not match!', 400

    credentials = flow.credentials
    request_session = google.auth.transport.requests.Request()
    id_info = id_token.verify_oauth2_token(
        id_token=credentials.id_token, #pyright: ignore reportAttributeAccessIssue=false
        request=request_session,
        audience=flow.client_config['client_id']
    )   
    
    print(f"id_info: {id_info}")
    print(f"credentials: {credentials}")
    
    # # Example of processing OAuth callback to get user info
    # user_info = process_user(id_info, credentials)
    
    # print(f"user_info: {user_info}")

    # Check if user exists in your database (pseudo code)
    user_exists = check_user_in_database(id_info['email'])

    if not user_exists:
        # Save the necessary OAuth data in the session to complete registration later
        session['oauth_data'] = id_info
        # Redirect to the registration page
        return redirect(url_for('auth.register'))
    
    # Log the user in (pseudo code)
    login_user(user_info)
    return redirect(url_for('index'))

def login_user(user_info, registration_info):
    print(f"Logging in user: {user_info}")
    print(f"Registration info: {registration_info}")
    # session['user_id'] = user_info['id']
    session['google_id'] = user_info['email']
    session['name'] = user_info['name']
    session['email'] = user_info['email']
    # session['organisation'] = request.form.get['organisation']
    # session['org_id'] = registration_info['org_id']

def check_user_in_database(email):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    return user is not None
    
# def complete_user_registration(oauth_data, registration_info):

#     logging.info(f"Creating user: {registration_info} / {oauth_data}")

#     # Improved method to ensure the database connection is closed properly
#     with get_db_connection() as db:
#         cursor = db.cursor()
#         try:
#             # Your existing database operations here
#             cursor.execute("INSERT OR IGNORE INTO organization (name) VALUES (?)", (registration_info['organization'],))
#             db.commit()

#             cursor.execute("SELECT id FROM organization WHERE name = ?", (registration_info['organization'],))
#             org_id = cursor.fetchone()[0]

#             cursor.execute("INSERT INTO users (email, name, org_id) VALUES (?, ?, ?)", (oauth_data['email'], oauth_data['name'], org_id))
#             db.commit()
#         except sqlite3.Error as error:
#             db.rollback()  # Rollback changes on error
#             # Log the error or handle it as per your application's requirements
#             print(f"An error occurred: {error}")
#         finally:
#             cursor.close()

def process_user(oauth_data, registration_info, credetials):
    """Process the user information obtained from Google."""
    username = oauth_data['name']
    user_email = oauth_data['email']
    organisation = registration_info['organization']
    refresh_token = credentials.refresh_token
    access_token = credentials.token
    expires_in = credentials.expiry.timestamp()  # Assuming you store as a timestamp
    token_type = "Bearer"
    scope = ' '.join(credentials.scopes)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Insert/Get Organisation
        logging.info(f"Organisation: {organisation}")
        cursor.execute("INSERT INTO organisations (name) VALUES (?) ON CONFLICT(name) DO NOTHING;", (organisation,))
        conn.commit()
        cursor.execute("SELECT id FROM organisations WHERE name = ?;", (organisation,))
        org_id = cursor.fetchone()[0]
        
        # Insert/Update User
        cursor.execute("SELECT user_id FROM users WHERE email = ?;", (user_email,))
        user = cursor.fetchone()
        if user:
            cursor.execute("""
                UPDATE users
                SET org_id = ?, name = ?, access_token = ?, refresh_token = ?, expires_in = ?, token_type = ?, scope = ?
                WHERE email = ?;
            """, (org_id, username, access_token, refresh_token, expires_in, token_type, scope, user_email))
        else:
            cursor.execute("""
                INSERT INTO users (org_id, name, email, access_token, refresh_token, expires_in, token_type, scope)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (org_id, username, user_email, access_token, refresh_token, expires_in, token_type, scope))
        conn.commit()

    return {
        'google_id': id_info.get('sub'),
        'name': username,
        'email': user_email,
        'organisation': organisation,
        'org_id': org_id
    }
