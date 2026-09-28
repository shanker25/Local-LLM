import os

def load_dotenv(filepath=".env"):
    if not os.path.exists(filepath):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alt_path = os.path.join(base_dir, filepath)
        if os.path.exists(alt_path):
            filepath = alt_path
        else:
            return
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration."""
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    MODEL_NAME = os.getenv("MODEL_NAME", "llama3.2:1b")
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))

