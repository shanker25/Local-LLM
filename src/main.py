import sys
import os

# Add the parent directory to sys.path so we can import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chat import start_chat

if __name__ == "__main__":
    start_chat()
