from src.llm_client import stream_response
from src.config import Config

def start_chat():
    print(f"=== JARVIS Initialized ===")
    print(f"Connected to local model: {Config.MODEL_NAME}")
    print("Type 'exit' or 'quit' to stop.")
    print("Type '/clear' to reset conversation memory.")
    print("=========================\n")
    
    # Initialize conversation memory
    system_prompt = "You are JARVIS, a helpful, concise, and smart local AI assistant."
    history = [{"role": "system", "content": system_prompt}]
    
    while True:
        try:
            user_input = input("You: ")
            
            if user_input.strip().lower() in ['exit', 'quit']:
                print("JARVIS: Goodbye!")
                break
                
            if user_input.strip().lower() == '/clear':
                history = [{"role": "system", "content": system_prompt}]
                print("JARVIS: Conversation memory cleared.\n")
                continue
                
            if not user_input.strip():
                continue
                
            # Add user message to history
            history.append({"role": "user", "content": user_input})
                
            print("JARVIS: ", end="", flush=True)
            assistant_reply = ""
            
            for chunk in stream_response(history):
                print(chunk, end="", flush=True)
                assistant_reply += chunk
            print("\n")
            
            # Add assistant response to history
            history.append({"role": "assistant", "content": assistant_reply})
            
        except KeyboardInterrupt:
            print("\nJARVIS: Goodbye!")
            break
        except Exception as e:
            print(f"JARVIS encountered an error: {e}")
