import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from src.app.graphs.graph import agent_graph
from langfuse.callback import CallbackHandler

logger = logging.getLogger("AgentChatApi")
router = APIRouter(
    prefix="/v1/agent",
    tags=["Agent Chat"]
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str
    user_id: str
    approve: bool = None  # None: regular chat; True/False: HITL approval

def get_langfuse_callback():
    """
    Helper to set up callback tracing dynamically if configuration is present.
    """
    lf_public = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip('"')
    lf_secret = os.getenv("LANGFUSE_SECRET_KEY", "").strip('"')
    lf_host = os.getenv("LANGFUSE_BASE_URL", "").strip('"')
    if lf_public and lf_secret:
        try:
            return CallbackHandler(public_key=lf_public, secret_key=lf_secret, host=lf_host)
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse callback handler: {e}")
    return None

@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    config = {
        "configurable": {
            "thread_id": req.thread_id
        }
    }
    
    # Inject Langfuse tracing callback
    cb = get_langfuse_callback()
    if cb:
        config["callbacks"] = [cb]
        
    try:
        # 1. Fetch current state of the conversation thread
        state = await agent_graph.aget_state(config)
        
        # 2. Check if the graph is currently interrupted and waiting for HITL approval
        if state.next:
            if req.approve is None:
                raise HTTPException(
                    status_code=400,
                    detail="Graph is waiting for approval. Please specify 'approve' as True or False."
                )
                
            if req.approve:
                # User approved: resume execution
                logger.info(f"User approved pending action for thread {req.thread_id}. Resuming...")
                final_state = await agent_graph.ainvoke(None, config)
            else:
                # User rejected: clear the pending action to cancel database write and resume
                logger.info(f"User rejected pending action for thread {req.thread_id}. Cancelling and resuming...")
                await agent_graph.aupdate_state(config, {"pending_action_details": None})
                final_state = await agent_graph.ainvoke(None, config)
        else:
            # 3. Standard execution flow
            if not req.message.strip():
                raise HTTPException(status_code=400, detail="Message cannot be empty.")
                
            initial_state = {
                "messages": [HumanMessage(content=req.message)],
                "user_id": req.user_id
            }
            final_state = await agent_graph.ainvoke(initial_state, config)
            
        # 4. Check if the graph has entered a new interrupt state (needs approval)
        new_state = await agent_graph.aget_state(config)
        if new_state.next:
            pending_action = new_state.next[0]
            # Find the last message (which is the confirmation prompt from the specialist agent)
            last_message = new_state.values["messages"][-1].content if new_state.values.get("messages") else ""
            
            return {
                "success": True,
                "status": "pending_approval",
                "pending_action": "booking" if "booking" in pending_action else "query",
                "details": new_state.values.get("pending_action_details"),
                "response": last_message,
                "thread_id": req.thread_id
            }
            
        # 5. Otherwise, return the final response
        assistant_messages = [
            msg.content for msg in final_state["messages"] 
            if msg.type == "ai"
        ]
        reply = assistant_messages[-1] if assistant_messages else "I couldn't process your request."
        
        return {
            "success": True,
            "status": "completed",
            "response": reply,
            "thread_id": req.thread_id
        }
        
    except Exception as e:
        logger.error(f"Agent Graph execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent Graph Error: {str(e)}")
