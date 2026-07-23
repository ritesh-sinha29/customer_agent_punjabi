import os
import logging
import json
import asyncio
import uuid
import time
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from src.app.graphs.graph import agent_graph
from langfuse.langchain import CallbackHandler
from src.app.services.db_service import db_service
from src.app.services.semantic_cache_service import semantic_cache_service
from src.app.services.translation_service import translation_service

logger = logging.getLogger("AgentChatApi")
router = APIRouter(
    prefix="/v1/agent",
    tags=["Agent Chat"]
)

class TranslateRequest(BaseModel):
    text: str


@router.post("/translate")
async def translate_endpoint(req: TranslateRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    try:
        from datetime import timedelta
        from src.app.temporal.temporal_client import get_temporal_client
        
        # Execute via Temporal Workflow with strict 25s timeout and retries
        try:
            temporal_client = await get_temporal_client()
            translated = await asyncio.wait_for(
                temporal_client.execute_workflow(
                    "MessageTranslationWorkflow",
                    args=[req.text],
                    id=f"msg-translation-{uuid.uuid4()}",
                    task_queue="ingestion-task-queue",
                    execution_timeout=timedelta(seconds=25)
                ),
                timeout=25.0
            )
        except Exception as te:
            logger.warning(f"Temporal translation workflow execution warning ({te}). Falling back to fast direct translation...")
            translated = await asyncio.wait_for(
                translation_service.translate_to_punjabi(req.text),
                timeout=25.0
            )

        if not translated:
            raise HTTPException(status_code=500, detail="Translation returned empty result.")

        return {
            "success": True,
            "translated_text": translated
        }
    except asyncio.TimeoutError:
        logger.error("Translation request timed out after 25 seconds.")
        raise HTTPException(status_code=504, detail="Translation timed out after 25 seconds.")
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=f"Translation Error: {str(e)}")

async def trigger_background_memory_workflow(user_id: str, thread_id: str):
    try:
        cnt_row = db_service.execute_query(
            "SELECT COUNT(*) FROM chat_message WHERE thread_id = %s", (thread_id,)
        )
        count = list(cnt_row[0].values())[0] if cnt_row else 0
        if count > 0 and count % 4 == 0:
            logger.info(f"Message count is {count} (multiple of 4 - equivalent to 2 turns). Launching Temporal UserMemoryWorkflow in background.")
            from src.app.temporal.temporal_client import get_temporal_client
            temporal_client = await get_temporal_client()
            await temporal_client.start_workflow(
                "UserMemoryWorkflow",
                args=[user_id, thread_id],
                id=f"user-memory-workflow-{user_id}-{thread_id}-{int(time.time())}",
                task_queue="ingestion-task-queue"
            )
    except Exception as te:
        logger.error(f"Failed to start background memory Temporal workflow: {te}")

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

def get_slim_user_profile(user_id: str) -> dict:
    """
    Fetches a slim, lightweight core memory context (max 3 recent facts, 1 recent summary)
    to keep context small and fast without fetching heavy memory every message turn.
    """
    try:
        memory_row = db_service.execute_query(
            "SELECT semantic_facts, episodic_summaries FROM user_memory WHERE user_id = %s",
            (user_id,)
        )
        if memory_row:
            facts = memory_row[0].get("semantic_facts") or []
            summaries = memory_row[0].get("episodic_summaries") or []
            return {
                "semantic_facts": facts[-3:] if facts else [],
                "episodic_summaries": summaries[-1:] if summaries else []
            }
    except Exception as me:
        logger.error(f"Error loading user profile memory: {me}")
    return {"semantic_facts": [], "episodic_summaries": []}



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
    if lf_public and lf_secret:
        try:
            return CallbackHandler()
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse callback handler: {e}")
    return None

