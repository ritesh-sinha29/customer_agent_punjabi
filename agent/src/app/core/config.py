import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from the agent's root directory .env file, overriding system variables
env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Verify and log loaded key to confirm it loaded the right key from .env
openai_key = os.getenv("OPENAI_API_KEY", "")
if openai_key:
    # Print the last 6 characters of the key
    print(f"[Config] Loaded OpenAI API Key from .env (ending in: ...{openai_key[-6:]})")
else:
    print("[Config] ERROR: OPENAI_API_KEY is missing from environment/config!", file=sys.stderr)

class Settings:
    OPENAI_API_KEY: str = openai_key
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "customer-pb-agent")
    LLAMA_CLOUD_API_KEY: str = os.getenv("LLAMA_CLOUD_API_KEY", "")
    EMBEDDING_API_URL: str = os.getenv("EMBEDDING_API_URL", "")
    UPSTASH_REDIS_URL: str = os.getenv("UPSTASH_REDIS_URL", "")

settings = Settings()
