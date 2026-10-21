import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Read and write events on the user's calendars, plus read-only calendar metadata
# (calendars.get, used for the calendar's timezone, isn't covered by the events scopes)
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.owned",
    "https://www.googleapis.com/auth/calendar.calendars.readonly",
]

# Must be a "Desktop app" OAuth client: run_local_server redirects to localhost on a random port
_CLIENT_SECRETS = "./credentials/calendar_credentials.json"
_TOKEN = "./credentials/calendar_token.json"


def calendar_get_service():
    """Return an authorised Google Calendar API client, signing in through the browser if needed."""
    creds = None
    if os.path.exists(_TOKEN):
        creds = Credentials.from_authorized_user_file(_TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)
