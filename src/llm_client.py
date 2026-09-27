import json
import urllib.request
import urllib.error
from typing import Generator
from src.config import Config

def stream_response(prompt: str) -> Generator[str, None, None]:
    """
    Sends a prompt to the local Ollama API and yields chunks of the response as they are generated.
    """
    url = f"{Config.OLLAMA_URL}/api/generate"
    payload = {
        "model": Config.MODEL_NAME,
        "prompt": prompt,
        "stream": True
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=Config.REQUEST_TIMEOUT) as response:
            for line in response:
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    yield chunk.get("response", "")
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError) or "Connection refused" in str(e.reason):
            yield f"Error: Could not connect to Ollama at {Config.OLLAMA_URL}. Is it running?"
        elif "timed out" in str(e.reason).lower():
            yield f"Error: Request timed out after {Config.REQUEST_TIMEOUT}s. Ollama may be busy loading the model."
        else:
            yield f"Error communicating with Ollama API: {e.reason}"
    except TimeoutError:
        yield f"Error: Request timed out after {Config.REQUEST_TIMEOUT}s. Ollama may be busy loading the model."
    except Exception as e:
        yield f"Error: {e}"

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
        with urllib.request.urlopen(req, timeout=Config.REQUEST_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "")
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError) or "Connection refused" in str(e.reason):
            return f"Error: Could not connect to Ollama at {Config.OLLAMA_URL}. Is it running?"
        elif "timed out" in str(e.reason).lower():
            return f"Error: Request timed out after {Config.REQUEST_TIMEOUT}s. Ollama may be busy loading the model."
        return f"Error communicating with Ollama API: {e.reason}"
    except TimeoutError:
        return f"Error: Request timed out after {Config.REQUEST_TIMEOUT}s. Ollama may be busy loading the model."
    except Exception as e:
        return f"Error: {e}"

