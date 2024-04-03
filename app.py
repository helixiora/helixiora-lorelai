#!/usr/bin/env python3

"""the main application file for the OAuth2 flow flask app
"""
import json
import os
import sys
import logging
import sqlite3
from contextlib import closing
from typing import Dict
from pprint import pprint

from flask import Flask, redirect, url_for, session, request, render_template, flash, jsonify
from celery import Celery

import google.auth.transport.requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from lorelai.contextretriever import ContextRetriever
from lorelai.llm import Llm

app = Flask(__name__)
app.secret_key = 'your_very_secret_and_long_random_string_here'

app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

def make_celery(appflask: Flask) -> Celery:
    """
    Create and configure a Celery instance for a Flask application.

    Parameters:
    - app: The Flask application instance.

    Returns:
    - Configured Celery instance.
    """
    # Initialize Celery with Flask app's settings
    celery = Celery(appflask.import_name, broker=appflask.config['CELERY_BROKER_URL'])
    celery.conf.update(appflask.config)

    # pylint: disable=R0903
    class ContextTask(celery.Task):
        """
        A Celery Task that ensures the task executes with Flask application context.
        """
        def __call__(self, *args, **kwargs):
            with appflask.app_context():
                return self.run(*args, **kwargs)

    # Setting the custom task class
    celery.Task = ContextTask

    return celery

celeryapp = make_celery(app)

# Allow OAuthlib to use HTTP for local testing only
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Helper function for database connections
def get_db_connection() -> sqlite3.Connection:
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
        raise e

def get_user_details() -> Dict[str, str]:
    """Fetches details of the currently logged-in user from the database.
    Returns:
        A dictionary with user details or an empty dictionary if not found.
    """
    required_keys = ['google_id', 'email']
    if not all(key in session for key in required_keys):
        return {}  # Returns an empty dictionary if required keys are missing

    logging.debug("SESSION: %s", session)
    email = session['email']

    try:
        with get_db_connection() as conn:
            with closing(conn.cursor()) as cursor:
                user_details = cursor.execute("""
                    SELECT u.name, u.email, o.name AS org_name
                    FROM users u
                    INNER JOIN organisations o ON u.org_id = o.id
                    WHERE u.email = ?
                """, (email,)).fetchone()
                if user_details:
                    return {key: user_details[key] for key in ['name', 'email', 'org_name']}
                return {}  # Returns an empty dictionary if no user details are found
    except RuntimeError as e:  # Consider narrowing this to specific exceptions
        logging.error("Failed to fetch user details: %s", e, exc_info=True)
        return {}  # Returns an empty dictionary in case of an exception

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

# Database setup
DATABASE = './userdb.sqlite'

# Database schema
connection = get_db_connection()
if connection:
    cur = connection.cursor()
else:
    raise ConnectionError("Failed to connect to the database.")

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

@celeryapp.task
def execute_rag_llm(chat_message, user, organisation):
    """A Celery task to execute the RAG+LLM model
    """
    print(f"Task ID: {execute_rag_llm.request.id}, Message: {chat_message}")
    print(f"Session: {user}, {organisation}")

    # update the task state before we begin processing
    execute_rag_llm.update_state(state='PROGRESS', meta={'status': 'Processing...'})

    # get the context for the question
    enriched_context = ContextRetriever(org_name=organisation, user=user)

    context, source = enriched_context.retrieve_context(chat_message)

    llm = Llm(model="gpt-3.5-turbo")
    answer = llm.get_answer(question=chat_message, context=context)

    print(f"Answer: {answer}")
    print(f"Source: {source}")

    json_data = {
        'answer': answer,
        'source': source
    }

    return json_data

@app.route('/submit_custom_org', methods=['POST'])
def submit():
    org_name = request.form['org_name']
    session["custom_org"]=org_name
    print("Entered Org Name:", org_name)
    conn = get_db_connection()
    cursor = conn.cursor()
    # create a new organisation if it doesn't exist
    # if it does exist, return it's id
    cursor.execute(("""
            INSERT INTO organisations (name)
            VALUES (?)
            ON CONFLICT (name)
            DO NOTHING;
        """), (org_name,))

    sql = "SELECT id FROM organisations WHERE name = ?;"
    org_id = cursor.execute(sql, (org_name,)).fetchone()[0]
    sql="Update users SET org_id = ? WHERE email = ?"
    cursor.execute(sql,(org_id,session["email"]))
    conn.commit()
    cursor.close()
    conn.close()
    print("updated org name")
    return redirect(url_for("index"))

