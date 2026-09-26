import datetime
import os
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json
from config import (
    CREDENTIALS_FILE, TOKEN_FILE, GOOGLE_CALENDAR_ID, TIMEZONE,
    GOOGLE_CREDENTIALS_JSON, GOOGLE_TOKEN_JSON
)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Google Calendar Color IDs (Available for events):
# 1  : Lavender (Pale Blue)
# 2  : Sage (Pale Green)
# 3  : Grape (Purple)
# 4  : Flamingo (Pink)
# 5  : Banana (Yellow)
# 6  : Tangerine (Orange)
# 7  : Peacock (Light Blue)
# 8  : Graphite (Gray)
# 9  : Blueberry (Blue)
# 10 : Basil (Green)
# 11 : Tomato (Red)


def get_calendar_service():
    """Create connection to Google Calendar using OAuth 2.0"""
    creds = None
    
    # 1. Try loading token from Env Var (JSON content)
    if GOOGLE_TOKEN_JSON:
        try:
            token_info = json.loads(GOOGLE_TOKEN_JSON)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except json.JSONDecodeError:
            print("Error: GOOGLE_TOKEN_JSON is not valid JSON.")
    
    # 2. Try loading token from File
    if not creds and os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            pass
    
    # If no valid token, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                creds = None

        if not creds:
            # Need to login. Check for Client Config (Credentials)
            client_config = None
            
            # A. Try Env Var for Credentials
            if GOOGLE_CREDENTIALS_JSON:
                try:
                    client_config = json.loads(GOOGLE_CREDENTIALS_JSON)
                except json.JSONDecodeError:
                    print("Error: GOOGLE_CREDENTIALS_JSON is not valid JSON.")

            # B. Try File for Credentials
            if not client_config and os.path.exists(CREDENTIALS_FILE):
                # We can't easily load client config locally without flow, 
                # but InstalledAppFlow handles files directly.
                pass
            
            if not client_config and not os.path.exists(CREDENTIALS_FILE):
                 raise FileNotFoundError("Candidates for credentials not found (Env Var or File).")

            # New login flow
            if client_config:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                
            creds = flow.run_local_server(port=0)
        
        # Save the token?
        # If we are using Env Vars, we can't save back to Env Var.
        # But we can try saving to file if path is robust.
        try:
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        except Exception:
            # If we can't write to file (e.g. read-only system), we just use the token in memory
            # The user will need to update the Env Var manually with the new token if it changed.
            pass
    
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def add_event(summary: str, start_time: str, end_time: Optional[str] = None,
              reminders: list = None, description: str = None, color_id: str = None) -> dict:
    """Add a new event to the calendar"""
    service = get_calendar_service()

    if not end_time:
        start_dt = datetime.datetime.fromisoformat(start_time)
        end_dt = start_dt + datetime.timedelta(hours=2)
        end_time = end_dt.isoformat()

    if not reminders:
        reminders = [5, 15, 1440]  # 5 mins before, 15 mins before, 1 day before
    
    # Limit to 5 reminders max
    reminders = reminders[:5]
    
    reminder_overrides = [{"method": "popup", "minutes": int(m)} for m in reminders]
    
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_time, "timeZone": TIMEZONE},
        "end": {"dateTime": end_time, "timeZone": TIMEZONE},
        "reminders": {
            "useDefault": False,
            "overrides": reminder_overrides,
        },
    }

    if color_id:
        event["colorId"] = color_id

    created_event = service.events().insert(
        calendarId=GOOGLE_CALENDAR_ID, body=event
    ).execute()

    return created_event


def find_event(keyword: str) -> Optional[dict]:
    """Find an event by keyword using fuzzy matching"""
    service = get_calendar_service()

    # Search in near future and recent past (wider range for better matching)
    time_min = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).isoformat() + "Z"
    time_max = (datetime.datetime.utcnow() + datetime.timedelta(days=120)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    if not events:
        return None

    # Use fuzzy matching on the summaries
    from thefuzz import process
    summaries = [e.get("summary", "") for e in events if e.get("summary")]
    
    if not summaries:
        return None
        
    best_match = process.extractOne(keyword, summaries, score_cutoff=60)
    
    if best_match:
        match_summary = best_match[0]
        # Find the event object with this summary
        for e in events:
            if e.get("summary") == match_summary:
                return e
                
    return None


def delete_event(keyword: str) -> str:
    """Delete an event based on a keyword"""
    event = find_event(keyword)
    if not event:
        return f"❌ لم أجد حدثاً بكلمة '{keyword}'"

    service = get_calendar_service()
    service.events().delete(
        calendarId=GOOGLE_CALENDAR_ID, eventId=event["id"]
    ).execute()

    return f"✅ تم حذف '{event.get('summary', 'بدون عنوان')}' بنجاح"


def reschedule_event(keyword: str, new_start_time: Optional[str] = None,
                     shift_minutes: int = 0) -> str:
    """Reschedule an event to a new time"""
    event = find_event(keyword)
    if not event:
        return f"❌ لم أجد حدثاً بكلمة '{keyword}'"

    service = get_calendar_service()

    current_start = event["start"].get("dateTime", event["start"].get("date"))
    current_end = event["end"].get("dateTime", event["end"].get("date"))

    if new_start_time:
        # Specific new time
        start_dt = datetime.datetime.fromisoformat(new_start_time)
        try:
            old_start_dt = datetime.datetime.fromisoformat(current_start.replace("Z", ""))
            old_end_dt = datetime.datetime.fromisoformat(current_end.replace("Z", ""))
        except ValueError:
             return "❌ عذراً، لا يمكنني تعديل الأحداث اليومية الكاملة (All-day events) حالياً."

        duration = old_end_dt - old_start_dt
        end_dt = start_dt + duration
    else:
        # Shift by minutes
        old_start_dt = datetime.datetime.fromisoformat(current_start.replace("Z", ""))
        old_end_dt = datetime.datetime.fromisoformat(current_end.replace("Z", ""))
        delta = datetime.timedelta(minutes=shift_minutes)
        start_dt = old_start_dt + delta
        end_dt = old_end_dt + delta

    event["start"]["dateTime"] = start_dt.isoformat()
    event["end"]["dateTime"] = end_dt.isoformat()

    updated_event = service.events().patch(
        calendarId=GOOGLE_CALENDAR_ID, eventId=event["id"], body=event
    ).execute()

    return f"✅ تم ترحيل '{updated_event.get('summary', 'بدون عنوان')}' إلى {start_dt.strftime('%Y-%m-%d %H:%M')}"


def update_event(keyword: str, new_summary: Optional[str] = None,
                 new_description: Optional[str] = None) -> str:
    """Update event details"""
    event = find_event(keyword)
    if not event:
        return f"❌ لم أجد حدثاً بكلمة '{keyword}'"

    service = get_calendar_service()
    if new_summary:
        event["summary"] = new_summary
    if new_description:
        event["description"] = new_description

    updated = service.events().patch(
        calendarId=GOOGLE_CALENDAR_ID, eventId=event["id"], body=event
    ).execute()

    return f"✅ تم تعديل الحدث إلى '{updated.get('summary', 'بدون عنوان')}'"


def check_conflicts(start_time: str, end_time: str) -> list:
    """Check for conflicts with existing events"""
    service = get_calendar_service()

    events_result = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        timeMin=start_time + "Z" if not start_time.endswith("Z") else start_time,
        timeMax=end_time + "Z" if not end_time.endswith("Z") else end_time,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])


def get_today_events() -> list:
    """Get all events for today"""
    service = get_calendar_service()

    import pytz
    cairo_tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(cairo_tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    events_result = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])
