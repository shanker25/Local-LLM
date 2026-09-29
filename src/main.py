"""JARVIS - Local LLM assistant.

Milestone 3: persistent conversation memory, multiple sessions,
context trimming. Standard library only.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as either `python -m src.main` or `python src/main.py`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import urllib.error
import urllib.request

from src.history import trim
from src.session_manager import SessionError, SessionManager
from src.store import JsonFileStore, StoreError


# ---- configuration -----------------------------------------------------

def load_env(path: Path = Path(".env")) -> dict:
    """Minimal .env loader (KEY=VALUE, # comments, blank lines ignored)."""
    cfg: dict[str, str] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                cfg[key.strip()] = value.strip()
    return cfg


def get_config() -> dict:
    env = load_env()
    return {
        "MODEL_NAME": env.get("MODEL_NAME", "llama3.2:1b"),
        "OLLAMA_URL": env.get("OLLAMA_URL", "http://localhost:11434"),
        "REQUEST_TIMEOUT": int(env.get("REQUEST_TIMEOUT", "120")),
        "SESSION_DIR": env.get("SESSION_DIR", "data/sessions"),
        "DEFAULT_SESSION": env.get("DEFAULT_SESSION", "default"),
        "MAX_CONTEXT_MESSAGES": int(env.get("MAX_CONTEXT_MESSAGES", "40")),
        "AUTO_RESUME": env.get("AUTO_RESUME", "true").lower() in ("1", "true", "yes"),
    }


SYSTEM_PROMPT = "You are JARVIS, a helpful local assistant."


# ---- ollama ------------------------------------------------------------

def stream_chat(config: dict, messages: list[dict]):
    """POST to Ollama /api/chat and yield content tokens as they arrive."""
    url = f"{config['OLLAMA_URL'].rstrip('/')}/api/chat"
    body = json.dumps(
        {
            "model": config["MODEL_NAME"],
            "messages": messages,
            "stream": True,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=config["REQUEST_TIMEOUT"]) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = chunk.get("message", {}).get("content", "")
            if piece:
                yield piece
            if chunk.get("done"):
                break


# ---- slash commands ----------------------------------------------------

HELP_TEXT = """\
Available commands:
  /clear           Clear messages in the current session (keeps session)
  /new <id>        Create a new session and switch to it
  /switch <id>     Switch to an existing session
  /list            List sessions with message counts (* = active)
  /help            Show this help
  /exit            Quit JARVIS
"""


def handle_command(line: str, sm: SessionManager) -> bool:
    """Handle a slash command. Returns True if the REPL should continue."""
    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/help":
        print(HELP_TEXT)
        return True

    if cmd == "/clear":
        sm.clear()
        print(f"[session '{sm.active_id}' cleared]")
        return True

    if cmd == "/new":
        if not arg:
            print("Usage: /new <id>")
            return True
        try:
            sm.create(arg)
            print(f"[created and switched to '{sm.active_id}']")
        except SessionError as exc:
            print(f"[error] {exc}")
        return True

    if cmd == "/switch":
        if not arg:
            print("Usage: /switch <id>")
            return True
        try:
            sm.switch(arg)
            print(f"[switched to '{sm.active_id}']")
        except SessionError as exc:
            print(f"[error] {exc}")
        return True

    if cmd == "/list":
        rows = sm.list()
        if not rows:
            print("[no sessions]")
        for r in rows:
            marker = "*" if r["active"] else " "
            print(f" {marker} {r['id']:<20} {r['message_count']:>5} messages")
        return True

    if cmd == "/exit":
        return False

    # Unknown slash command: do NOT send to the model.
    print(f"[unknown command: {cmd}]  Type /help for available commands.")
    return True


# ---- repl --------------------------------------------------------------

def run_repl(config: dict, sm: SessionManager) -> None:
    print(f"JARVIS ready. Model: {config['MODEL_NAME']}")
    print(f"Active session: {sm.active_id}")
    print("Type /help for commands, /exit to quit.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            if not handle_command(user_input, sm):
                break
            continue

        # Persist the user turn.
        sm.append("user", user_input)

        # Build trimmed, ts-free payload for Ollama.
        trimmed = trim(
            sm.messages(),
            sm.system_prompt(),
            config["MAX_CONTEXT_MESSAGES"],
        )
        payload = [{"role": m["role"], "content": m["content"]} for m in trimmed]

        print("jarvis> ", end="", flush=True)
        collected: list[str] = []
        try:
            for token in stream_chat(config, payload):
                print(token, end="", flush=True)
                collected.append(token)
        except urllib.error.URLError as exc:
            print(f"\n[network error] {exc}")
            # Roll back the user turn so history stays consistent.
            msgs = sm.messages()
            if msgs and msgs[-1]["role"] == "user":
                msgs.pop()
                sm._current["messages"] = msgs
                sm.store.save(sm.active_id, sm._current)
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"\n[error] {exc}")
            continue

        print()  # newline after stream finishes
        sm.append("assistant", "".join(collected))


# ---- entry point -------------------------------------------------------

def main() -> int:
    config = get_config()

    try:
        store = JsonFileStore(config["SESSION_DIR"])
    except StoreError as exc:
        print(f"[fatal] cannot open session store: {exc}")
        return 1

    try:
        sm = SessionManager(
            store,
            default_session=config["DEFAULT_SESSION"],
            model=config["MODEL_NAME"],
            system_prompt=SYSTEM_PROMPT,
            auto_resume=config["AUTO_RESUME"],
        )
    except SessionError as exc:
        print(f"[fatal] session init failed: {exc}")
        return 1

    run_repl(config, sm)
    return 0


if __name__ == "__main__":
    sys.exit(main())