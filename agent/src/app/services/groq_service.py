import os
import logging
import httpx
import json
import re
from typing import List, Dict, Any

logger = logging.getLogger("GroqService")

# Get API key from environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip('"')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

class GroqService:
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def check_usefulness(self, messages: List[Dict[str, str]]) -> bool:
        """
        Calls Groq with llama-3.1-8b-instant to classify if the conversation history
        contains useful user profile or farm details. Returns True if YES, else False.
        """
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set. Skipping gate check.")
            return False

        # Format conversation history for classification
        conversation_str = ""
        for m in messages[-6:]:
            role = "User" if m["role"] == "user" else "Assistant"
            conversation_str += f"{role}: {m['content']}\n"

        system_prompt = (
            "You are a classification gate. Analyze the recent conversation messages between the user (farmer) and the assistant.\n"
            "Identify if the user has shared any new, specific, or useful details about:\n"
            "1. The types of livestock they own (cows, buffaloes) and counts.\n"
            "2. Their location, farm name, or district.\n"
            "3. Specific issues, symptoms, or concerns they have with their animals (e.g., mastitis, low milk fat %, calcium deficiency).\n"
            "4. Specific orders, products, or dosages they are interested in.\n\n"
            "Respond with exactly 'YES' if there is new/useful information to save to their long-term profile, or 'NO' if the conversation contains only greetings, generic chit-chat, booking questions with no personal details, or no new user information.\n"
            "Do not explain. Return ONLY 'YES' or 'NO'."
        )

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Conversation History:\n{conversation_str}"}
            ],
            "temperature": 0.0,
            "max_tokens": 10
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(GROQ_API_URL, headers=self.headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"].strip()
                    logger.info(f"Groq usefulness gate response: '{content}'")
                    return "YES" in content.upper()
                else:
                    logger.error(f"Groq API returned error status {response.status_code}: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Groq usefulness check failed: {e}")
            return False

    async def consolidate_memory(self, messages: List[Dict[str, str]], current_facts: List[str]) -> Dict[str, Any]:
        """
        Calls Groq with llama-3.3-70b-versatile to extract and merge semantic facts
        and generate a date-stamped episodic summary.
        """
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set. Skipping consolidation.")
            return {"semantic_facts": current_facts, "episodic_summary": ""}

        conversation_str = ""
        for m in messages:
            role = "User" if m["role"] == "user" else "Assistant"
            conversation_str += f"{role}: {m['content']}\n"

        system_prompt = (
            "You are an AI memory consolidation engine for agricultural agents.\n"
            "Analyze the conversation history and the user's existing profile facts.\n"
            "Your task is to:\n"
            "1. Extract any new specific facts about the user's farm, livestock (counts/types), location, preferences, or issues from the conversation.\n"
            "2. Merge them into the existing list of facts. Deduplicate, update facts if they changed, and remove obsolete or contradictory ones. Keep the facts list concise (max 10 facts).\n"
            "3. Generate a single, concise date-stamped sentence summarizing this conversation thread/episode (e.g. '[2026-07-21] Inquired about Buffalo-Power 2X dosage for low milk fat, placed a booking for 2 quantities.').\n\n"
            "You must respond ONLY with a JSON object format (no markdown blocks like ```json):\n"
            "{\n"
            '  "semantic_facts": ["fact 1", "fact 2", ...],\n'
            '  "episodic_summary": "[YYYY-MM-DD] Summary text"\n'
            "}"
        )

        user_content = f"Existing Facts:\n{json.dumps(current_facts)}\n\nConversation History:\n{conversation_str}"

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(GROQ_API_URL, headers=self.headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"].strip()
                    parsed = json.loads(content)
                    return {
                        "semantic_facts": parsed.get("semantic_facts", current_facts),
                        "episodic_summary": parsed.get("episodic_summary", "")
                    }
                else:
                    logger.error(f"Groq API consolidation failed: {response.text}")
                    return {"semantic_facts": current_facts, "episodic_summary": ""}
        except Exception as e:
            logger.error(f"Groq memory consolidation failed: {e}")
            return {"semantic_facts": current_facts, "episodic_summary": ""}

groq_service = GroqService()
