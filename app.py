from flask import Flask, redirect, url_for, session, request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_very_secret_and_long_random_string_here'

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

client_secrets_file = os.path.join(os.path.dirname(__file__), "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/drive.readonly", "openid"],
    redirect_uri="http://127.0.0.1:5000/oauth2callback"
    # redirect_uri="https://lorelai.helixiora.com"
)

# Database setup
DATABASE = './userdb.sqlite'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# shows a link to lorelai if the user is logged in, otherwise shows a link to login
@app.route('/')
def index():
    if 'google_id' in session:
        name = session['name']
        return f"Hello, {name}. <a href=""lorelai.helixiora.com"">Go to Lorelai</a>"
    else:
        authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
        session['state'] = state
        return '<a href="{}">Login with Google</a>'.format(authorization_url)

@app.route('/oauth2callback')
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session['state'] == request.args['state']:
        return 'State does not match!', 400

    credentials = flow.credentials
    request_session = google.auth.transport.requests.Request()
    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=request_session,
        audience=flow.client_config['client_id']
    )

    print(f"CREDS: {credentials}")    
    print(f"ID: {id_info}")
    
    # Here, 'sub' is used as the user ID. Depending on your application, you might use a different identifier
    user_id = id_info.get('sub')
    username = id_info.get('name')
    user_email = id_info.get('email')
   
    # Database insert/update
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS user_tokens (
        user_id TEXT PRIMARY KEY,
        access_token TEXT,
        refresh_token TEXT,
        expires_in INTEGER,
        token_type TEXT,
        scope TEXT
    )''')
    
    cur.execute(("""
        INSERT INTO users (id, name, email)
        VALUES (?, ?, ?)
        ON CONFLICT (id)
        DO UPDATE SET email = EXCLUDED.email, name = EXCLUDED.name;
    """), (user_id, username, user_email))

    cur.execute('''
        INSERT INTO user_tokens (user_id, access_token, refresh_token, expires_in, token_type, scope) 
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
        access_token=excluded.access_token,
        refresh_token=excluded.refresh_token,
        expires_in=excluded.expires_in,
        token_type=excluded.token_type,
        scope=excluded.scope;
        ''', (
        user_id,
        credentials.token,
        credentials.refresh_token,
        credentials.expiry,
        "Bearer",
        ' '.join(credentials.scopes)
    ))
    conn.commit()
    cur.close()
    conn.close()

    session['google_id'] = id_info.get('sub')
    session['name'] = id_info.get('name')
    return redirect(url_for('profile'))

@app.route('/profile')
def profile():
    if 'google_id' in session:
        name = session['name']
        return f'Hello, {session}. <a href="lorelai.helixiora.com">Go to Lorelai</a>'
    else:
        return 'You are not logged in!'

if __name__ == '__main__':
    app.run('localhost', 5000)
