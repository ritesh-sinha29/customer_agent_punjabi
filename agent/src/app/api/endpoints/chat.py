from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from app.core.guardrail_service import AgentGuardrailService

router = APIRouter(prefix="/chat", tags=["Agent Chat"])

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message input to the agent")
    user_id: Optional[str] = Field(None, description="Optional caller user ID")

class ChatResponse(BaseModel):
    response: str
    is_flagged: bool = False
    refusal_reason: Optional[str] = None

@router.post("/", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Guarded Agent Endpoint protected by NVIDIA NeMo Guardrails.
    - Filters Jailbreaks & Prompt Injections
    - Redacts PII (Emails, Phones, SSNs, Credit Cards)
    """
    guardrail_svc = AgentGuardrailService.get_instance()
    
    # 1. Inspect & Sanitize User Input
    is_safe, sanitized_input, refusal_reason = await guardrail_svc.validate_input(request.message)
    if not is_safe:
        return ChatResponse(
            response=refusal_reason or "Request blocked by AI Security Policy.",
            is_flagged=True,
            refusal_reason="SECURITY_VIOLATION_JAILBREAK_DETECTED"
        )
    
    # 2. Process query through Guarded Agent pipeline
    try:
        guarded_reply = await guardrail_svc.generate_guarded_response(sanitized_input)
        return ChatResponse(response=guarded_reply, is_flagged=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")
