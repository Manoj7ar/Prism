import os
from dotenv import load_dotenv, set_key
from pathlib import Path

root_env = Path(__file__).parent.parent / '.env'
load_dotenv(root_env, override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_PRO_MODEL = "gemini-2.0-flash"
GEMINI_FLASH_MODEL = "gemini-2.0-flash"
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "127.0.0.1")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

CORS_ORIGINS = [
    origin.strip() 
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
]

def save_key(key: str):
    """Save API key to .env file"""
    if not root_env.exists():
        with open(root_env, 'w') as f:
            f.write("")
    
    # Update local variable so we don't need reload
    global GEMINI_API_KEY
    GEMINI_API_KEY = key
    
    # Write to file
    set_key(root_env, "GEMINI_API_KEY", key)