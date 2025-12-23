import requests
import hashlib
import time
from django.conf import settings

# TikTok Configuration
TIKTOK_ACCESS_TOKEN = "feac57217a5a5e6596ee42683064da0213c0c740"
# Placeholder for Pixel ID - User needs to update this
TIKTOK_PIXEL_ID = "D53J4HRC77U9GK0PCE80" 

def send_tiktok_server_event(event_name, event_data, user, event_id=None, url=None):
    """
    Send server-side event to TikTok Events API.
    
    Args:
        event_name (str): The name of the event (e.g., 'CompletePayment', 'Purchase').
        event_data (dict): Event properties (value, currency, contents, etc.).
        user (CustomUser): The user object to extract email/phone/id.
        event_id (str): Unique event ID for deduplication.
        url (str): The page URL where the event happened.
    """
    if not TIKTOK_ACCESS_TOKEN or TIKTOK_PIXEL_ID == "D53J4HRC77U9GK0PCE80":
        print("TikTok Pixel ID or Access Token not configured correctly.")
        # We proceed anyway in case the user updates the ID later, but usually we might want to return.
        # But if ID is missing, API will fail.
        if TIKTOK_PIXEL_ID == "D53J4HRC77U9GK0PCE80":
             return

    endpoint = "https://business-api.tiktok.com/open_api/v1.3/pixel/track/"
    
    # Hash user data (SHA256)
    # TikTok requires emails/phones to be hashed if not sending plain text (but plain text is usually allowed if sent via secure server, but hashing is best practice)
    # Actually TikTok CAPI docs say: "SHA256 hashed"
    
    email = user.email.lower().strip() if user.email else ""
    phone = user.phone_number.strip() if user.phone_number else ""
    
    user_data = {}
    
    if email:
        hashed_email = hashlib.sha256(email.encode('utf-8')).hexdigest()
        user_data['emails'] = [hashed_email]
        
    if phone:
        # Phone should be E.164 format generally, but we just hash what we have
        hashed_phone = hashlib.sha256(phone.encode('utf-8')).hexdigest()
        user_data['phones'] = [hashed_phone]
        
    if user.id:
        hashed_id = hashlib.sha256(str(user.id).encode('utf-8')).hexdigest()
        user_data['external_ids'] = [hashed_id]
        
    # Basic IP and User Agent from request would be good but we don't have request object here easily unless passed.
    # For now we skip client_ip and client_user_agent, but they are recommended.
    
    payload = {
        "pixel_code": TIKTOK_PIXEL_ID,
        "event": event_name,
        "event_time": int(time.time()),
        "event_id": event_id,
        "user": user_data,
        "properties": event_data,
    }
    
    if url:
        payload["context"] = {
            "page": {
                "url": url
            }
        }
    
    headers = {
        "Access-Token": TIKTOK_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        response_json = response.json()
        if response_json.get("code") != 0:
            print(f"TikTok API Error: {response_json}")
        else:
            print(f"TikTok Event {event_name} sent successfully.")
    except Exception as e:
        print(f"Error sending TikTok event: {e}")
