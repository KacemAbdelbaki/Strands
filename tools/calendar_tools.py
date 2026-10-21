import html
import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from strands import tool
from strands_tools.utils.user_input import get_user_input

from logic.gcalendar import calendar_get_service

_MAX_RESULTS_LIMIT = 50
_AUTH_ERROR = (
    "Google Calendar authorisation has expired or was revoked. Ask the user to delete "
    "credentials/calendar_token.json and sign in again."
)


def _event_time(value: str, timezone: str) -> dict:
    """Turn "YYYY-MM-DD" (all-day) or "YYYY-MM-DDTHH:MM" into a Calendar API start/end object."""
    if "T" in value:
        return {"dateTime": datetime.fromisoformat(value).replace(tzinfo=None).isoformat(), "timeZone": timezone}
    return {"date": date.fromisoformat(value).isoformat()}


@tool
def get_events(start_date: str = "", days: int = 7, query: str = "", max_results: int = 20) -> list[dict] | str:
    """List events from the user's primary Google Calendar.

    Args:
        start_date: First day to list, as "YYYY-MM-DD". Empty means today.
        days: Number of days to cover from start_date (1 for a single day).
        query: Optional free-text search over event titles, descriptions, locations and attendees.
        max_results: Maximum number of events to return (1-50).

    Returns:
        A list of events with id, summary, start, end and location, in the calendar's timezone,
        or a message if nothing matched or the request failed.
    """
    max_results = max(1, min(max_results, _MAX_RESULTS_LIMIT))
    try:
        service = calendar_get_service()
        timezone = service.calendars().get(calendarId="primary").execute()["timeZone"]
        tz = ZoneInfo(timezone)
        first_day = date.fromisoformat(start_date) if start_date else datetime.now(tz).date()
        time_min = datetime.combine(first_day, time.min, tz)
        time_max = time_min + timedelta(days=max(1, days))

        params = {
            "calendarId": "primary",
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        if query:
            params["q"] = query
        events = service.events().list(**params).execute().get("items", [])
        if not events:
            return f"No events between {time_min:%Y-%m-%d} and {time_max:%Y-%m-%d} ({timezone})."

        return [
            {
                "id": event["id"],
                "summary": event.get("summary", "(no title)"),
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "location": event.get("location", ""),
            }
            for event in events
        ]
    except ValueError as error:
        return f"Invalid date: {error}. Use YYYY-MM-DD."
    except RefreshError:
        return _AUTH_ERROR
    except HttpError as error:
        return f"Google Calendar API error: {error}"


@tool
def create_event(summary: str, start: str, end: str, location: str = "", description: str = "") -> str:
    """Add an event to the user's primary Google Calendar after the user approves it.

    Times are in the calendar's own timezone. Use "YYYY-MM-DDTHH:MM" for a timed event,
    or "YYYY-MM-DD" for an all-day event (the end date is exclusive: a one-day event on
    2026-03-10 ends on 2026-03-11).

    Args:
        summary: Event title.
        start: Start, as "YYYY-MM-DDTHH:MM" or "YYYY-MM-DD".
        end: End, in the same format as start.
        location: Optional location.
        description: Optional notes.

    Returns:
        A confirmation with the event link, or a message if the user declined or the request failed.
    """
    if os.getenv("BYPASS_TOOL_CONSENT", "").lower() != "true":
        # get_user_input renders the prompt as prompt_toolkit HTML, so escape the event details
        answer = get_user_input(f"Create event: {html.escape(summary)} ({html.escape(start)} → {html.escape(end)}) [y/N]", default="n")
        if answer.strip().lower() not in ("y", "yes"):
            return "The user declined to create this event."
    try:
        service = calendar_get_service()
        timezone = service.calendars().get(calendarId="primary").execute()["timeZone"]
        body = {
            "summary": summary,
            "start": _event_time(start, timezone),
            "end": _event_time(end, timezone),
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        event = service.events().insert(calendarId="primary", body=body).execute()
        return f"Event created: {event.get('summary')} ({start} → {end}, {timezone}). Link: {event.get('htmlLink')}"
    except ValueError as error:
        return f"Invalid date: {error}. Use YYYY-MM-DDTHH:MM or YYYY-MM-DD."
    except RefreshError:
        return _AUTH_ERROR
    except HttpError as error:
        return f"Google Calendar API error: {error}"
