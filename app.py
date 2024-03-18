from flask import Flask, redirect, url_for, session
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
import os

app = Flask(__name__)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

client_secrets_file = os.path.join(os.path.dirname(__file__), "client_secret.json")

# the current callback registered in the google apps developer console is https://lorelai.helixiora.com, we can change this
flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"],
    # redirect_uri="http://localhost:5000/oauth2callback"
    redirect_uri="https://lorelai.helixiora.com"
)

@app.route('/')
def index():
    authorization_url, state = flow.authorization_url()
    session['state'] = state
    return '<a href="{}">Login with Google</a>'.format(authorization_url)

# not used because the callback doesn't go here
# @app.route('/oauth2callback')
# def callback():
#     flow.fetch_token(authorization_response=request.url)

#     if not session['state'] == request.args['state']:
#         return 'State does not match!', 400

#     credentials = flow.credentials
#     request_session = google.auth.transport.requests.Request()
#     id_info = id_token.verify_oauth2_token(
#         id_token=credentials._id_token,
#         request=request_session,
#         audience=GOOGLE_CLIENT_ID
#     )

#     session['google_id'] = id_info.get('sub')
#     session['name'] = id_info.get('name')
#     return redirect(url_for('profile'))

@app.route('/profile')
def profile():
    if 'google_id' not in session:
        return 'You are not logged in!'
    return 'Hello, {}'.format(session['name'])

if __name__ == '__main__':
    app.run('localhost', 5000)
