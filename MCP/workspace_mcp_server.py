"""Standalone server exposing Google Workspace tools via FastAPI."""

import base64
import os
from typing import Any, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import uvicorn

from logger_utils import logger, log_call
load_dotenv()
SCOPES = [
    "openid",
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
]

creds = Credentials(
    token=os.environ.get("GOOGLE_ACCESS_TOKEN"),
    refresh_token=os.environ.get("GOOGLE_REFRESH_TOKEN"),
    token_uri=os.environ.get("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    scopes=SCOPES,
)

gmail_service = build("gmail", "v1", credentials=creds)
calendar_service = build("calendar", "v3", credentials=creds)

app = FastAPI(title="Workspace MCP Server")

# store last few tool invocations for debugging
tool_history: List[str] = []


@app.get("/tools")
async def list_tools() -> list[dict[str, Any]]:
    """Return the available tools and their schemas."""
    return [
        {
            "name": "list_calendar_events",
            "description": "List upcoming events from Google Calendar.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar identifier. Defaults to 'primary'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to return.",
                    },
                    "time_min": {"type": "string", "description": "ISO start time"},
                    "time_max": {"type": "string", "description": "ISO end time"},
                },
            },
        },
        {
            "name": "create_calendar_event",
            "description": "Create a new Google Calendar event.",
            "inputSchema": {
                "type": "object",
                "required": ["summary", "start", "end"],
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar identifier. Defaults to 'primary'.",
                    },
                    "summary": {"type": "string", "description": "Event summary"},
                    "start": {"type": "string", "description": "ISO start datetime"},
                    "end": {"type": "string", "description": "ISO end datetime"},
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Emails of attendees",
                    },
                },
            },
        },
        {
            "name": "check_day_availability",
            "description": "Return free slots for a specific day.",
            "inputSchema": {
                "type": "object",
                "required": ["date"],
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar identifier. Defaults to 'primary'.",
                    },
                    "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                },
            },
        },
        {
            "name": "list_recent_emails",
            "description": "List snippets of recent Gmail messages matching an optional search query.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail search query. Defaults to 'newer_than:1d'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of messages to return.",
                    },
                },
            },
        },
        {
            "name": "count_emails_by_label",
            "description": "Return the total number of messages with the given Gmail label ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "label_id": {
                        "type": "string",
                        "description": "Label identifier (e.g. INBOX).",
                    }
                },
            },
        },
        {
            "name": "list_gmail_labels",
            "description": "List all Gmail labels for the current user.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "send_email",
            "description": "Send an email using Gmail.",
            "inputSchema": {
                "type": "object",
                "required": ["to", "message"],
                "properties": {
                    "to": {"type": "string", "description": "Recipient address."},
                    "subject": {"type": "string", "description": "Email subject."},
                    "message": {"type": "string", "description": "Email body."},
                },
            },
        },
    ]


