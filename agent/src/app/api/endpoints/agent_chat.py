import asyncio
import io
import json
import logging
import os
import re
import sys
import time
import uuid

# Fix Windows charmap codec UnicodeEncodeError when printing emojis to console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from src.app.graphs.graph import agent_graph
from src.app.services.db_service import db_service
from src.app.services.deepeval_server_evaluator import trigger_live_deepeval
from src.app.services.semantic_cache_service import semantic_cache_service
from src.app.services.translation_service import translation_service

try:
    from src.app.core.guardrail_service import AgentGuardrailService
except ImportError:
    from app.core.guardrail_service import AgentGuardrailService

logger = logging.getLogger("AgentChatApi")
router = APIRouter(prefix="/v1/agent", tags=["Agent Chat"])


class TranslateRequest(BaseModel):
    text: str


def print_console_execution_summary(
    start_time: float,
    user_query: str,
    nodes_called: List[str],
    tools_called: List[str],
    final_state: Dict[str, Any],
    clean_reply: str,
    first_token_time: float = None,
):
    e2e_latency = time.time() - start_time
    ttft_ms = ((first_token_time - start_time) * 1000) if first_token_time else 0.0

    facts = final_state.get("internal_facts", []) if final_state else []
    facts_count = len(facts)
    query_snippet = user_query[:50] + "..." if len(user_query) > 50 else user_query

    print("\n" + "=" * 65, flush=True)
    print(f" REAL EXECUTION METRICS [Query: '{query_snippet}']", flush=True)
    print(f"   • Total E2E Latency:          {e2e_latency:.2f} s", flush=True)
    if ttft_ms > 0:
        print(f"   • TTFT (Time to First Token): {ttft_ms:.1f} ms", flush=True)
    print(f"   • Sub-Agents Executed ({len(nodes_called)}):   {nodes_called}", flush=True)
    if tools_called:
        print(f"   • Tools Invoked ({len(tools_called)}):     {tools_called}", flush=True)
    print(f"   • Verified Facts Synthesized: {facts_count}", flush=True)
    print("=" * 65 + "\n", flush=True)


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
                    execution_timeout=timedelta(seconds=25),
                ),
                timeout=25.0,
            )
        except Exception as te:
            logger.warning(
                f"Temporal translation workflow execution warning ({te}). Falling back to fast direct translation..."
            )
            translated = await asyncio.wait_for(
                translation_service.translate_to_punjabi(req.text), timeout=25.0
            )

        if not translated:
            raise HTTPException(
                status_code=500, detail="Translation returned empty result."
            )

        return {"success": True, "translated_text": translated}
    except asyncio.TimeoutError:
        logger.error("Translation request timed out after 25 seconds.")
        raise HTTPException(
            status_code=504, detail="Translation timed out after 25 seconds."
        )
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
            logger.info(
                f"Message count is {count} (multiple of 4 - equivalent to 2 turns). Launching Temporal UserMemoryWorkflow in background."
            )
            from src.app.temporal.temporal_client import get_temporal_client

            temporal_client = await get_temporal_client()
            await temporal_client.start_workflow(
                "UserMemoryWorkflow",
                args=[user_id, thread_id],
                id=f"user-memory-workflow-{user_id}-{thread_id}-{int(time.time())}",
                task_queue="ingestion-task-queue",
            )
    except Exception as te:
        logger.error(f"Failed to start background memory Temporal workflow: {te}")


async def save_user_message(thread_id: str, user_id: str, message: str):
    try:
        thread_exists = await db_service.aexecute_query(
            "SELECT 1 FROM chat_thread WHERE id = %s", (thread_id,)
        )
        if not thread_exists:
            title = message[:50] + "..." if len(message) > 50 else message
            await db_service.aexecute_insert(
                "INSERT INTO chat_thread (id, title, user_id) VALUES (%s, %s, %s)",
                (thread_id, title, user_id),
            )
        msg_id = f"msg-user-{uuid.uuid4()}"
        await db_service.aexecute_insert(
            "INSERT INTO chat_message (id, thread_id, role, content) VALUES (%s, %s, %s, %s)",
            (msg_id, thread_id, "user", message),
        )
    except Exception as e:
        logger.error(f"Error saving user message: {e}")


