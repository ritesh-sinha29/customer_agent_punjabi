import asyncio
import logging
import os
import httpx
from src.app.core.config import settings

logger = logging.getLogger("TranslationService")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip('"')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class TranslationService:
    """
    Ultra-fast English-to-Punjabi (Gurmukhi) translation service using Groq (llama-3.1-8b-instant).
    Executes in < 300 ms with ZERO heavy model loading or downloads.
    """

    async def translate_to_punjabi(self, text: str) -> str:
        if not text or not text.strip():
            return ""

        # 1. Groq Fast Translation API (llama-3.1-8b-instant, ~200ms latency)
        if GROQ_API_KEY:
            try:
                system_prompt = (
                    "You are a professional English-to-Punjabi (Gurmukhi script) translator for agricultural & dairy farmers.\n"
                    "Translate the provided text accurately and naturally into Punjabi using Gurmukhi script (ਗੁਰਮੁਖੀ).\n"
                    "Preserve technical terms, numbers, product names (e.g. Horsa-550X-Turbo, TrioSan Gold, MaxaPro-DS Dairy, Buffalo-Power 2X), and dosages accurately.\n"
                    "Return ONLY the translated Punjabi text without any conversational intro, quotes, or markdown wrappers."
                )

                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                }

                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                }

                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.post(GROQ_API_URL, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        translated = data["choices"][0]["message"]["content"].strip()
                        if translated:
                            logger.info("[TranslationService] Instant Punjabi translation complete via Groq.")
                            return translated
                    else:
                        logger.error(f"Groq translation API error status {res.status_code}: {res.text}")
            except Exception as ge:
                logger.error(f"Groq API translation failed: {ge}")

        # 2. OpenAI Fallback
        if settings.OPENAI_API_KEY:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="gpt-4.1-mini",
                    temperature=0.1,
                    api_key=settings.OPENAI_API_KEY,
                )
                res = await llm.ainvoke(
                    [
                        SystemMessage(
                            content="Translate the text into natural Punjabi (Gurmukhi script). Return ONLY the translated Punjabi text."
                        ),
                        HumanMessage(content=text),
                    ]
                )
                return res.content.strip()
            except Exception as oe:
                logger.error(f"OpenAI translation failed: {oe}")

        return text


translation_service = TranslationService()
