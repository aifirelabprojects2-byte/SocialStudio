import asyncio
import httpx

async def post_to_linkedin(access_token: str, person_urn: str, text: str):
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202501"  # Use latest YYYYMM format (check docs for current)
    }
    payload = {
        "author": person_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            post_id = response.headers.get("x-restli-id")
            print(f"Posted successfully! Post ID: {post_id}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
            response.raise_for_status()
            