# Improved index route using render_template
@app.route('/')
def index():
    """the index page

    Returns:
        string: the index page
    """
    if 'google_id' in session:
        #get user org from db
        # Database insert/update
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "SELECT users.user_id,users.org_id, organisations.name FROM users JOIN organisations on users.org_id=organisations.id WHERE email = ?;"
        user_id,ord_id,org_name = cursor.execute(sql, (session['email'],)).fetchone()
        print(user_id,ord_id,org_name)
        if org_name.lower() == "gmail.com":  #checks if domain is gmail.com, if true then proceed to create custom org
            return render_template('index_create_custom_org.html')
        
        user_data = {
            'user_organization': org_name,
            'user_email': session['email'],
        }
        session['organisation']=org_name 
        return render_template('index_logged_in.html', **user_data)

    try:
        authorization_url, state = flow.authorization_url(access_type='offline',
                                                            include_granted_scopes='true')
        session['state'] = state
        return render_template('index.html', auth_url=authorization_url)
    except RuntimeError as e:
        print(f"Error generating authorization URL: {e}")
        return render_template('error.html', error_message="Failed to generate login URL.")

@app.route('/js/<script_name>.js')
def serve_js(script_name):
    """the javascript endpoint
    """
    return render_template(f"js/{script_name}.js"), 200, {'Content-Type': 'application/javascript'}


# a get and post route for the chat page
@app.route('/chat', methods=['POST'])
def chat():
    """the chat route
    """
    content = request.get_json()

    # this is used to post a task to the celery worker
    task = execute_rag_llm.apply_async(args=[content['message'], session['email'],
                                             session['organisation']])

    return jsonify({'task_id': task.id}), 202

@app.route('/chat', methods=['GET'])
def fetch_chat_result():
    """the chat route
    """
    task_id = request.args.get('task_id')
    task = execute_rag_llm.AsyncResult(task_id)
    if task.state == 'SUCCESS':
        return jsonify({'status': 'SUCCESS', 'result': task.result})
    return jsonify({'status': 'PENDING'}), 202

@app.route('/profile')
def profile():
    """the profile page
    """
    if 'google_id' in session:
        # Example: Fetch user details from the database
        user = get_user_details()
        # Assume `get_user_details` returns a dict with user info and credentials
        return render_template('profile.html', user=user)
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
        id_token=credentials.id_token, #pyright: ignore reportAttributeAccessIssue=false
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

    # check if a user with the same email exists
    sql = "SELECT user_id FROM users WHERE email = ?;"
    user_id = cursor.execute(sql, (user_email,)).fetchone()

    if user_id is None:
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
    session['email'] = id_info.get('email')
    session['organisation'] = organisation
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    """the admin page
    """
    if 'google_id' in session:
        return render_template('admin.html')
    return 'You are not logged in!'

@app.route('/admin/pinecone')
def list_indexes():
    """the list indexes page
    """

    enriched_context = ContextRetriever(org_name=session['organisation'], user=session['email'])

    indexes = enriched_context.get_all_indexes()

    pprint(indexes)
    # Render a template, passing the indexes and their metadata
    return render_template('admin/pinecone.html', indexes=indexes)

@app.route('/admin/pinecone/<host_name>')
def index_details(host_name):
    """the index details page
    """
    enriched_context = ContextRetriever(org_name=session['organisation'], user=session['email'])

    # Assume getIndexDetails function exists to fetch metadata for a specific index
    index_metadata = enriched_context.get_index_details(index_host=host_name)

    pprint(index_metadata)

    return render_template('admin/index_details.html', index_host=host_name,
                           metadata=index_metadata)

# Logout route
@app.route('/logout')
def logout():
    """the logout route
    """
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('index'))

# Error handler for 404
@app.errorhandler(404)
def page_not_found(e):
    """the error handler for 404 errors
    """
    return render_template('404.html', e=e), 404

# Error handler for 500
@app.errorhandler(500)
def internal_server_error(e):
    """the error handler for 500 errors
    """
    error_info = sys.exc_info()
    if error_info:
        error_message = str(error_info[1])  # Get the exception message
    else:
        error_message = f"An unknown error occurred. {e}"

    # Pass the error message to the template
    return render_template('500.html', error_message=error_message), 500

if __name__ == '__main__':
    print("Starting the app...")
    app.run(host='localhost', port=5000, use_reloader=True, debug=True)
