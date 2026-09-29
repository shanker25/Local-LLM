# JARVIS

A local, privacy-first AI assistant built on top of [Ollama](https://ollama.com).
Written in pure Python using only the standard library — no third-party
dependencies, no cloud services, no telemetry.

JARVIS remembers your conversations across restarts, keeps separate named
sessions, and streams responses token-by-token from a model running entirely
on your machine.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Slash Commands](#slash-commands)
- [Storage](#storage)
- [Context Trimming](#context-trimming)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Design Principles](#design-principles)
- [Roadmap](#roadmap)
- [Non-Goals](#non-goals)
- [License](#license)

---

## Overview

JARVIS is a minimal, educational local-LLM client. It connects a Python REPL
to a locally-hosted Ollama model over HTTP, streams responses to the terminal,
and persists every conversation to disk.

It was built incrementally across three milestones:

| Milestone | Delivered |
|-----------|-----------|
| **M1** | Python ⇄ Ollama connectivity via `/api/chat` |
| **M2** | In-memory conversation history, streaming output, `/clear` |
| **M3** | Persistent JSON storage, multiple named sessions, automatic session resume, context-window trimming |

The design prioritizes **readability**, **modularity**, and **zero external
dependencies** over feature breadth.

---

## Features

- **Persistent memory** — conversations survive application restarts.
- **Multiple named sessions** — independent histories (`default`, `work`,
  `research`, …) that you can create, switch between, and clear.
- **Automatic session resume** — JARVIS reopens the last active session on
  startup.
- **Context-window trimming** — only the system prompt plus the most recent
  `MAX_CONTEXT_MESSAGES` messages are sent to the model. The full transcript
  remains on disk.
- **Streaming responses** — tokens are printed to the console as they arrive.
- **Graceful failure** — corrupt session files are backed up and replaced
  without crashing the application.
- **Zero dependencies** — standard library only. No `pip install` required.

---

## Requirements

- **Python** 3.10 or newer
- **[Ollama](https://ollama.com)** installed and running locally
- At least one pulled model, for example:

  ```bash
  ollama pull llama3.2:1b
Installation
Clone the repository

bash
git clone https://github.com/shanker25/Local-LLM.git
cd Local-LLM
Create your environment file

bash
cp .env.example .env
Edit .env if you want a different model, URL, session directory, or
context limit. Defaults work out of the box.

Start JARVIS

bash
python src/main.py
Both invocation styles are supported:

bash
python src/main.py       # direct
python -m src.main       # as a module
No virtual environment is required since there are no dependencies. If you
prefer one anyway, create and activate it as usual.

Configuration
Configuration is read from .env at the project root. Every key has a
sensible default, so an empty or missing .env still works.

Key	Default	Description
MODEL_NAME	llama3.2:1b	Ollama model to use
OLLAMA_URL	http://localhost:11434	Ollama server base URL
REQUEST_TIMEOUT	120	HTTP request timeout (seconds)
SESSION_DIR	data/sessions	Directory for session JSON files
DEFAULT_SESSION	default	Session created/loaded on first run
MAX_CONTEXT_MESSAGES	40	Max non-system messages sent to the model
AUTO_RESUME	true	Resume last active session on startup
The real .env is gitignored. Only .env.example is committed.

Usage
Start the assistant:

bash
python src/main.py
On startup you'll see:

text
JARVIS ready. Model: llama3.2:1b
Active session: default
Type /help for commands, /exit to quit.
Type a message and press Enter. Responses stream in token-by-token. Every
message — user and assistant — is written to disk immediately, so quitting at
any time loses nothing.

A short example
text
you> explain quicksort in one sentence
jarvis> Quicksort is a divide-and-conquer sorting algorithm that picks a
pivot, partitions the array around it, and recursively sorts the two halves.

you> /new algorithms
[created and switched to 'algorithms']

you> what did I ask you before?
jarvis> You asked me to explain quicksort in one sentence.
Slash Commands
Command	Description
/clear	Clear messages in the current session (keeps the session and its metadata)
/new <id>	Create a new session and switch to it immediately
/switch <id>	Switch to an existing session
/list	List all sessions with message counts; * marks the active one
/help	Show the command reference
/exit	Quit JARVIS
Anything starting with / that isn't recognized prints a hint and is never
sent to the model.

Session ID rules: lowercase letters, digits, _, and - only, matching
[a-z0-9_-]+.

Storage
Sessions are stored as individual JSON files under SESSION_DIR (default
data/sessions/):

text
data/
└── sessions/
    ├── index.json      # active session pointer + session summaries
    ├── default.json    # one file per session
    ├── work.json
    └── research.json
Each session file has this shape:

json
{
  "session_id": "default",
  "created_at": "2026-09-29T10:00:00+00:00",
  "updated_at": "2026-09-29T11:42:13+00:00",
  "model": "llama3.2:1b",
  "system_prompt": "You are JARVIS, a helpful local assistant.",
  "messages": [
    {
      "role": "user",
      "content": "hello",
      "ts": "2026-09-29T10:00:05+00:00"
    },
    {
      "role": "assistant",
      "content": "Hi!",
      "ts": "2026-09-29T10:00:06+00:00"
    }
  ]
}
Metadata vs. payload
The ts, created_at, and updated_at fields are storage metadata.
Only role and content are sent to Ollama on each request.

Atomic writes
Every save writes to a temporary file first and then renames it over the
target with os.replace(). A crash mid-write cannot leave a partially
written session file.

Corruption recovery
If a session file cannot be parsed as JSON, JARVIS:

Copies the file to <name>.json.bak — nothing is lost.

Prints a warning to the console.

Starts a fresh session under the same id.

The application never crashes because of a bad session file.

Privacy
The entire data/ directory is gitignored. Your conversation history never
leaves your machine and is never committed.

Context Trimming
LLMs have a fixed context window. To stay inside it — and to keep each
request fast and cheap — JARVIS trims the outbound payload before every call:

text
[system prompt] + [last MAX_CONTEXT_MESSAGES non-system messages]
The system prompt is always preserved as the first message. The full
transcript stays on disk regardless. Trimming affects only what is sent to
the model, never what is remembered.

To observe it in action, set a small value in .env:

text
MAX_CONTEXT_MESSAGES=5
Have a 20-turn conversation, restart, and ask "what did we talk about
earlier?" — you'll see the model only has access to the most recent turns.

Architecture
JARVIS is a small layered application. Each layer has one job and one reason
to change.

text
┌──────────────────────────────────────────────┐
│                  main.py                     │
│  REPL loop · slash commands · Ollama client  │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│             SessionManager                   │
│  Active session · create/switch/list/delete  │
│  Append messages · clear · index tracking    │
└────────┬─────────────────────────┬───────────┘
         │                         │
         ▼                         ▼
┌────────────────────┐   ┌─────────────────────┐
│  ConversationStore │   │      history.py     │
│  (interface)       │   │  trim(messages, …)  │
└─────────┬──────────┘   └─────────────────────┘
          │
          ▼
┌────────────────────┐
│   JsonFileStore    │
│  Atomic writes     │
│  index.json        │
│  <id>.json         │
└────────────────────┘
main.py — owns the REPL, parses slash commands, streams from Ollama,
and orchestrates the turn. It never touches disk directly.

SessionManager — owns session identity and lifecycle. Knows which
session is active. Delegates all persistence to the store.

ConversationStore / JsonFileStore — persistence behind a small
interface. Swapping in a SQLite or vector backend later requires no changes
above this layer.

history.py — pure functions for context-window management. No I/O.

Project Structure
text
Local-LLM/
├── data/                       # gitignored — created at runtime
│   └── sessions/
│       ├── index.json
│       └── <session>.json
├── src/
│   ├── main.py                 # REPL, slash commands, Ollama client
│   ├── store.py                # ConversationStore, JsonFileStore
│   ├── session_manager.py      # SessionManager
│   └── history.py              # history.trim()
├── tests/
│   ├── test_store.py
│   ├── test_history.py
│   └── test_session_manager.py
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
Testing
JARVIS is tested with the standard library's unittest. No pytest, no
plugins, no extra tooling.

bash
python -m unittest discover tests/
The suite covers:

test_store.py — save/load round-trip, automatic directory creation,
atomic writes, missing files, corrupt-JSON recovery, delete, index
persistence.

test_history.py — system-prompt preservation, latest-message
retention, maximum-count enforcement, non-mutation of inputs,
max_messages <= 0 behavior.

test_session_manager.py — create, load, switch, list, delete, append,
clear, active-session persistence across restarts, corrupt-file fallback.

All tests run in under a second and use temporary directories — nothing
touches your real data/ folder.

Design Principles
Zero dependencies. Only the Python standard library is used. Nothing
to install, nothing to audit, nothing to break.

Small, layered modules. Each file has one responsibility. Persistence,
session logic, and context management never leak into each other.

Interfaces over implementations. ConversationStore is an abstract
base class so alternative backends can be added without touching
main.py.

Fail soft. A corrupt file, a missing session, or a network error
produces a warning — not a crash.

Data is local. Conversations never leave the machine and are never
committed to version control.

Metadata stays separate from payload. Timestamps are for storage and
listing; only role and content reach the model.

Roadmap
Planned for future milestones (not yet implemented):

M4 — Retrieval-augmented generation (RAG) with local embeddings.

M5 — Optional SQLite backend behind the same ConversationStore
interface.

M6 — Turn summarization for very long conversations.

M7 — Lightweight terminal UI (still stdlib only, e.g. curses).

See the commit history for milestone-by-milestone progress.

Non-Goals
JARVIS is deliberately not:

a cloud service or SaaS product

a multi-user or multi-tenant system

a web or mobile application

an agent framework or tool-use orchestrator

an encrypted or access-controlled store

a wrapper around third-party LLM SDKs

These are out of scope by design. The project favors clarity and smallness
over breadth.