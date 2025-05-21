import csv
import os
import pydoc
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from llm_service import get_service
from logger_utils import log_call

MCP_DIR = Path(__file__).parent

# Load environment variables from a .env file if present
load_dotenv()

SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
LABEL_CSV = MCP_DIR / "gmail_labels.csv"


def start_server() -> subprocess.Popen:
    """Launch workspace_mcp_server.py as a subprocess."""
    server_path = MCP_DIR / "workspace_mcp_server.py"
    return subprocess.Popen(
        ["python", str(server_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=MCP_DIR,
    )


def stream_output(proc: subprocess.Popen, buffer: list[str]) -> None:
    """Read server output and store it without printing."""
    assert proc.stdout is not None
    for line in proc.stdout:
        buffer.append(line)


def load_important_label_ids() -> list[str]:
    """Return Gmail label IDs marked as important in the CSV file."""
    if not LABEL_CSV.exists():
        return []
    ids: list[str] = []
    with LABEL_CSV.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("important", "").lower() == "true":
                ids.append(row["id"])
    return ids


def run_summary(query: str, question: str) -> None:
    """Run the email_insights_agent script with the given parameters."""
    labels = load_important_label_ids()
    script = MCP_DIR / "email_insights_agent.py"
    cmd = ["python", str(script), "--query", query]
    if labels:
        cmd += ["--labels", ",".join(labels)]
    cmd.append(question)
    print(f"Running summary with query: {query}")
    subprocess.run(cmd, cwd=MCP_DIR)


def count_emails(label_id: str) -> None:
    url = f"{SERVER_URL}/call_tool"
    payload = {"name": "count_emails_by_label", "arguments": {"label_id": label_id}}
    try:
        resp = requests.post(url, json=payload, timeout=30)
        log_call("count_emails_by_label", payload, resp.text)
        resp.raise_for_status()
        data = resp.json()
        print(f"Total emails with label '{label_id}': {data.get('text')}")
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")


def list_labels() -> dict[str, str]:
    """Return a mapping of Gmail label IDs to names and display them."""
    url = f"{SERVER_URL}/call_tool"
    payload = {"name": "list_gmail_labels", "arguments": {}}
    try:
        resp = requests.post(url, json=payload, timeout=30)
        log_call("list_gmail_labels", payload, resp.text)
        resp.raise_for_status()
        text = resp.json().get("text", "")
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")
        return {}
    lines = text.splitlines()
    mapping: dict[str, str] = {}
    for line in lines:
        if ":" in line:
            label_id, name = line.split(":", 1)
            mapping[label_id.strip()] = name.strip()
    if lines:
        pydoc.pager("\n".join(lines))
    else:
        print("No labels found.")
    return mapping


def choose_label() -> str | None:
    """Prompt user to choose a Gmail label by ID or name."""
    labels = list_labels()
    if not labels:
        return None
    while True:
        answer = input("Label ID or name (default INBOX): ").strip()
        if not answer:
            answer = "INBOX"
        for lid, name in labels.items():
            if answer == lid or answer.lower() == name.lower():
                return lid
        print("Label not found, please try again.")


def sync_labels_csv() -> None:
    """Fetch Gmail labels and save them to a CSV with an importance flag."""
    mapping = list_labels()
    if not mapping:
        return
    labels = [{"id": lid, "name": name} for lid, name in mapping.items()]
    for lbl in labels:
        ans = input(f"Mark '{lbl['name']}' as important? [y/N]: ").strip().lower()
        lbl["important"] = "True" if ans in ("y", "yes") else "False"
    with LABEL_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "name", "important"])
        writer.writeheader()
        writer.writerows(labels)
    print(f"Saved {len(labels)} labels to {LABEL_CSV}")


