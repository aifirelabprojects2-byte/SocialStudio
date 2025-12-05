# SocialStudio

## Run FastAPI: 
```bash
uvicorn main:app --reload 
```
## Run Celery Worker:
```bash
celery -A celery_app worker --loglevel=info --pool=solo
``` 

# Generate Thread User ID 

`Run ThreadUserIdGEn.py with help of long-lived access tokens for Threads Testers `


# Generate Facebook Page Access Token:

`https://graph.facebook.com/v24.0/me/accounts?access_token=YOUR_CURRENT_USER_TOKEN_HERE `