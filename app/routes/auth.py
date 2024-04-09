import json
import sqlite3
from flask import blueprints, render_template, session, jsonify, request, redirect, url_for
import google.auth.transport.requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from app.utils import get_db_connection, is_admin

auth_bp = blueprints.Blueprint('auth', __name__)

@auth_bp.route('/profile')
def profile():
    """the profile page
    """
    if 'google_id' in session:
        # Example: Fetch user details from the database
        user = {
            'name': session['name'],
            'email': session['email'],
            'organisation': session['organisation']
        }
        return render_template('profile.html', user=user, is_admin=is_admin(session['google_id']))
    return 'You are not logged in!'


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
    
    print(f"Registration info: {registration_info}")
    print(f"OAuth data: {oauth_data}")
    
    username = registration_info['name']
    user_email = registration_info['email']
    organisation = registration_info['organisation']
    
    access_token = session.pop('access_token', None)
    refresh_token = session.pop('refresh_token', None)
    expires_in = session.pop('expires_in', None)
    token_type = session.pop('token_type', None)
    scope = session.pop('scope', None)
    user_info = process_user(organisation, username, user_email, access_token, refresh_token, expires_in, token_type, scope)

    # logging.info(f"Creating user: {registration_info} / {oauth_data}")

    # Log the user in (pseudo code)
    login_user(user_info['name'], user_info['email'], user_info['org_id'], user_info['organisation'])
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
    userid, name, orgid, organisation = check_user_in_database(id_info['email'])
    email = id_info['email']

    if not userid:
        # Save the necessary OAuth data in the session to complete registration later
        
        session['access_token'] = credentials.token 
        session['refresh_token'] = credentials.refresh_token
        session['expires_in'] = credentials.expiry
        session['token_type'] = 'Bearer'
        session['scope'] = credentials.scopes
    
        session['oauth_data'] = id_info
        # Redirect to the registration page
        return redirect(url_for('auth.register'))
    
    # Log the user in 
    login_user(name, email, orgid, organisation)
    return redirect(url_for('index'))

def login_user(name: str, email: str, org_id: int, organisation: str) -> None:
    session['google_id'] = email
    session['name'] = name
    session['email'] = email
    session['org_id'] = org_id
    session['organisation'] = organisation

def check_user_in_database(email: str) -> tuple(int, str, int, str):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT user_id, users.name, org_id, organisations.name FROM users LEFT JOIN organisations ON users.org_id = organisations.id WHERE email = ?", (email,))
    user = cursor.fetchone()
    user_id = user[0] if user else None
    name = user[1] if user else None
    org_id = user[2] if user else None
    organisation = user[3] if user else None
    return user_id, name, org_id, organisation

def process_user(organisation: str, username: str, user_email: str, access_token: str, refresh_token: str, expires_in: str, token_type: str, scope: list) -> dict:
    """Process the user information obtained from Google."""

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Insert/Get Organisation
        cursor.execute("INSERT INTO organisations (name) VALUES (?) ON CONFLICT(name) DO NOTHING;", (organisation,))
        conn.commit()
        cursor.execute("SELECT id FROM organisations WHERE name = ?;", (organisation,))
        org_id = cursor.fetchone()[0]
        scope_str = ' '.join(scope)
        
        # Insert/Update User
        cursor.execute("SELECT user_id FROM users WHERE email = ?;", (user_email,))
        user = cursor.fetchone()
        if user:
            cursor.execute("""
                UPDATE users
                SET org_id = ?, name = ?, access_token = ?, refresh_token = ?, expires_in = ?, token_type = ?, scope = ?
                WHERE email = ?;
            """, (org_id, username, access_token, refresh_token, expires_in, token_type, scope_str, user_email))
        else:
            cursor.execute("""
                INSERT INTO users (org_id, name, email, access_token, refresh_token, expires_in, token_type, scope)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (org_id, username, user_email, access_token, refresh_token, expires_in, token_type, scope_str))
        conn.commit()

    return {
        'name': username,
        'email': user_email,
        'organisation': organisation,
        'org_id': org_id
    }