@app.post("/call_tool")
async def call_tool(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Invoke a tool by name with the supplied arguments."""
    name = payload.get("name")
    arguments = payload.get("arguments", {}) if isinstance(payload, dict) else {}
    if not name:
        raise HTTPException(status_code=400, detail="Missing 'name' field")

    tool_history.append(f"{name} {arguments}")
    if len(tool_history) > 50:
        tool_history.pop(0)

    if name == "list_calendar_events":
        calendar_id = arguments.get("calendar_id", "primary")
        max_results = int(arguments.get("max_results", 10))
        time_min = arguments.get("time_min")
        time_max = arguments.get("time_max")
        kwargs = {
            "calendarId": calendar_id,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_min:
            kwargs["timeMin"] = time_min
        if time_max:
            kwargs["timeMax"] = time_max
        
        try:
            events_result = calendar_service.events().list(**kwargs).execute()
            events = events_result.get("items", [])
            lines = []
            for event in events:
                start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
                summary = event.get("summary", "(no title)")
                lines.append(f"{start} {summary}")
            text = "\n".join(lines) if lines else "No events found."
            response = {"type": "text", "text": text, "events": events}
        except Exception as e:
            logger.error(f"Error listing calendar events: {e}")
            response = {"type": "text", "text": f"Unable to access calendar. Please check your credentials. Error: {str(e)}"}
        
        log_call(name, arguments, response)
        return response

    if name == "create_calendar_event":
        calendar_id = arguments.get("calendar_id", "primary")
        summary = arguments.get("summary", "")
        start = arguments.get("start")
        end = arguments.get("end")
        attendees = arguments.get("attendees", [])
        if isinstance(attendees, str):
            attendees = [attendees]
        if not start or not end:
            raise HTTPException(status_code=400, detail="Missing start or end")
        body = {
            "summary": summary,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        
        try:
            created = calendar_service.events().insert(calendarId=calendar_id, body=body).execute()
            response = {"type": "text", "text": "Event created.", "id": created.get("id")}
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            response = {"type": "text", "text": f"Unable to create calendar event. Please check your credentials. Error: {str(e)}"}
        
        log_call(name, arguments, response)
        return response

    if name == "check_day_availability":
        calendar_id = arguments.get("calendar_id", "primary")
        date = arguments.get("date")
        if not date:
            raise HTTPException(status_code=400, detail="Missing date")
        start_of_day = f"{date}T00:00:00Z"
        end_of_day = f"{date}T23:59:59Z"
        
        try:
            events_result = calendar_service.events().list(
                calendarId=calendar_id,
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            events = events_result.get("items", [])
            
            if not events:
                response = {"type": "text", "text": "You are free all day on " + date}
                log_call(name, arguments, response)
                return response

            # compute free slots between events
            from datetime import datetime

            fmt = "%Y-%m-%dT%H:%M:%S%z"
            parsed = []
            for ev in events:
                s = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date") + "T00:00:00Z")
                e = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date") + "T00:00:00Z")
                parsed.append((datetime.fromisoformat(s.replace("Z", "+00:00")), datetime.fromisoformat(e.replace("Z", "+00:00")), ev.get("summary", "(No title)")))
            parsed.sort(key=lambda t: t[0])
            day_start = datetime.fromisoformat(start_of_day.replace("Z", "+00:00"))
            day_end = datetime.fromisoformat(end_of_day.replace("Z", "+00:00"))
            
            scheduled_events = []
            for start, end, summary in parsed:
                start_str = start.strftime("%I:%M %p")
                end_str = end.strftime("%I:%M %p")
                scheduled_events.append(f"{start_str} - {end_str}: {summary}")
            
            free_slots = []
            cur = day_start
            for s, e, _ in parsed:
                if s > cur:
                    start_str = cur.strftime("%I:%M %p")
                    end_str = s.strftime("%I:%M %p")
                    free_slots.append(f"{start_str} - {end_str}")
                cur = max(cur, e)
            if cur < day_end:
                start_str = cur.strftime("%I:%M %p")
                end_str = day_end.strftime("%I:%M %p")
                free_slots.append(f"{start_str} - {end_str}")
            
            formatted_date = datetime.fromisoformat(date).strftime("%A, %B %d, %Y")
            text = f"Schedule for {formatted_date}:\n\n"
            text += "Scheduled Events:\n"
            if scheduled_events:
                text += "\n".join(scheduled_events)
            else:
                text += "No scheduled events\n"
            
            text += "\n\nAvailable Time Slots:\n"
            if free_slots:
                text += "\n".join(free_slots)
            else:
                text += "No free time available"
            
            response = {"type": "text", "text": text}
        except Exception as e:
            logger.error(f"Error checking day availability: {e}")
            response = {"type": "text", "text": f"Unable to check calendar availability. Please check your credentials. Error: {str(e)}"}
        
        log_call(name, arguments, response)
        return response


    if name == "list_recent_emails":
        query = arguments.get("query", "newer_than:1d")
        label_ids = arguments.get("label_ids") or []
        if isinstance(label_ids, str):
            label_ids = [label_ids]
        max_results = int(arguments.get("max_results", 10))

        label_map = {
            lbl["id"]: lbl["name"]
            for lbl in gmail_service.users().labels().list(userId="me").execute().get("labels", [])
        }

        collected: list[dict[str, str]] = []
        seen: set[str] = set()
        raw_messages: list[dict[str, Any]] = []
        list_results: list[dict[str, Any]] = []

        def fetch_for_label(lid: str | None) -> None:
            kwargs = {"userId": "me", "q": query, "maxResults": max_results}
            if lid:
                kwargs["labelIds"] = [lid]
            result = gmail_service.users().messages().list(**kwargs).execute()
            list_results.append(result)
            for m in result.get("messages", []):
                if m["id"] not in seen:
                    seen.add(m["id"])
                    collected.append(m)

        if label_ids:
            for lid in label_ids:
                fetch_for_label(lid)
        else:
            fetch_for_label(None)
            
        lines: list[str] = []
        for m in collected:
            msg = (
                gmail_service.users()
                .messages()
                .get(
                    userId="me",
                    id=m["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date"],
                )
                .execute()
            )
            raw_messages.append(msg)
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "(no subject)")
            sender = headers.get("From", "(unknown)")
            date_str = headers.get("Date", "(unknown)")
            snippet = msg.get("snippet", "")
            lbl_names = [label_map.get(lid, lid) for lid in msg.get("labelIds", [])]
            lines.append(
                f"Date: {date_str}\nFrom: {sender}\nSubject: {subject}\nLabels: {', '.join(lbl_names)}\n{snippet}"
            )
        text = "\n\n".join(lines) if lines else "No recent emails found."
        response = {"type": "text", "text": text, "count": len(collected), "messages": raw_messages}
        log_call(f"{name}_raw", arguments, {"list_results": list_results, "messages": raw_messages})
        log_call(name, arguments, response)
        return response

    if name == "count_emails_by_label":
        label_id = arguments.get("label_id", "INBOX")
        info = gmail_service.users().labels().get(userId="me", id=label_id).execute()
        count = info.get("messagesTotal", 0)
        response = {"type": "text", "text": str(count)}
        log_call(name, arguments, response)
        return response

    if name == "list_gmail_labels":
        result = gmail_service.users().labels().list(userId="me").execute()
        labels = result.get("labels", [])
        lines = [f"{lbl['id']}: {lbl['name']}" for lbl in labels]
        text = "\n".join(lines) if lines else "No labels found."
        response = {"type": "text", "text": text}
        log_call(name, arguments, response)
        return response

    if name == "send_email":
        to_addr = arguments.get("to")
        subject = arguments.get("subject", "")
        message = arguments.get("message")
        if not to_addr or not message:
            raise HTTPException(status_code=400, detail="Missing required fields")
        raw = base64.urlsafe_b64encode(
            f"To: {to_addr}\r\nSubject: {subject}\r\n\r\n{message}".encode("utf-8")
        ).decode("utf-8")
        gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
        response = {"type": "text", "text": "Email sent."}
        log_call(name, arguments, response)
        return response

    raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")


@app.get("/dev", response_class=HTMLResponse)
async def dev_page() -> str:
    rows = "\n".join(f"<li>{entry}</li>" for entry in reversed(tool_history))
    return f"<html><body><h1>Recent Tool Calls</h1><ul>{rows}</ul></body></html>"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
