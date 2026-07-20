import os
import logging
import json
import asyncio
import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from src.app.graphs.graph import agent_graph
from langfuse.langchain import CallbackHandler
from src.app.services.db_service import db_service

logger = logging.getLogger("AgentChatApi")
router = APIRouter(
    prefix="/v1/agent",
    tags=["Agent Chat"]
)

def save_user_message(thread_id: str, user_id: str, message: str):
    try:
        thread_exists = db_service.execute_query(
            "SELECT 1 FROM chat_thread WHERE id = %s", (thread_id,)
        )
        if not thread_exists:
            title = message[:50] + "..." if len(message) > 50 else message
            db_service.execute_insert(
                "INSERT INTO chat_thread (id, title, user_id) VALUES (%s, %s, %s)",
                (thread_id, title, user_id)
            )
        msg_id = f"msg-user-{uuid.uuid4()}"
        db_service.execute_insert(
            "INSERT INTO chat_message (id, thread_id, role, content) VALUES (%s, %s, %s, %s)",
            (msg_id, thread_id, "user", message)
        )
    except Exception as e:
        logger.error(f"Error saving user message: {e}")

def save_assistant_message(thread_id: str, content: str):
    try:
        msg_id = f"msg-assistant-{uuid.uuid4()}"
        db_service.execute_insert(
            "INSERT INTO chat_message (id, thread_id, role, content) VALUES (%s, %s, %s, %s)",
            (msg_id, thread_id, "assistant", content)
        )
        db_service.execute_insert(
            "UPDATE chat_thread SET updated_at = NOW() WHERE id = %s",
            (thread_id,)
        )
    except Exception as e:
        logger.error(f"Error saving assistant message: {e}")


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    user_id: str
    approve: bool = None  # None: regular chat; True/False: HITL approval

def extract_reasoning(output: Any) -> str:
    if not output:
        return ""
    if hasattr(output, "reasoning") and getattr(output, "reasoning", None):
        return str(output.reasoning)
    if isinstance(output, dict) and output.get("reasoning"):
        return str(output["reasoning"])
    
    content = getattr(output, "content", "")
    if isinstance(content, str) and content.strip():
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and parsed.get("reasoning"):
                return str(parsed["reasoning"])
        except Exception:
            pass
            
    parsed_obj = getattr(output, "additional_kwargs", {}).get("parsed")
    if parsed_obj:
        if hasattr(parsed_obj, "reasoning") and getattr(parsed_obj, "reasoning", None):
            return str(parsed_obj.reasoning)
        if isinstance(parsed_obj, dict) and parsed_obj.get("reasoning"):
            return str(parsed_obj["reasoning"])
        
    return ""

def get_langfuse_callback():
    """
    Helper to set up callback tracing dynamically if configuration is present.
    """
    lf_public = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip('"')
    lf_secret = os.getenv("LANGFUSE_SECRET_KEY", "").strip('"')
    lf_host = os.getenv("LANGFUSE_BASE_URL", "").strip('"')
    if lf_public and lf_secret:
        try:
            return CallbackHandler(public_key=lf_public)
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
                save_user_message(req.thread_id, req.user_id, "Yes, confirm.")
                final_state = await agent_graph.ainvoke(None, config)
            else:
                # User rejected: clear the pending action to cancel database write and resume
                logger.info(f"User rejected pending action for thread {req.thread_id}. Cancelling and resuming...")
                save_user_message(req.thread_id, req.user_id, "No, cancel.")
                await agent_graph.aupdate_state(config, {"pending_action_details": None})
                final_state = await agent_graph.ainvoke(None, config)
        else:
            # 3. Standard execution flow
            if not req.message.strip():
                raise HTTPException(status_code=400, detail="Message cannot be empty.")
                
            save_user_message(req.thread_id, req.user_id, req.message)
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
            save_assistant_message(req.thread_id, last_message)
            
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
        save_assistant_message(req.thread_id, reply)
        
        return {
            "success": True,
            "status": "completed",
            "response": reply,
            "thread_id": req.thread_id
        }
        
    except Exception as e:
        logger.error(f"Agent Graph execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent Graph Error: {str(e)}")


@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    config = {
        "configurable": {
            "thread_id": req.thread_id
        }
    }
    
    async def process_stream_events(stream_iterator):
        async for event in stream_iterator:
            kind = event.get("event")
            node_name = event.get("metadata", {}).get("langgraph_node", "")
            
            if kind == "on_chat_model_stream":
                if node_name == "supervisor_router":
                    continue
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    token = chunk.content
                    if token and isinstance(token, str):
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            elif kind == "on_chat_model_end":
                if node_name == "supervisor_router":
                    output = event.get("data", {}).get("output")
                    reasoning = extract_reasoning(output)
                    if reasoning:
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning})}\n\n"
    
    async def event_generator():
        cb = get_langfuse_callback()
        if cb:
            config["callbacks"] = [cb]
            
        try:
            # 1. Fetch current state of the conversation thread
            state = await agent_graph.aget_state(config)
            
            # 2. Check if the graph is currently interrupted and waiting for HITL approval
            if state.next:
                if req.approve is None:
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Graph is waiting for approval. Please specify approve as True or False.'})}\n\n"
                    return
                    
                if req.approve:
                    # User approved: resume execution
                    logger.info(f"User approved pending action for thread {req.thread_id}. Resuming...")
                    save_user_message(req.thread_id, req.user_id, "Yes, confirm.")
                    async for chunk in process_stream_events(agent_graph.astream_events(None, config, version="v2")):
                        yield chunk
                else:
                    # User rejected: clear the pending action to cancel database write and resume
                    logger.info(f"User rejected pending action for thread {req.thread_id}. Cancelling and resuming...")
                    save_user_message(req.thread_id, req.user_id, "No, cancel.")
                    await agent_graph.aupdate_state(config, {"pending_action_details": None})
                    async for chunk in process_stream_events(agent_graph.astream_events(None, config, version="v2")):
                        yield chunk
            else:
                # 3. Standard execution flow
                if not req.message.strip():
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Message cannot be empty.'})}\n\n"
                    return
                    
                save_user_message(req.thread_id, req.user_id, req.message)
                initial_state = {
                    "messages": [HumanMessage(content=req.message)],
                    "user_id": req.user_id
                }
                
                async for chunk in process_stream_events(agent_graph.astream_events(initial_state, config, version="v2")):
                    yield chunk
            
            # 4. Check if the graph has entered a new interrupt state (needs approval) or completed
            new_state = await agent_graph.aget_state(config)
            if new_state.next:
                pending_action = new_state.next[0]
                last_message = new_state.values["messages"][-1].content if new_state.values.get("messages") else ""
                save_assistant_message(req.thread_id, last_message)
                
                payload = {
                    "type": "pending_approval",
                    "status": "pending_approval",
                    "pending_action": "booking" if "booking" in pending_action else "query",
                    "details": new_state.values.get("pending_action_details"),
                    "response": last_message,
                    "thread_id": req.thread_id
                }
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                assistant_messages = [
                    msg.content for msg in new_state.values.get("messages", [])
                    if msg.type == "ai"
                ]
                reply = assistant_messages[-1] if assistant_messages else "I couldn't process your request."
                save_assistant_message(req.thread_id, reply)
                payload = {
                    "type": "completed",
                    "status": "completed",
                    "response": reply,
                    "thread_id": req.thread_id
                }
                yield f"data: {json.dumps(payload)}\n\n"
                      
        except Exception as e:
            logger.error(f"Streaming endpoint error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': f'Agent Graph Error: {str(e)}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


