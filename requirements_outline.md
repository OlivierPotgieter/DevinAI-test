
---

## 2. `requirements_outline.md`

```md
# Requirements Outline

**Project**: Python-based MCP (Model Content Protocol) Application

## Table of Contents
1. [Introduction](#1-introduction)
2. [Core Objectives](#2-core-objectives)
3. [Feature Requirements](#3-feature-requirements)
4. [Architecture & Design](#4-architecture--design)
5. [Logging & Storage](#5-logging--storage)
6. [Testing & Validation](#6-testing--validation)
7. [Next Steps & Future Considerations](#7-next-steps--future-considerations)

---

## 1. Introduction
The MCP (Model Content Protocol) Application is designed to allow large language models (LLMs) to communicate with external data in a more advanced, context-aware manner. Written in **Python**, it serves as a bridge between user queries and various data sources:

- **Gmail** (with label-awareness and semantic search capabilities)
- **Google Calendar** (for scheduling and availability)
- **Linear** (for issue/task management)
- **Multiple LLM Providers** (OpenAI, Anthropic Claude, Google Gemini, DeepSeek, etc.)

The project also includes a **Python-based GUI**, enabling a user-friendly interface for local usage. All local testing and usage happen on a single developer’s machine.

---

## 2. Core Objectives
1. **Leverage MCP to orchestrate data retrieval** from Gmail, Calendar, and Linear.
2. **Provide semantic understanding** of user commands, responding with relevant results.
3. **Allow switching between LLMs** for flexible experimentation or fallback.
4. **Log and store all requests/responses** to enable auditing and iterative improvements.
5. **Present a GUI** that visually displays email summaries, schedules, tasks, and LLM-driven insights.

---

## 3. Feature Requirements

### 3.1 Gmail Label Awareness
- The application **must** always consider **all Gmail labels** (e.g., Inbox, Sent, “Jeeves,” etc.).
- It should maintain a dynamic sense of which labels contain crucial information and which are typically low-priority.
- When summarizing emails, it should learn to **filter out** repeated automated messages (e.g., from a “Jeeves” label) unless explicitly requested.

### 3.2 Repetitive Email Classification
- The system must identify recurring, unimportant items—like automated reports or spammy newsletters—and reduce their prominence in general summaries.
- Provide a mechanism to override these defaults via the GUI or command-line arguments.

### 3.3 Semantic Search
- On queries (e.g., “Show anything related to downtime”), the system uses **text analysis** to locate relevant emails, tasks, or calendar events—even if the exact word “downtime” isn’t present.
- **MCP** logic should parse synonyms or related phrases.

### 3.4 Multi-LLM Configuration
- Support a **configurable** environment variable or file to select which LLM provider is currently active.
- If a primary LLM fails or returns an error (e.g., rate limit), the system should seamlessly fallback to the next available LLM.

### 3.5 Calendar Integration
- Read the user’s calendar events for upcoming appointments.
- Provide available timeslots for scheduling new meetings.
- Potentially integrate with email or chat to automatically propose meeting invites.

### 3.6 Linear Integration
- Authenticate with Linear (using a token in `.env`).
- Pull in open issues, provide them in summaries, and allow the user to update or create new issues via the GUI or command-based interactions.

### 3.7 Python GUI
- Present a **user-friendly interface** to interact with the system’s features:
  - Email summaries
  - Calendar availability
  - Linear issues
  - LLM selection
  - Logging or settings panel

- The GUI must run locally. It **does not** require a web service or external hosting.
- Must capture user input queries and store them in the logs (see [5. Logging & Storage](#5-logging--storage)).

---

## 4. Architecture & Design
- **Language**: Python (3.9+ recommended).
- **Design Pattern**: Modular, with separate modules for:
  1. **MCP Engine**: Core logic for orchestrating requests and parsing user commands.
  2. **Services**: 
     - `gmail_service.py`
     - `calendar_service.py`
     - `linear_service.py`
     - `llm_service.py` (abstract + concrete provider classes)
  3. **GUI**: 
     - `gui.py` or a dedicated folder containing views, controllers, etc.
- **.env Management**:
  - Auto-generated on first run to store credentials (Gmail API keys, LLM keys, Linear tokens).
  - **Never** commit `.env` to version control.

---

## 5. Logging & Storage
- **Local Logging**: 
  - Store every request/response from the user, from LLMs, and from external APIs.
  - Redact or hash any secret tokens in logs.
  - Support JSON format or another structured format for easy review.
- **Log Location**: A `logs/` directory or user-specified path (configurable in `.env` or a config file).

---

## 6. Testing & Validation
1. **Unit Tests**: 
   - Each service module requires a corresponding test file (e.g., `test_gmail_service.py`) verifying core functionality, including error handling.
   - The MCP engine logic (semantic search, label filtering, fallback logic) must have direct tests proving correctness.
2. **Integration Tests**:
   - Validate the entire flow from user query → searching Gmail + Linear + Calendar → summarizing results → returning a response, all while capturing logs.
   - Mock external services if the environment is offline or credentials are missing.
3. **GUI Tests**:
   - Use a Python GUI testing approach (for example, `pytest-qt` if PyQt is used) to simulate user interactions.
4. **Manual Testing**:
   - Because the app is used locally by a single developer, occasional manual checks can supplement automated tests. This includes verifying:
     - The `.env` file is generated correctly.
     - The logs are being created and updated with correct redactions.
5. **Acceptance Tests**:
   - Real scenarios: 
     - Summarizing the last week’s emails across multiple labels.  
     - Switching LLM providers via the config.  
     - Finding an open slot in Google Calendar for a new meeting.  
     - Creating or updating a Linear issue from the GUI.

---

## 7. Next Steps & Future Considerations
- **Plugin-Based Extensibility**: Consider a plugin-like system to add more data sources or new features (e.g., Slack, Jira, Notion).
- **Shared/Networked Use**: Potentially expand usage beyond the local environment to a small team, requiring a more robust security model.
- **LLM Fine-Tuning**: Explore storing user queries/responses to build custom fine-tuned models or prompts in the future.

---

## Conclusion
This `requirements_outline.md` is **the authoritative guide** for the Python-based MCP application. Every new feature or modification must directly reference and fulfill these requirements. For instructions on how to implement and test these requirements, see [agents.md](./agents.md).
