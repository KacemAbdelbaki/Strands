import base64
import html
import re
from datetime import datetime

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from strands import tool

from logic.gmail import gmail_get_service

_MAX_BODY_CHARS = 2_000
_MAX_RESULTS_LIMIT = 20


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")


def _find_part(payload: dict, mime_type: str) -> str | None:
    """Depth-first search of a MIME tree for the first part of the given type."""
    if payload.get("mimeType") == mime_type and "data" in payload.get("body", {}):
        return _decode(payload["body"]["data"])
    for part in payload.get("parts", []):
        found = _find_part(part, mime_type)
        if found:
            return found
    return None


def _extract_body(payload: dict) -> str:
    """Return the plain-text body, falling back to tag-stripped HTML."""
    text = _find_part(payload, "text/plain")
    if text is None:
        raw_html = _find_part(payload, "text/html")
        if raw_html is None:
            return ""
        raw_html = re.sub(r"(?is)<(script|style).*?</\1>", "", raw_html)
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_BODY_CHARS]


@tool
def get_emails(query: str = "in:inbox category:primary", max_results: int = 5) -> list[dict] | str:
    """Search the user's Gmail mailbox (read-only).

    Args:
        query: Gmail search query. Combine terms with spaces (AND) or OR. Supported operators:
            status (in:, is:, category:, label:), addresses (from:, to:, cc:, bcc:, deliveredto:, list:),
            dates (after:, before:, newer:, older:, newer_than:, older_than:),
            content (subject:, has:, filename:), size (larger:, smaller:, size:),
            modifiers ("..." or + for exact match, - to exclude, {} to group OR terms).
            Example: "from:boss@example.com is:unread newer_than:7d".
        max_results: Maximum number of emails to return (1-20).

    Returns:
        A list of emails with id, date, from, to, subject, snippet and a truncated body,
        or a message if nothing matched or the request failed.
    """
    max_results = max(1, min(max_results, _MAX_RESULTS_LIMIT))
    try:
        service = gmail_get_service()
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No emails matched the query."

        emails = []
        for message in messages:
            msg = service.users().messages().get(userId="me", id=message["id"]).execute()
            payload = msg.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            emails.append({
                "id": msg["id"],
                "date": datetime.fromtimestamp(int(msg["internalDate"]) / 1000.0).strftime("%Y-%m-%d %H:%M:%S"),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "subject": headers.get("subject", ""),
                "snippet": html.unescape(msg.get("snippet", "")),
                "body": _extract_body(payload),
            })
        return emails
    except RefreshError:
        return (
            "Gmail authorisation has expired or was revoked. Ask the user to delete "
            "credentials/gmail_token.json and sign in again."
        )
    except HttpError as error:
        return f"Gmail API error: {error}"
