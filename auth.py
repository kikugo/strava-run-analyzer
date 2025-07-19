import requests
import webbrowser
import os
from dotenv import load_dotenv, set_key

load_dotenv()
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = 'http://localhost'

# Step 1: Open authorization URL with proper scope
scope = 'read,activity:read_all'
auth_url = (
    f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope={scope}"
    f"&approval_prompt=force"
)
print("Opening browser for authorization (approval_prompt=force)...")
webbrowser.open(auth_url)

# Step 2: User pastes the code from the redirect URL
code = input("Enter the 'code' from the URL after authorizing (e.g., from ?code=abc123): ").strip()

# Step 3: Exchange code for tokens
token_response = requests.post('https://www.strava.com/oauth/token', data={
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'code': code,
    'grant_type': 'authorization_code'
}).json()
print("Full Token Response:", token_response)  # Debug print

if 'access_token' in token_response:
    set_key('.env', 'ACCESS_TOKEN', token_response['access_token'])
    set_key('.env', 'REFRESH_TOKEN', token_response['refresh_token'])
    print("Tokens updated successfully! New Access Token:", token_response['access_token'])
    granted_scope = token_response.get('scope', 'N/A')
    print("Granted Scope:", granted_scope)
    if 'activity:read_all' not in granted_scope:
        print("WARNING: Missing 'activity:read_all' scope. Please re-authorize and ensure you approve all permissions.")
else:
    print("Error getting tokens:", token_response) 