async def save_assistant_message(thread_id: str, content: str):
    try:
        msg_id = f"msg-assistant-{uuid.uuid4()}"
        await db_service.aexecute_insert(
            "INSERT INTO chat_message (id, thread_id, role, content) VALUES (%s, %s, %s, %s)",
            (msg_id, thread_id, "assistant", content),
        )
        await db_service.aexecute_insert(
            "UPDATE chat_thread SET updated_at = NOW() WHERE id = %s", (thread_id,)
        )
    except Exception as e:
        logger.error(f"Error saving assistant message: {e}")


async def get_slim_user_profile(user_id: str) -> dict:
    """
    Fetches a slim, lightweight core memory context (max 3 recent facts, 1 recent summary)
    to keep context small and fast without fetching heavy memory every message turn.
    """
    try:
        memory_row = await db_service.aexecute_query(
            "SELECT semantic_facts, episodic_summaries FROM user_memory WHERE user_id = %s",
            (user_id,),
        )
        if memory_row:
            facts = memory_row[0].get("semantic_facts") or []
            summaries = memory_row[0].get("episodic_summaries") or []
            return {
                "semantic_facts": facts[-3:] if facts else [],
                "episodic_summaries": summaries[-1:] if summaries else [],
            }
    except Exception as me:
        logger.error(f"Error loading user profile memory: {me}")
    return {"semantic_facts": [], "episodic_summaries": []}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User message payload constrained to max 2000 characters.")
    thread_id: str = Field(..., min_length=1, max_length=100)
    user_id: str = Field(..., min_length=1, max_length=100)
    approve: Optional[bool] = None  # None: regular chat; True/False: HITL approval


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
    start_time = time.time()
    config = {
        "configurable": {"thread_id": req.thread_id},
        "metadata": {
            "langfuse_session_id": req.thread_id,
            "langfuse_user_id": req.user_id,
        },
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
                    detail="Graph is waiting for approval. Please specify 'approve' as True or False.",
                )

            if req.approve:
                # User approved: resume execution
                logger.info(
                    f"User approved pending action for thread {req.thread_id}. Resuming..."
                )
                await save_user_message(req.thread_id, req.user_id, "Yes, confirm.")
                final_state = await agent_graph.ainvoke(None, config)
            else:
                # User rejected: clear the pending action to cancel database write and resume
                logger.info(
                    f"User rejected pending action for thread {req.thread_id}. Cancelling and resuming..."
                )
                await save_user_message(req.thread_id, req.user_id, "No, cancel.")
                await agent_graph.aupdate_state(
                    config, {"pending_action_details": None}
                )
                final_state = await agent_graph.ainvoke(None, config)
        else:
            # 3. Standard execution flow
            if not req.message.strip():
                raise HTTPException(status_code=400, detail="Message cannot be empty.")

            # Check Semantic Cache first
            cached_data = await semantic_cache_service.get_cached_response(
                req.user_id, req.message
            )
            if cached_data:
                await save_user_message(req.thread_id, req.user_id, req.message)
                await save_assistant_message(req.thread_id, cached_data["response"])
                return {
                    "success": True,
                    "status": "completed",
                    "response": cached_data["response"],
                    "thread_id": req.thread_id,
                    "cached": True,
                }

            await save_user_message(req.thread_id, req.user_id, req.message)

            # Fetch slim, lightweight user core memory context
            user_profile = await get_slim_user_profile(req.user_id)

            initial_state = {
                "messages": [HumanMessage(content=req.message)],
                "user_id": req.user_id,
                "user_profile": user_profile,
                "internal_facts": [],
                "action_type": None,
                "pending_action_details": None,
            }
            final_state = await agent_graph.ainvoke(initial_state, config)

        # 4. Check if the graph has entered a new interrupt state (needs approval)
        new_state = await agent_graph.aget_state(config)
        if new_state.next:
            pending_action = new_state.next[0]
            # Find the last message (which is the confirmation prompt from the specialist agent)
            last_message = (
                new_state.values["messages"][-1].content
                if new_state.values.get("messages")
                else ""
            )
            await save_assistant_message(req.thread_id, last_message)

            return {
                "success": True,
                "status": "pending_approval",
                "pending_action": "booking" if "booking" in pending_action else "query",
                "details": new_state.values.get("pending_action_details"),
                "response": last_message,
                "thread_id": req.thread_id,
            }

        # 5. Otherwise, return the final response
        assistant_messages = [
            msg.content for msg in final_state["messages"] if msg.type == "ai"
        ]
        reply = (
            assistant_messages[-1]
            if assistant_messages
            else "I couldn't process your request."
        )
        await save_assistant_message(req.thread_id, reply)

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

        # Trigger background DeepEval metrics evaluation (0 added latency to user response)
        trigger_live_deepeval(req.message, reply, final_state)

        # Print structured console diagnostics and live benchmark scorecard
        print_console_execution_summary(
            start_time=start_time,
            user_query=req.message,
            nodes_called=[],
            tools_called=[],
            final_state=final_state,
            clean_reply=reply,
        )

        return {
            "success": True,
            "status": "completed",
            "response": reply,
            "thread_id": req.thread_id,
        }

    except Exception as e:
        logger.error(f"Agent Graph execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent Graph Error: {str(e)}")


