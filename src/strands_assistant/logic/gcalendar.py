from strands_assistant.settings import CREDENTIALS_DIR

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Read and write events on the user's calendars, plus read-only calendar metadata
# (calendars.get, used for the calendar's timezone, isn't covered by the events scopes)
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.owned",
    "https://www.googleapis.com/auth/calendar.calendars.readonly",
]

# Must be a "Desktop app" OAuth client: run_local_server redirects to localhost on a random port
def calendar_get_service():
    """Return an authorised Google Calendar API client, signing in through the browser if needed."""
    creds = None
    token = CREDENTIALS_DIR / "calendar_token.json"
    client_secrets = CREDENTIALS_DIR / "calendar_credentials.json"
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError(
                f"Not signed in to Google Calendar. Run `python -m strands_assistant.google_login calendar` "
                f"after adding {client_secrets}."
            )
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)
