from pinecone import Pinecone
import os
import certifi

from src.app.core.config import settings

class PineconeService:
    def __init__(self):
        self.api_key = settings.PINECONE_API_KEY
        self.index_name = settings.PINECONE_INDEX_NAME
        self.pc = None
        self.index = None
        
        if self.api_key:
            self.pc = Pinecone(api_key=self.api_key)
            if self.index_name:
                try:
                    self.index = self.pc.Index(self.index_name)
                except Exception as e:
                    print(f"Error loading Pinecone index '{self.index_name}': {e}")

    def get_index(self):
        return self.index

    def check_connection(self) -> bool:
        if not self.pc or not self.index:
            return False
        try:
            self.index.describe_index_stats()
            return True
        except Exception as e:
            print(f"Pinecone connection check failed: {e}")
            return False

pinecone_service = PineconeService()
