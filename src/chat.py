from src.llm_client import generate_response
from src.config import Config

def start_chat():
    print(f"=== JARVIS Initialized ===")
    print(f"Connected to local model: {Config.MODEL_NAME}")
    print("Type 'exit' or 'quit' to stop.")
    print("=========================\n")
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.strip().lower() in ['exit', 'quit']:
                print("JARVIS: Goodbye!")
                break
                
            if not user_input.strip():
                continue
                
            response = generate_response(user_input)
            print(f"JARVIS: {response}\n")
            
        except KeyboardInterrupt:
            print("\nJARVIS: Goodbye!")
            break
        except Exception as e:
            print(f"JARVIS encountered an error: {e}")
