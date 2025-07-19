import requests
import os
from dotenv import load_dotenv
import time

load_dotenv()

def get_headers():
    """Load the latest ACCESS_TOKEN from environment and return headers dict."""
    load_dotenv()
    token = os.getenv('ACCESS_TOKEN')
    return {'Authorization': f'Bearer {token}'}


def refresh_token():
    load_dotenv()
    refresh_token_val = os.getenv('REFRESH_TOKEN')
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    response = requests.post('https://www.strava.com/oauth/token', data={
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token_val,
        'grant_type': 'refresh_token'
    })
    token_data = response.json()
    # Update env file and in-memory env vars
    os.environ['ACCESS_TOKEN'] = token_data['access_token']
    os.environ['REFRESH_TOKEN'] = token_data['refresh_token']
    with open('.env', 'w') as f:
        f.write(f"CLIENT_ID={client_id}\n")
        f.write(f"CLIENT_SECRET={client_secret}\n")
        f.write(f"ACCESS_TOKEN={token_data['access_token']}\n")
        f.write(f"REFRESH_TOKEN={token_data['refresh_token']}\n")
    return token_data['access_token']


def get_recent_runs(after_days=7, fetch_latest_only=False):
    try:
        if fetch_latest_only:
            params = {'per_page': 1}
        else:
            after_timestamp = int(time.time() - after_days * 86400)
            params = {'per_page': 10, 'after': after_timestamp}
        headers = get_headers()
        response = requests.get('https://www.strava.com/api/v3/athlete/activities', headers=headers, params=params)
        if response.status_code == 401:
            refresh_token()
            headers = get_headers()
            response = requests.get('https://www.strava.com/api/v3/athlete/activities', headers=headers, params=params)
        response.raise_for_status()
        activities = response.json()
        runs = [act for act in activities if act['type'] == 'Run']
        if fetch_latest_only and not runs:
            return get_recent_runs(after_days=after_days)
        return runs
    except requests.exceptions.RequestException as e:
        return []


def get_activity_streams(activity_id):
    try:
        # Add 'distance' to the requested stream keys
        params = {'keys': 'time,distance,velocity_smooth,heartrate', 'key_by_type': True}
        headers = get_headers()
        response = requests.get(f'https://www.strava.com/api/v3/activities/{activity_id}/streams', headers=headers, params=params)
        if response.status_code == 401:
            refresh_token()
            headers = get_headers()
            response = requests.get(f'https://www.strava.com/api/v3/activities/{activity_id}/streams', headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        return {} 