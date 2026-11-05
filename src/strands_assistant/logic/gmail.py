from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from strands_assistant.settings import CREDENTIALS_DIR

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def gmail_get_service():
    """Return an authorised Gmail API client using an existing token."""
    creds = None
    token = CREDENTIALS_DIR / "gmail_token.json"
    client_secrets = CREDENTIALS_DIR / "gmail_credentials.json"
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError(
                f"Not signed in to Gmail. Run `python -m strands_assistant.google_login gmail` "
                f"after adding {client_secrets}."
            )
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)