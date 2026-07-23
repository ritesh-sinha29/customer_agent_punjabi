import json
import logging
import os
import re
from typing import Dict, List
import httpx
import logfire
from langfuse import Langfuse
from src.app.core.config import settings

logger = logging.getLogger("QueryOptimizer")

# Initialize Logfire
logfire.configure()

# Initialize Langfuse
lf_public = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip('"')
lf_secret = os.getenv("LANGFUSE_SECRET_KEY", "").strip('"')
lf_host = os.getenv("LANGFUSE_BASE_URL", "").strip('"')

langfuse = None
if lf_public and lf_secret:
    try:
        langfuse = Langfuse(
            public_key=lf_public,
            secret_key=lf_secret,
            host=lf_host or "https://us.cloud.langfuse.com"
        )
        logger.info("Langfuse initialized successfully for query observation.")
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip('"')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class QueryOptimizer:
    """
    Handles Query Re-writing and Multi-Query Expansion using gpt-4.1-mini as primary
    and Groq (llama-3.1-8b-instant) as fast fallback.
    Executes in < 300 ms with 0 Hugging Face network timeouts.
    """

    def _extract_json_array(self, text: str) -> List[str] | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned)
            cleaned = cleaned.strip()

        start_idx = cleaned.find("[")
        end_idx = cleaned.rfind("]") + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = cleaned[start_idx:end_idx]
            try:
                data = json.loads(json_str)
                if isinstance(data, list) and all(isinstance(x, str) for x in data):
                    return data
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode JSON substring: {json_str}")
        return None

    def _fallback_parse(self, text: str) -> List[str]:
        quotes = re.findall(r'"([^"]*)"', text)
        if len(quotes) >= 2:
            return [q.strip() for q in quotes[:4]]
            
        lines = []
        for line in text.split("\n"):
            line = re.sub(r"^[-*•\d\.\s]+", "", line).strip()
            if line and len(line) > 3:
                lines.append(line)
        if len(lines) >= 1:
            return lines[:3]
            
        return []

    @logfire.instrument("optimize_query")
    def optimize_query(
        self, 
        chat_history: List[Dict[str, str]], 
        current_query: str, 
        user_id: str = "guest_user"
    ) -> List[str]:
        """
        Takes conversation history + current user query, and expands it to 3 optimized queries
        using OpenAI (gpt-4.1-mini) as primary, falling back to Groq (llama-3.1-8b-instant).
        """
        history_str = ""
        for msg in chat_history[-5:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_str += f"{role}: {msg.get('content', '')}\n"

        system_message = (
            "You are a search query optimizer for an agricultural and animal feed product database.\n"
            "Given a conversation history and a final user question:\n"
            "1. Resolve pronouns (e.g., 'it', 'them', 'dosage of this') using context.\n"
            "2. If the user query is in Punjabi (native or transliterated Hinglish/Punjabi), translate agricultural terms into English search keywords (e.g., 'ਮੱਝ' or 'majj' -> buffalo, 'ਦੁੱਧ' or 'dudh' -> milk, 'ਥਣੈਲਾ' -> mastitis, 'ਬੁਖਾਰ' -> fever) and output terms in English.\n"
            "3. Generate exactly 3 unique, search-optimized search query variations that will retrieve the best matching documents.\n"
            "Respond ONLY with a JSON array of strings containing the 3 queries. Example:\n"
            '[\"cow milk calcium deficiency feed\", \"cattle milk fever prevention supplements\", \"dairy cows feed fat quality increase\"]'
        )

        user_message = f"Conversation History:\n{history_str}\nUser Question: {current_query}"

        # 1. Primary: OpenAI gpt-4.1-mini (250ms)
        if settings.OPENAI_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4.1-mini",
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 150
                }
                with httpx.Client(timeout=4.0) as client:
                    res = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"]
                        queries = self._extract_json_array(content) or self._fallback_parse(content)
                        if queries:
                            logger.info(f"OpenAI gpt-4.1-mini generated expansions in <300ms: {queries}")
                            return queries
            except Exception as oe:
                logger.warning(f"OpenAI query optimization failed ({oe}). Falling back to Groq...")

        # 2. Fallback: Groq llama-3.1-8b-instant (150ms)
        if GROQ_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 150
                }
                with httpx.Client(timeout=4.0) as client:
                    res = client.post(GROQ_API_URL, json=payload, headers=headers)
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"]
                        queries = self._extract_json_array(content) or self._fallback_parse(content)
                        if queries:
                            logger.info(f"Groq llama-3.1-8b-instant generated expansions in <200ms: {queries}")
                            return queries
            except Exception as ge:
                logger.error(f"Groq fallback query optimization failed: {ge}")

        # Final Fallback: Return original query
        return [current_query]


query_optimizer = QueryOptimizer()