@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest, request: Request):
    config = {
        "configurable": {"thread_id": req.thread_id},
        "metadata": {
            "langfuse_session_id": req.thread_id,
            "langfuse_user_id": req.user_id,
        },
    }

    nodes_called_order = []
    tools_called_order = []

    timing_tracker = {"first_token_time": None}

    async def process_stream_events(stream_iterator):
        reasoning_sent = False
        last_status = ""

        async for event in stream_iterator:
            if await request.is_disconnected():
                logger.info("[STREAM CANCELLATION] Client tab disconnected mid-flight. Stopping stream execution.")
                break

            kind = event.get("event")
            node_name = event.get("metadata", {}).get("langgraph_node", "")
            event_name = event.get("name", "")
            target = node_name or event_name

            # Emit real-time status updates & console logs as graph nodes & subagents begin
            if kind in ["on_chain_start", "on_node_start"]:
                if node_name and node_name not in nodes_called_order:
                    nodes_called_order.append(node_name)
                    logger.info(f"AGENT CALLED: {node_name}")
                    yield f"data: {json.dumps({'type': 'agent_call', 'agent': node_name, 'content': f'{node_name} called'})}\n\n"

                status_msg = None
                if target == "supervisor_router":
                    status_msg = "Analyzing query intent & checking workflow routing..."
                elif target == "rag_agent":
                    status_msg = (
                        "Generating contents and looking into company Knowledge Base..."
                    )
                elif target in ["booking_node", "booking_agent", "booking_read_agent"]:
                    status_msg = "Processing product booking & checking inventory..."
                elif target in ["query_node", "query_agent", "query_read_agent"]:
                    status_msg = "Processing support ticket & reviewing inquiries..."
                elif target == "deep_memory_node":
                    status_msg = "Consulting user memory & historical farmer facts..."
                elif target == "web_search_fanout":
                    status_msg = (
                        "Decomposing query into 3 parallel search perspectives..."
                    )
                elif target == "web_search_worker":
                    status_msg = "Executing parallel Tavily web search..."
                elif target == "critic_agent":
                    status_msg = "Critic Agent evaluating, de-duplicating & verifying web facts..."
                elif target == "supervisor_sales_agent":
                    status_msg = (
                        "Consulting agricultural knowledge base & composing response..."
                    )

                if status_msg and status_msg != last_status:
                    last_status = status_msg
                    yield f"data: {json.dumps({'type': 'status', 'content': status_msg})}\n\n"

            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                if tool_name and tool_name not in tools_called_order:
                    tools_called_order.append(tool_name)
                    logger.info(f"TOOL CALLED: {tool_name}")
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'content': f'{tool_name} called'})}\n\n"

                status_msg = None
                if tool_name in ["run_rag_agent", "retrieval_service"]:
                    status_msg = "Searching vector database & embedding documents..."
                elif tool_name in ["create_booking", "get_booking_updates"]:
                    status_msg = "Booking product & saving transaction record..."
                elif tool_name in ["create_query", "get_user_queries"]:
                    status_msg = "Submitting customer support ticket..."

                if status_msg and status_msg != last_status:
                    last_status = status_msg
                    yield f"data: {json.dumps({'type': 'status', 'content': status_msg})}\n\n"

            if kind == "on_chat_model_stream":
                # Only stream tokens from the final response generator (supervisor_sales_agent)
                if node_name != "supervisor_sales_agent":
                    continue
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    token = chunk.content
                    if token and isinstance(token, str):
                        if timing_tracker["first_token_time"] is None:
                            timing_tracker["first_token_time"] = time.time()
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            elif kind in ["on_chat_model_end", "on_chain_end", "on_node_end"]:
                if node_name == "web_search_worker":
                    output = event.get("data", {}).get("output")
                    if isinstance(output, dict) and "web_search_worker_items" in output:
                        items = output.get("web_search_worker_items", [])
                        if items and isinstance(items, list):
                            yield f"data: {json.dumps({'type': 'web_search_worker_results', 'results': items})}\n\n"
                elif node_name == "web_search_fanout":
                    output = event.get("data", {}).get("output")
                    if isinstance(output, dict) and "web_search_queries" in output:
                        queries = output.get("web_search_queries", [])
                        if queries and isinstance(queries, list):
                            yield f"data: {json.dumps({'type': 'web_search_queries', 'queries': queries})}\n\n"
                elif node_name == "supervisor_router" and not reasoning_sent:
                    output = event.get("data", {}).get("output")
                    reasoning = extract_reasoning(output)
                    if reasoning:
                        reasoning_sent = True
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning})}\n\n"
                elif node_name in ["booking_agent", "query_agent"]:
                    yield f"data: {json.dumps({'type': 'tool_success', 'tool': 'create_booking' if node_name == 'booking_agent' else 'create_query'})}\n\n"
            elif kind == "on_tool_end" and event.get("name") in [
                "create_booking",
                "create_query",
            ]:
                yield f"data: {json.dumps({'type': 'tool_success', 'tool': event.get('name')})}\n\n"

    async def event_generator():
        start_time = time.time()
        cb = get_langfuse_callback()
        if cb:
            config["callbacks"] = [cb]

        try:
            yield f"data: {json.dumps({'type': 'status', 'content': 'Thinking...'})}\n\n"

            # 1. Fetch current state of the conversation thread
            state = await agent_graph.aget_state(config)

            # 2. Check if the graph is currently interrupted and waiting for HITL approval
            if state.next:
                if req.approve is None:
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Graph is waiting for approval. Please specify approve as True or False.'})}\n\n"
                    return

                if req.approve:
                    # User approved: resume execution
                    logger.info(
                        f"User approved pending action for thread {req.thread_id}. Resuming..."
                    )
                    asyncio.create_task(save_user_message(req.thread_id, req.user_id, "Yes, confirm."))
                    async for chunk in process_stream_events(
                        agent_graph.astream_events(None, config, version="v2")
                    ):
                        yield chunk
                else:
                    # User rejected: clear the pending action to cancel database write and resume
                    logger.info(
                        f"User rejected pending action for thread {req.thread_id}. Cancelling and resuming..."
                    )
                    asyncio.create_task(save_user_message(req.thread_id, req.user_id, "No, cancel."))
                    await agent_graph.aupdate_state(
                        config, {"pending_action_details": None}
                    )
                    async for chunk in process_stream_events(
                        agent_graph.astream_events(None, config, version="v2")
                    ):
                        yield chunk
            else:
                # 3. Standard execution flow
                if not req.message.strip():
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Message cannot be empty.'})}\n\n"
                    return

                # PARALLEL PRE-GRAPH EXECUTION: Fire Guardrails, Cache Check & Profile Fetch concurrently!
                guardrail_svc = AgentGuardrailService.get_instance()
                
                guardrail_task = asyncio.create_task(guardrail_svc.validate_input(req.message))
                cache_task = asyncio.create_task(semantic_cache_service.get_cached_response(req.user_id, req.message))
                profile_task = asyncio.create_task(get_slim_user_profile(req.user_id))

                # Fire DB message save in background (non-blocking, 0ms wait for user)
                asyncio.create_task(save_user_message(req.thread_id, req.user_id, req.message))

                # Await Guardrail & Cache check concurrently
                (is_safe, sanitized_input, refusal_reason) = await guardrail_task
                cached_data = await cache_task

                if not is_safe:
                    logger.warning(
                        f"[GUARDRAIL BLOCKED] Thread {req.thread_id} | User {req.user_id}: {req.message}"
                    )
                    refusal_text = (
                        refusal_reason
                        or "I cannot process this request because it violates safety policies and security rules."
                    )
                    asyncio.create_task(save_assistant_message(req.thread_id, refusal_text))

                    yield f"data: {json.dumps({'type': 'error', 'error': refusal_text})}\n\n"
                    yield f"data: {json.dumps({'type': 'token', 'content': refusal_text})}\n\n"
                    payload = {
                        "type": "completed",
                        "status": "completed",
                        "response": refusal_text,
                        "thread_id": req.thread_id,
                        "guardrail_blocked": True,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    return

                user_message_to_process = sanitized_input

                if cached_data:
                    asyncio.create_task(save_assistant_message(req.thread_id, cached_data["response"]))
                    yield f"data: {json.dumps({'type': 'reasoning', 'content': 'Retrieved instantly from 7-day Semantic Cache.'})}\n\n"
                    yield f"data: {json.dumps({'type': 'token', 'content': cached_data['response']})}\n\n"
                    payload = {
                        "type": "completed",
                        "status": "completed",
                        "response": cached_data["response"],
                        "thread_id": req.thread_id,
                        "cached": True,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    return

                # Await user profile memory (which was already running in parallel!)
                user_profile = await profile_task

                initial_state = {
                    "messages": [HumanMessage(content=user_message_to_process)],
                    "user_id": req.user_id,
                    "user_profile": user_profile,
                    "internal_facts": [],
                    "action_type": None,
                    "pending_action_details": None,
                }

                yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing intent & generating response...'})}\n\n"
                async for chunk in process_stream_events(
                    agent_graph.astream_events(initial_state, config, version="v2")
                ):
                    yield chunk

            # 4. Check if the graph has entered a new interrupt state (needs approval) or completed
            new_state = await agent_graph.aget_state(config)
            if new_state.next:
                pending_action = new_state.next[0]
                last_message = (
                    new_state.values["messages"][-1].content
                    if new_state.values.get("messages")
                    else ""
                )
                await save_assistant_message(req.thread_id, last_message)

                payload = {
                    "type": "pending_approval",
                    "status": "pending_approval",
                    "pending_action": "booking"
                    if "booking" in pending_action
                    else "query",
                    "details": new_state.values.get("pending_action_details"),
                    "response": last_message,
                    "thread_id": req.thread_id,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                assistant_messages = [
                    msg.content
                    for msg in new_state.values.get("messages", [])
                    if msg.type == "ai"
                ]
                reply = (
                    assistant_messages[-1]
                    if assistant_messages
                    else "I couldn't process your request."
                )

                # Extract and strip <suggested_actions> tag if present
                suggested_actions = new_state.values.get("suggested_actions") or []
                if not suggested_actions and reply:
                    match = re.search(
                        r"<suggested_actions>\s*(.*?)\s*</suggested_actions>",
                        reply,
                        re.DOTALL,
                    )
                    if match:
                        lines = match.group(1).strip().split("\n")
                        for line_item in lines:
                            cleaned_act = re.sub(
                                r"^\s*[-*\d.]+\s*", "", line_item
                            ).strip()
                            if cleaned_act:
                                suggested_actions.append(cleaned_act)
                        suggested_actions = suggested_actions[:3]

                clean_reply = re.sub(
                    r"<suggested_actions>\s*.*?\s*</suggested_actions>",
                    "",
                    reply,
                    flags=re.DOTALL,
                ).strip()
                await save_assistant_message(req.thread_id, clean_reply)

                # Store in 7-day Semantic Cache (reusing rag_dense_vec from RAG with 0 extra API calls)
                if req.approve is None and clean_reply:
                    rag_dense_vec = None
                    for item in new_state.values.get("internal_facts", []):
                        if (
                            isinstance(item, dict)
                            and item.get("subagent") == "rag_agent"
                        ):
                            rag_dense_vec = item.get("rag_dense_vec")
                            break
                    await semantic_cache_service.set_cached_response(
                        req.user_id, req.message, clean_reply, dense_vec=rag_dense_vec
                    )

                # Print structured, zero-latency console diagnostics summary and benchmark scorecard
                print_console_execution_summary(
                    start_time=start_time,
                    user_query=req.message,
                    nodes_called=nodes_called_order,
                    tools_called=tools_called_order,
                    final_state=new_state.values,
                    clean_reply=clean_reply,
                    first_token_time=timing_tracker["first_token_time"],
                )

                # Trigger background memory check if message count is a multiple of 3
                await trigger_background_memory_workflow(req.user_id, req.thread_id)

                # Trigger background DeepEval metrics evaluation (0 added latency)
                trigger_live_deepeval(req.message, clean_reply, new_state.values)

                payload = {
                    "type": "completed",
                    "status": "completed",
                    "response": clean_reply,
                    "suggested_actions": suggested_actions,
                    "thread_id": req.thread_id,
                }
                yield f"data: {json.dumps(payload)}\n\n"

        except Exception as e:
            logger.error(f"Streaming endpoint error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': f'Agent Graph Error: {str(e)}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
