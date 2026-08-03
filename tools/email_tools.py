import base64
from datetime import datetime
from strands import tool
from logic.gmail import gmail_get_service

@tool
def get_emails(q: str, maxResult: int):
    service = gmail_get_service()
    results = (
        service.users().messages().list(userId="me", q=q, maxResults=maxResult).execute()
    )
    messages = results.get("messages", [])

    if not messages:
        return

    emails = []
    for counter, message in enumerate(messages):
        msg = (service.users().messages().get(userId="me", id=message["id"]).execute())
        date_str = datetime.fromtimestamp(int(msg['internalDate']) / 1000.0).strftime('%Y-%m-%d %H:%M:%S')

        payload = msg.get("payload", {})
        body_data = ""
        
        if "data" in payload.get("body", {}):
            body_data = payload["body"]["data"]
        elif "parts" in payload:
            for part in payload["parts"]:
                if "data" in part.get("body", {}):
                    body_data = part["body"]["data"]
                    break
                    
        if body_data:
            coded_body = base64.urlsafe_b64decode(body_data) 
            decoded_body = coded_body.decode("utf-8", errors="ignore")
            msg["decoded_body"] = decoded_body
        else:
            msg["decoded_body"] = None

        emails.append([msg, date_str])
    
    return emails
