import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime
import json
import base64

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def gmail_get_service(labels: list[str]=["INBOX"], maxResults: int=5):
  """Shows basic usage of the Gmail API.
  Lists the user's Gmail labels.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("./credentials/gmail_token.json"):
    creds = Credentials.from_authorized_user_file("./credentials/gmail_token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "./credentials/gmail_credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("./credentials/gmail_token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("gmail", "v1", credentials=creds)
    results = (
        service.users().messages().list(
          userId="me", 
          # labelIds=labels, 
          q = "category:primary in:inbox",
          maxResults=maxResults
          ).execute()
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
        print(f'({counter}) {date_str}:\n{msg['snippet']}')
        # file = open("./credentials/gmail_message.json", "w")
        # file.write(json.dumps(msg))
        # file.close()

  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")

if __name__ == "__main__":
    gmail_get_service()