@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    config = {
        "configurable": {
            "thread_id": req.thread_id
        },
        "metadata": {
            "langfuse_session_id": req.thread_id,
            "langfuse_user_id": req.user_id
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

            # Check Semantic Cache first
            cached_data = await semantic_cache_service.get_cached_response(req.user_id, req.message)
            if cached_data:
                save_user_message(req.thread_id, req.user_id, req.message)
                save_assistant_message(req.thread_id, cached_data["response"])
                return {
                    "success": True,
                    "status": "completed",
                    "response": cached_data["response"],
                    "thread_id": req.thread_id,
                    "cached": True
                }
                
            save_user_message(req.thread_id, req.user_id, req.message)
            
            # Fetch slim, lightweight user core memory context
            user_profile = get_slim_user_profile(req.user_id)

            initial_state = {
                "messages": [HumanMessage(content=req.message)],
                "user_id": req.user_id,
                "user_profile": user_profile,
                "internal_facts": [],
                "action_type": None,
                "pending_action_details": None
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
        
        # Store in Semantic Cache for 7 days (reusing rag_dense_vec from RAG with 0 extra API calls)
        if req.approve is None and reply:
            rag_dense_vec = None
            for item in final_state.get("internal_facts", []):
                if isinstance(item, dict) and item.get("subagent") == "rag_agent":
                    rag_dense_vec = item.get("rag_dense_vec")
                    break
            await semantic_cache_service.set_cached_response(
                req.user_id, req.message, reply, dense_vec=rag_dense_vec
            )
        
        # Trigger background memory check if message count is a multiple of 3
        await trigger_background_memory_workflow(req.user_id, req.thread_id)
        
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
        },
        "metadata": {
            "langfuse_session_id": req.thread_id,
            "langfuse_user_id": req.user_id
        }
    }
    
    async def process_stream_events(stream_iterator):
        reasoning_sent = False
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
            elif kind in ["on_chat_model_end", "on_chain_end"]:
                if node_name == "supervisor_router" and not reasoning_sent:
                    output = event.get("data", {}).get("output")
                    reasoning = extract_reasoning(output)
                    if reasoning:
                        reasoning_sent = True
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning})}\n\n"
                elif node_name in ["booking_agent", "query_agent"]:
                    yield f"data: {json.dumps({'type': 'tool_success', 'tool': 'create_booking' if node_name == 'booking_agent' else 'create_query'})}\n\n"
            elif kind == "on_tool_end" and event.get("name") in ["create_booking", "create_query"]:
                yield f"data: {json.dumps({'type': 'tool_success', 'tool': event.get('name')})}\n\n"
    
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

                # Fast check in Semantic Cache
                cached_data = await semantic_cache_service.get_cached_response(req.user_id, req.message)
                if cached_data:
                    save_user_message(req.thread_id, req.user_id, req.message)
                    save_assistant_message(req.thread_id, cached_data["response"])
                    yield f"data: {json.dumps({'type': 'reasoning', 'content': 'Retrieved instantly from 7-day Semantic Cache.'})}\n\n"
                    yield f"data: {json.dumps({'type': 'token', 'content': cached_data['response']})}\n\n"
                    payload = {
                        "type": "completed",
                        "status": "completed",
                        "response": cached_data["response"],
                        "thread_id": req.thread_id,
                        "cached": True
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    return

                save_user_message(req.thread_id, req.user_id, req.message)
                
                # Fetch slim, lightweight user core memory context
                user_profile = get_slim_user_profile(req.user_id)

                initial_state = {
                    "messages": [HumanMessage(content=req.message)],
                    "user_id": req.user_id,
                    "user_profile": user_profile,
                    "internal_facts": [],
                    "action_type": None,
                    "pending_action_details": None
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
                
                # Store in 7-day Semantic Cache (reusing rag_dense_vec from RAG with 0 extra API calls)
                if req.approve is None and reply:
                    rag_dense_vec = None
                    for item in new_state.values.get("internal_facts", []):
                        if isinstance(item, dict) and item.get("subagent") == "rag_agent":
                            rag_dense_vec = item.get("rag_dense_vec")
                            break
                    await semantic_cache_service.set_cached_response(
                        req.user_id, req.message, reply, dense_vec=rag_dense_vec
                    )

                # Trigger background memory check if message count is a multiple of 3
                await trigger_background_memory_workflow(req.user_id, req.thread_id)
                
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


