
Small demo project for experimenting with Google Workspace APIs and OpenAI.

## Directory layout

- **MCP/main.py** - Interactive CLI that automatically launches the workspace
  server and provides helper commands.
- **MCP/workspace_mcp_server.py** - FastAPI server that exposes Gmail and
  Calendar tools.
- **MCP/email_insights_agent.py** - CLI script that fetches recent email
  snippets and asks OpenAI questions about them.
- **MCP/llm_email_summary.py** - Standalone version of the email summariser.
- **MCP/logger_utils.py** - Shared utility that writes API requests and
  responses to `MCP/app.log`.

All requests sent to Google Workspace or OpenAI are logged, along with the
server's responses. Logs are appended to `MCP/app.log`.

Run `python MCP/main.py` to launch the CLI. The workspace server starts
automatically, and you can view its recent output via the "Show recent server
log" menu option.
