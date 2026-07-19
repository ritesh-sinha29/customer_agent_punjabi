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

# Initialize Langfuse (cleaning any quotes from env variables)
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
else:
    logger.warning("Langfuse credentials not fully set. Observation will be limited.")


class QueryOptimizer:
    """
    Handles Query Re-writing and Multi-Query Expansion using Hugging Face Serverless Inference.
    Falls back to OpenAI gpt-4.1-nano if Hugging Face execution fails.
    Features robust JSON extraction and full trace logs via Logfire and Langfuse.
    """

    def __init__(self):
        # Clean the Hugging Face token in case of quotes
        self.hf_token = os.getenv("HF_TOKEN", "").strip('"')
        
        # Use Qwen-72B-Instruct for high quality multilingual capabilities
        self.model_url = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct"
        
        # Fallback model in case the 72B is overloaded
        self.fallback_model_url = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-14B-Instruct"

    def _extract_json_array(self, text: str) -> List[str] | None:
        """
        Extracts and parses a JSON array of strings from the model's text output.
        Handles markdown code blocks and raw JSON text.
        """
        # Clean markdown code blocks if any
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned)
            cleaned = cleaned.strip()

        # Find bracket start and end
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
        """
        Regex and string splitting fallback parser if the LLM output is not valid JSON.
        """
        # Look for quoted strings in brackets
        quotes = re.findall(r'"([^"]*)"', text)
        if len(quotes) >= 2:
            return [q.strip() for q in quotes[:4]]
            
        # Split by newlines and clean lines starting with bullet points
        lines = []
        for line in text.split("\n"):
            line = re.sub(r"^[-*•\d\.\s]+", "", line).strip()
            if line and len(line) > 3:
                lines.append(line)
        if len(lines) >= 1:
            return lines[:3]
            
        return []

    @logfire.instrument("optimize_query_hf")
    def optimize_query(
        self, 
        chat_history: List[Dict[str, str]], 
        current_query: str, 
        user_id: str = "guest_user"
    ) -> List[str]:
        """
        Takes conversation history + current user query, and expands it to 3 optimized queries
        using Hugging Face Serverless Qwen as primary, falling back to OpenAI (gpt-4.1-nano) if necessary.
        """
        # Format conversation context
        history_str = ""
        for msg in chat_history[-5:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_str += f"{role}: {msg['content']}\n"

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

        # Combine as standard chat template
        prompt = f"<|im_start|>system\n{system_message}<|im_end|>\n<|im_start|>user\n{user_message}<|im_end|>\n<|im_start|>assistant\n"

        headers = {
            "Content-Type": "application/json"
        }
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"

        payload = {
            "inputs": prompt,
            "parameters": {
                "temperature": 0.1,
                "max_new_tokens": 150,
                "return_full_text": False
            }
        }

        # Start Langfuse Trace
        trace = None
        generation = None
        if langfuse:
            try:
                trace = langfuse.start_observation(
                    as_type="span",
                    name="query-optimization",
                    input={"original_query": current_query},
                    metadata={"user_id": user_id}
                )
                generation = trace.start_observation(
                    as_type="generation",
                    name="qwen-query-rewrite",
                    model="Qwen2.5-72B-Instruct",
                    input=prompt
                )
            except Exception as le:
                logger.error(f"Langfuse trace creation failed: {le}")

        logger.info(f"Optimizing query: '{current_query}' via Qwen...")
        logfire.info("Sending prompt to Hugging Face Qwen", original_query=current_query)

        response_text = ""
        used_model = "Qwen/Qwen2.5-72B-Instruct"

        try:
            with httpx.Client(timeout=8.0) as client:
                # Attempt primary 72B model
                response = client.post(self.model_url, json=payload, headers=headers)
                
                # If 72B is overloaded or failed, fall back to 14B model
                if response.status_code != 200:
                    logger.warning(f"Primary Qwen-72B failed ({response.status_code}). Trying Qwen-14B fallback...")
                    used_model = "Qwen/Qwen2.5-14B-Instruct"
                    response = client.post(self.fallback_model_url, json=payload, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        response_text = result[0].get("generated_text", "")
                    elif isinstance(result, dict):
                        response_text = result.get("generated_text", "")
                else:
                    raise RuntimeError(f"Hugging Face API returned error status {response.status_code}: {response.text}")
                    
        except Exception as e:
            logger.error(f"Hugging Face API call failed: {e}. Trying fallback to OpenAI...")
            logfire.warning("Hugging Face API error, attempting OpenAI fallback", error=str(e))

            # Try Fallback to OpenAI gpt-4o-mini
            openai_err_str = "no key"
            used_model = "openai:gpt-4o-mini"
            if settings.OPENAI_API_KEY:
                try:
                    headers = {
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 150
                    }
                    with httpx.Client(timeout=8.0) as client:
                        response = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                        if response.status_code == 200:
                            result = response.json()
                            response_text = result["choices"][0]["message"]["content"]
                            logger.info(f"OpenAI gpt-4o-mini generated response: {response_text}")
                            
                            parsed_queries = self._extract_json_array(response_text)
                            if not parsed_queries:
                                parsed_queries = self._fallback_parse(response_text)
                            
                            if parsed_queries:
                                if generation:
                                    generation.update(
                                        output=str(parsed_queries), 
                                        model=used_model, 
                                        status_message=f"HuggingFace failed ({e}), fell back to OpenAI"
                                    )
                                    generation.end()
                                    if trace:
                                        trace.update(output=str(parsed_queries))
                                        trace.end()
                                return parsed_queries
                        else:
                            raise RuntimeError(f"OpenAI API returned status {response.status_code}: {response.text}")
                except Exception as openai_err:
                    openai_err_str = str(openai_err)
                    logger.error(f"OpenAI fallback failed: {openai_err_str}")
                    logfire.exception("OpenAI fallback failed", error=openai_err_str)

            # Final Fallback: Return original query
            parsed_queries = [current_query]
            if generation:
                generation.update(
                    output=str(parsed_queries), 
                    level="ERROR", 
                    status_message=f"Hugging Face failed ({e}), OpenAI fallback failed ({openai_err_str}). Reverted to original query."
                )
                generation.end()
                if trace:
                    trace.update(output=str(parsed_queries), level="ERROR")
                    trace.end()
            return parsed_queries

        # Clean and parse response
        parsed_queries = self._extract_json_array(response_text)
        if not parsed_queries:
            logger.warning(f"Could not parse valid JSON array from: '{response_text}'. Running fallback parse.")
            parsed_queries = self._fallback_parse(response_text)

        # Final safety check: if we have empty queries, revert to original
        if not parsed_queries:
            parsed_queries = [current_query]

        # Log completion
        logger.info(f"Successfully generated optimized queries: {parsed_queries}")
        logfire.info("Query optimization completed", parsed_queries=parsed_queries)

        if generation:
            try:
                generation.update(
                    output=str(parsed_queries),
                    model=used_model,
                    usage={
                        "input_tokens": len(prompt) // 4,
                        "output_tokens": len(response_text) // 4
                    }
                )
                generation.end()
                if trace:
                    trace.update(output=str(parsed_queries))
                    trace.end()
            except Exception as le:
                logger.error(f"Failed to record Langfuse generation end: {le}")

        return parsed_queries


query_optimizer = QueryOptimizer()

