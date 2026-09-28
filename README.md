# JARVIS - Milestone 2: Conversation Memory

A lightweight local AI chatbot that connects a Python application to a local LLM via Ollama. 
This milestone introduces **In-Memory Conversation History**, allowing JARVIS to remember context across multiple turns without needing an external database. Built with **zero dependencies**, using only Python's standard library.

## Features
- **Stateless to Stateful**: Uses Ollama's native `/api/chat` endpoint.
- **In-Memory Storage**: History is maintained as a list of role-based messages (`system`, `user`, `assistant`).
- **Real-time Streaming**: Tokens stream to the console instantly.
- **Clear Memory**: Type `/clear` to start a fresh conversation session.

## Setup
1. Ensure Ollama is installed and running.
2. Pull a local model: `ollama pull llama3.2:1b` (or the model specified in your `.env`)
3. Create a `.env` file (you can copy `.env.example` if available) to configure the model.

## Configuration
The application reads configuration from the `.env` file. You can adjust the `MODEL_NAME`, `OLLAMA_URL`, and `REQUEST_TIMEOUT` there.

## Running the Application
```bash
python src/main.py
```

## Running Tests
```bash
python -m unittest discover tests/
```
