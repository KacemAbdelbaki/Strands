import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from strands_assistant.logic.gcalendar import SCOPES as CALENDAR_SCOPES
from strands_assistant.logic.gmail import SCOPES as GMAIL_SCOPES
from strands_assistant.settings import CREDENTIALS_DIR


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"gmail", "calendar"}:
        raise SystemExit("Usage: python -m strands_assistant.google_login gmail|calendar")

    service = sys.argv[1]
    scopes = GMAIL_SCOPES if service == "gmail" else CALENDAR_SCOPES
    credentials_path = CREDENTIALS_DIR / f"{service}_credentials.json"
    token_path = CREDENTIALS_DIR / f"{service}_token.json"
    if not credentials_path.exists():
        raise SystemExit(f"OAuth client file not found: {credentials_path}")

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    credentials = flow.run_local_server(port=0)
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Saved {service} token to {token_path}")


if __name__ == "__main__":
    main()
