# JARVIS - Milestone 1

A minimal local AI chatbot that connects a Python application to a local LLM via Ollama. 
This milestone is designed with **zero dependencies**, using only Python's standard library.

## Setup
1. Ensure Ollama is installed and running.
2. Pull a local model: `ollama pull llama3.2` (or the model specified in your `.env`)
3. Create a `.env` file (you can copy `.env.example` if available) to configure the model.

## Configuration
The application reads configuration from the `.env` file. You can adjust the `MODEL_NAME` or `OLLAMA_URL` there.

## Running the Application
```bash
python src/main.py
```

## Running Tests
```bash
python -m unittest discover tests/
```
