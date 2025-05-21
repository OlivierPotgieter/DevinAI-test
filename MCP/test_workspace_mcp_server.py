import asyncio
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Provide a minimal dotenv stub so the module can import without the package
dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Stub google API modules used by workspace_mcp_server
google_stub = types.ModuleType("google")
oauth2_stub = types.ModuleType("oauth2")
creds_stub = types.ModuleType("credentials")


class Credentials:
    def __init__(self, *a, **k):
        pass


creds_stub.Credentials = Credentials
oauth2_stub.credentials = creds_stub
google_stub.oauth2 = oauth2_stub
discovery_stub = types.ModuleType("discovery")
discovery_stub.build = lambda *a, **k: MagicMock()
googleapiclient_stub = types.ModuleType("googleapiclient")
googleapiclient_stub.discovery = discovery_stub
sys.modules.setdefault("google", google_stub)
sys.modules.setdefault("google.oauth2", oauth2_stub)
sys.modules.setdefault("google.oauth2.credentials", creds_stub)
sys.modules.setdefault("googleapiclient", googleapiclient_stub)
sys.modules.setdefault("googleapiclient.discovery", discovery_stub)

import workspace_mcp_server as server


class TestWorkspaceMcpServer(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.object(server, "gmail_service")
        self.mock_service = self.patcher.start()
        self.cal_patcher = patch.object(server, "calendar_service")
        self.mock_calendar = self.cal_patcher.start()

        mock_users = MagicMock()
        self.mock_service.users.return_value = mock_users

        mock_labels = MagicMock()
        mock_labels.list.return_value.execute.return_value = {
            "labels": [{"id": "INBOX", "name": "Inbox"}]
        }
        mock_users.labels.return_value = mock_labels

        mock_messages = MagicMock()
        mock_messages.list.return_value.execute.return_value = {
            "messages": [{"id": "1"}]
        }
        msg_data = {
            "id": "1",
            "labelIds": ["INBOX"],
            "snippet": "hello",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test"},
                    {"name": "From", "value": "a@example.com"},
                    {"name": "Date", "value": "Mon, 19 May 2025 10:00:00 +0000"},
                ]
            },
        }
        mock_messages.get.return_value.execute.return_value = msg_data
        mock_users.messages.return_value = mock_messages

        mock_events = MagicMock()
        mock_events.list.return_value.execute.return_value = {
            "items": [
                {
                    "summary": "Meeting",
                    "start": {"dateTime": "2025-05-19T10:00:00Z"},
                    "end": {"dateTime": "2025-05-19T11:00:00Z"},
                }
            ]
        }
        mock_events.insert.return_value.execute.return_value = {"id": "abc"}
        self.mock_calendar.events.return_value = mock_events

    def tearDown(self):
        self.patcher.stop()
        self.cal_patcher.stop()

    def test_list_recent_emails_returns_raw_messages(self):
        payload = {
            "name": "list_recent_emails",
            "arguments": {"query": "test", "max_results": 1},
        }
        resp = asyncio.run(server.call_tool(payload))
        self.assertIn("messages", resp)
        self.assertEqual(resp["messages"][0]["id"], "1")
        self.assertIn("Date:", resp["text"])

    def test_list_calendar_events(self):
        payload = {"name": "list_calendar_events", "arguments": {"max_results": 1}}
        resp = asyncio.run(server.call_tool(payload))
        self.assertIn("events", resp)
        self.assertEqual(len(resp["events"]), 1)

    def test_create_calendar_event(self):
        payload = {
            "name": "create_calendar_event",
            "arguments": {
                "summary": "Meet",
                "start": "2025-05-19T10:00:00Z",
                "end": "2025-05-19T11:00:00Z",
            },
        }
        resp = asyncio.run(server.call_tool(payload))
        self.assertEqual(resp["text"], "Event created.")

    def test_check_day_availability_free(self):
        self.mock_calendar.events.return_value.list.return_value.execute.return_value = {
            "items": []
        }
        payload = {
            "name": "check_day_availability",
            "arguments": {"date": "2025-05-19"},
        }
        resp = asyncio.run(server.call_tool(payload))
        self.assertEqual(resp["text"], "Free all day")


if __name__ == "__main__":
    unittest.main()
