import json
import urllib.request
import urllib.error
from src.config import Config

def generate_response(prompt: str) -> str:
    """
    Sends a prompt to the local Ollama API and returns the generated text.
    """
    url = f"{Config.OLLAMA_URL}/api/generate"
    payload = {
        "model": Config.MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "")
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError) or "Connection refused" in str(e.reason):
            return f"Error: Could not connect to Ollama at {Config.OLLAMA_URL}. Is it running?"
        return f"Error communicating with Ollama API: {e.reason}"
    except Exception as e:
        return f"Error: {e}"
