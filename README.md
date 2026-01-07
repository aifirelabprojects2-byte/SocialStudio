# SocialStudio

## Run FastAPI: 
```bash
uvicorn main:app --reload 
```
## Run Celery Worker:
```bash
celery -A celery_app worker --loglevel=info --pool=eventlet
``` 
## Use the solo pool which doesn't require monkey patching
```bash
celery -A celery_app worker --loglevel=info --pool=solo
``` 

# Generate Thread User ID 

`Run ThreadUserIdGEn.py with help of long-lived access tokens for Threads Testers `

# Generate Facebook User Access Token
Get a Short-Lived Token: Go to the Graph API Explorer. Select your App, click "Generate Access Token," and grant the necessary permissions.

Exchange for Long-Lived: Use the Access Token Debugger. Paste your short-lived token and click "Extend Access Token" at the bottom
https://developers.facebook.com/tools/debug/accesstoken/


# Generate Facebook Page Access Token

`https://graph.facebook.com/v24.0/me/accounts?access_token=YOUR_CURRENT_USER_TOKEN_HERE `

# To Get Instagram Account ID

`curl -i -X GET "https://graph.facebook.com/v21.0/me?fields=instagram_business_account&access_token=YOUR_PAGE_TOKEN"`
