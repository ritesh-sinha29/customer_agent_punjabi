import os
import re
import logging
from typing import Tuple, Dict, Any, Optional
from nemoguardrails import RailsConfig, LLMRails
from nemoguardrails.actions import action

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Custom Action: PII Masking (Emails, Phone Numbers, SSNs, Cards, PAN Cards)
# ------------------------------------------------------------------
@action(name="mask_pii")
def mask_pii(text: str) -> str:
    """Sanitizes PII from user inputs and bot outputs."""
    if not text:
        return text

    original_text = text

    # Mask Email
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "[REDACTED_EMAIL]", text)
    # Mask Phone Number (Standard US/International)
    text = re.sub(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', "[REDACTED_PHONE]", text)
    # Mask SSN
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', "[REDACTED_SSN]", text)
    # Mask Credit Card (13 to 16 digits)
    text = re.sub(r'\b(?:\d[ -]*?){13,16}\b', "[REDACTED_CARD]", text)
    # Mask Indian PAN Card / Government Tax IDs (e.g., gdpr5656565, ABCDE1234F)
    text = re.sub(r'\b[a-zA-Z]{4,5}\d{4,7}[a-zA-Z]?\b', "[REDACTED_PAN_CARD]", text, flags=re.IGNORECASE)


    if text != original_text:
        print(f"\n[GUARDRAIL CONSOLE LOG - PII DETECTED & REDACTED]:")
        print(f"  Original:  {original_text}")
        print(f"  Sanitized: {text}\n")

    return text


# ------------------------------------------------------------------
# Custom Action: Fast Local Jailbreak & Prompt Injection Check
# ------------------------------------------------------------------
@action(name="self_check_input")
def self_check_input(user_input: str) -> bool:
    """Inspects user input for adversarial prompt injection and jailbreak attacks."""
    if not user_input:
        return False
    
    jailbreak_keywords = [
        "dan mode", "ignore previous instructions", "ignore all prior",
        "system override", "forget system instructions", "disregard safety",
        "developer mode", "jailbreak", "bypass security",
        "im admin", "i am admin", "you are a medical chatbot", "save humanity"
    ]
    
    text_lower = user_input.lower()
    for kw in jailbreak_keywords:
        if kw in text_lower:
            print(f"\n[GUARDRAIL CONSOLE LOG - ATTACK BLOCKED]:")

            print(f"  Reason:     Jailbreak / Role-play Social Engineering Trigger Detected ('{kw}')")
            print(f"  User Input: {user_input}\n")
            logger.warning(f"Guardrail Alert: Prompt Injection / Jailbreak keyword detected: '{kw}'")
            return True # Attack detected
    return False


# ------------------------------------------------------------------
# Main Guardrail Service Singleton Class
# ------------------------------------------------------------------
class AgentGuardrailService:
    _instance: Optional['AgentGuardrailService'] = None

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(__file__), "guardrails_config")
        
        self.config_dir = config_dir
        self.rails_config = RailsConfig.from_path(self.config_dir)
        self.rails = LLMRails(self.rails_config)
        
        # Register security actions
        self.rails.register_action(mask_pii, "mask_pii")
        self.rails.register_action(self_check_input, "self_check_input")

    @classmethod
    def get_instance(cls, config_dir: Optional[str] = None) -> 'AgentGuardrailService':
        if cls._instance is None:
            cls._instance = AgentGuardrailService(config_dir)
        return cls._instance

    async def validate_input(self, user_input: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validates and sanitizes incoming user input.
        Returns:
            Tuple[is_safe (bool), sanitized_input (str), refusal_message (str | None)]
        """
        print(f"\n[GUARDRAIL CONSOLE LOG - INCOMING REQUEST]: {user_input}")

        # Step 1: Detect Prompt Injection / Jailbreak
        is_attack = self_check_input(user_input)
        if is_attack:
            refusal = "I cannot process this request because it violates safety policies and security rules."
            return False, user_input, refusal

        # Step 2: Sanitize PII
        sanitized = mask_pii(user_input)
        print(f"[GUARDRAIL CONSOLE LOG - PASSED INPUT FILTER]: Processing query...")
        return True, sanitized, None

    async def validate_output(self, bot_output: str) -> Tuple[bool, str]:
        """
        Sanitizes and verifies outgoing LLM responses.
        """
        sanitized = mask_pii(bot_output)
        return True, sanitized

    async def validate_tool_call(self, tool_name: str, tool_args: Dict[str, Any]):
        """
        Action Rail: Validates tool name & arguments before execution.
        """
        from app.core.tool_guardrails import validate_tool_execution
        return validate_tool_execution(tool_name, tool_args)

    async def generate_guarded_response(self, prompt: str) -> str:
        """
        Executes the full NeMo Guardrails pipeline (Input Rails -> LLM -> Output Rails).
        """
        is_safe, sanitized_prompt, refusal = await self.validate_input(prompt)
        if not is_safe:
            return refusal or "Access Denied by Security Policy."

        # Pass sanitized prompt through LLMRails pipeline
        response = await self.rails.generate_async(prompt=sanitized_prompt)
        
        # Validate & redact output
        _, sanitized_response = await self.validate_output(response)
        return sanitized_response
