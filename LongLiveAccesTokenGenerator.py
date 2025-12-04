import requests
import pyperclip  


app_id = "1831253481092784"
app_secret = "dbd63415f07e5c791d9916c571024928"
short_lived_token = "EAAaBgZB079rABQHHCA6zm0wbuAZBENcwDJO6pAVL98e2LoZB6zGiSDZBd1LP2Dh4kNJQkfbsMLNK9CBNkfi9XyaZCmwasxf9KsvuDOChQSQadEPhXRhsOgZCmwQp9CvvAjxhtnb54G04Kz85kTphikZAn9vBGKuMzOVOyt52pJvAjwbIQny3v11Ozd6sulCWnaZA1vWZAz28bfBV4VKWfFWaV5p0R5OqnVZAsioBeXNZBM4ljbZBhthnsGspLUAZAHez3AWX6E4tT5lG7qZB2S2BZCMZBd8v5zWp1ybkShp8DwZDZD"




response1 = requests.get(
    "https://graph.facebook.com/v20.0/oauth/access_token",
    params={
        'grant_type': 'fb_exchange_token',
        'client_id': app_id,
        'client_secret': app_secret,
        'fb_exchange_token': short_lived_token
    }
)
data1 = response1.json()

if 'access_token' not in data1:
    print("Error getting long-lived token:", data1)
    exit()

long_lived_token = data1['access_token']
print("Long-lived user token obtained")

# Step 2 – Get never-expiring Page token + Page ID
response2 = requests.get(
    "https://graph.facebook.com/v20.0/me/accounts",
    params={'access_token': long_lived_token}
)
pages = response2.json()

if 'data' not in pages:
    print("Error fetching pages:", pages)
    exit()

for page in pages['data']:
    print(f"\nPage found → {page['name']} (ID: {page['id']})")
    page_access_token = page['access_token']
    page_id = page['id']

    print("\nFULL PAGE ACCESS TOKEN (copy this):")
    print(page_access_token)
    print("\nPAGE ID:")
    print(page_id)

    pyperclip.copy(page_access_token)
    print("\nFULL Page Access Token has been copied to your clipboard!")

