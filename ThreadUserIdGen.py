import requests

ACCESS_TOKEN = ''  # Long-lived token

# Fetch user ID via Threads endpoint (preferred for accuracy)
url = 'https://graph.threads.net/v1.0/me'
params = {
    'fields': 'id,username',
    'access_token': ACCESS_TOKEN
}
response = requests.get(url, params=params)
user_data = response.json()
threads_user_id = user_data['id']  # e.g., '17841401234567890'
print(f"Threads User ID for {user_data.get('username', 'pablo.dev')}: {threads_user_id}")
print(response.json())  # Debug: Check for errors