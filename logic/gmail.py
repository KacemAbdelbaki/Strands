import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def gmail_get_service():
  """Shows basic usage of the Gmail API.
  Lists the user's Gmail labels.
  """
  creds = None
  if os.path.exists("./credentials/gmail_token.json"):
    creds = Credentials.from_authorized_user_file("./credentials/gmail_token.json", SCOPES)
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "./credentials/gmail_credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    with open("./credentials/gmail_token.json", "w") as token:
      token.write(creds.to_json())

  try:   
    service = build("gmail", "v1", credentials=creds)
    return service

  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")