def list_next_week_events() -> None:
    """Print upcoming events for the next 7 days."""
    start = datetime.utcnow()
    end = start + timedelta(days=7)
    url = f"{SERVER_URL}/call_tool"
    payload = {
        "name": "list_calendar_events",
        "arguments": {
            "time_min": start.isoformat() + "Z",
            "time_max": end.isoformat() + "Z",
            "max_results": 20,
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        log_call("list_calendar_events", payload, resp.text)
        resp.raise_for_status()
        print(resp.json().get("text", "No events."))
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")


def create_calendar_event() -> None:
    """Interactively create a calendar event."""
    summary = input("Event summary: ").strip()
    start = input("Start datetime (ISO): ").strip()
    end = input("End datetime (ISO): ").strip()
    attendees_str = input("Attendee emails (comma separated, optional): ").strip()
    attendees = [a.strip() for a in attendees_str.split(",") if a.strip()]
    url = f"{SERVER_URL}/call_tool"
    payload = {
        "name": "create_calendar_event",
        "arguments": {
            "summary": summary,
            "start": start,
            "end": end,
            "attendees": attendees,
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        log_call("create_calendar_event", payload, resp.text)
        resp.raise_for_status()
        print(resp.json().get("text", ""))
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")


def check_day_availability() -> None:
    """Check free slots for a given day."""
    date_str = input("Date (YYYY-MM-DD): ").strip()
    url = f"{SERVER_URL}/call_tool"
    payload = {
        "name": "check_day_availability",
        "arguments": {"date": date_str},
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        log_call("check_day_availability", payload, resp.text)
        resp.raise_for_status()
        print(resp.json().get("text", ""))
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")


def test_credentials() -> None:
    """Attempt to refresh OAuth credentials loaded from the environment."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    scopes = [
        "openid",
        "https://mail.google.com/",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/userinfo.email",
    ]

    creds = Credentials(
        token=os.environ.get("GOOGLE_ACCESS_TOKEN"),
        refresh_token=os.environ.get("GOOGLE_REFRESH_TOKEN"),
        token_uri=os.environ.get(
            "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"
        ),
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=scopes,
    )

    try:
        creds.refresh(Request())
    except Exception as exc:  # pragma: no cover - manual utility
        print(f"Credentials refresh failed: {exc}")
    else:  # pragma: no cover - manual utility
        print("Credentials refresh succeeded.")


def main() -> None:
    """Start the server and present the interactive menu."""
    output_lines: list[str] = []
    server_proc = start_server()
    t = threading.Thread(
        target=stream_output, args=(server_proc, output_lines), daemon=True
    )
    t.start()

    while True:
        print(
            "\nOptions:\n"
            "1. Summarize last week's emails\n"
            "2. Review a specific day\n"
            "3. Count emails by label\n"
            "4. Sync label CSV\n"
            "5. List Gmail labels\n"
            "6. Show recent server log\n"
            "7. Test credentials\n"
            "8. List next week's events\n"
            "9. Create calendar event\n"
            "10. Check day availability\n"
            "11. Quit"
        )
        choice = input("Select: ").strip()

        if choice == "1":
            run_summary(
                "newer_than:7d",
                "Summarize the last week's emails with important highlights and stats.",
            )
        elif choice == "2":
            date_str = input("Enter date (YYYY-MM-DD): ").strip()
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                print("Invalid date format.")
                continue
            next_day = date + timedelta(days=1)
            query = f"after:{date.strftime('%Y/%m/%d')} before:{next_day.strftime('%Y/%m/%d')}"
            run_summary(query, f"Summarize all emails from {date_str} in detail.")
        elif choice == "3":
            label = choose_label()
            if label:
                count_emails(label)
        elif choice == "4":
            sync_labels_csv()
        elif choice == "5":
            list_labels()
        elif choice == "6":
            print("\n--- Server Output (last 20 lines) ---")
            for line in output_lines[-20:]:
                print(line, end="")
            print("--- End Output ---\n")
        elif choice == "7":
            test_credentials()
        elif choice == "8":
            list_next_week_events()
        elif choice == "9":
            create_calendar_event()
        elif choice == "10":
            check_day_availability()
        elif choice == "11":
            break
        else:
            print("Invalid option.")

    server_proc.terminate()
    server_proc.wait()


if __name__ == "__main__":
    main()
