from llama_parse import LlamaParse
from src.app.core.config import settings

class LlamaService:
    def __init__(self):
        self.api_key = settings.LLAMA_CLOUD_API_KEY
        self.parser = None
        
        if self.api_key:
            try:
                self.parser = LlamaParse(
                    api_key=self.api_key,
                    result_type="markdown"
                )
            except Exception as e:
                print(f"Error initializing LlamaParse: {e}")

    def get_parser(self) -> LlamaParse | None:
        return self.parser

    def check_connection(self) -> bool:
        # A simple configuration validity check
        return bool(self.api_key and self.api_key.startswith("llx-"))

llama_service = LlamaService()
