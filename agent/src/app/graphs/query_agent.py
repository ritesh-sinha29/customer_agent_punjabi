from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from src.app.core.config import settings
from src.app.graphs.state import AgentState
from src.app.tools.query_tools import get_user_queries, create_query

class QueryExtraction(BaseModel):
    title: Optional[str] = Field(
        None, description="A brief summary or title of the support query/ticket."
    )
    description: Optional[str] = Field(
        None, description="Detailed explanation of the issue or support request."
    )
    is_ready: bool = Field(
        False, description="Set to True ONLY if both title and description are extracted/ready."
    )
    list_queries_requested: bool = Field(
        False, description="Set to True if the user is asking to list, show, or check their existing tickets/queries."
    )

async def query_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Query Agent: Extracts parameters for support ticket creation or listings, 
    and handles tool routing or HITL initialization.
    """
    messages = state["messages"]
    user_id = state.get("user_id", "guest_user")
    
    # 1. Initialize LLM
    llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=settings.OPENAI_API_KEY, temperature=0.0)
    structured_llm = llm.with_structured_output(QueryExtraction)
    
    # 2. Extract user intent
    system_instruction = (
        "You are the Support Specialist for VRSA AGROTECH.\n"
        "Analyze the user conversation and extract details about support tickets/queries:\n"
        "1. Identify if they want to create/open a new support query, ticket or request. Extract title and description.\n"
        "2. Identify if they want to list or view their existing support queries/tickets.\n"
    )
    
    extraction = await structured_llm.ainvoke(
        [{"role": "system", "content": system_instruction}] + messages,
        config
    )
    
    # Case A: User wants to view existing support tickets
    if extraction.list_queries_requested:
        try:
            queries = get_user_queries(user_id=user_id)
            if not queries:
                reply = "You do not have any open support queries at the moment."
            else:
                reply = "Here are your recent support queries:\n"
                for idx, q in enumerate(queries, 1):
                    reply += f"{idx}. **Title**: {q['title']}, **Status**: {q['status']} (Created: {q['created_at'].strftime('%Y-%m-%d') if q.get('created_at') else 'N/A'})\n"
        except Exception as e:
            reply = f"Failed to retrieve queries: {str(e)}"
            
        return {
            "messages": [AIMessage(content=reply, name="query_agent")],
            "next": "supervisor"
        }
        
    # Case B: User wants to file a new query/ticket
    if extraction.is_ready and extraction.title and extraction.description:
        # Save proposed ticket details in state for HITL validation
        pending_action = {
            "action": "create_query",
            "title": extraction.title,
            "description": extraction.description
        }
        
        confirm_message = (
            f"I have drafted a support ticket for you:\n"
            f"- **Title**: {extraction.title}\n"
            f"- **Description**: {extraction.description}\n\n"
            "Would you like to confirm and file this support query?"
        )
        
        return {
            "messages": [AIMessage(content=confirm_message, name="query_agent")],
            "pending_action_details": pending_action,
            "next": "execute_query"
        }
        
    # Case C: Ask user for clarification
    clarification_prompt = (
        "You are the Support Agent at VRSA AGROTECH. The user wants to file a support ticket, but you are missing "
        "either the title or details/description. Reply politely asking them for the missing details."
    )
    reply_response = await llm.ainvoke(
        [{"role": "system", "content": clarification_prompt}] + messages,
        config
    )
    return {
        "messages": [AIMessage(content=reply_response.content, name="query_agent")],
        "next": "supervisor"
    }

async def execute_query_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Support Query write execution node. This node is placed behind an interrupt barrier (HITL).
    It only runs when approved by the user/system.
    """
    pending = state.get("pending_action_details")
    user_id = state.get("user_id", "guest_user")
    
    # Check if approved
    if not pending or pending.get("action") != "create_query":
        return {
            "messages": [AIMessage(content="Support query creation cancelled.", name="query_agent")],
            "pending_action_details": None,
            "next": "supervisor"
        }
        
    title = pending["title"]
    description = pending["description"]
    
    try:
        record = create_query(user_id=user_id, title=title, description=description)
        reply = (
            f"✅ **Support ticket created successfully!**\n"
            f"- Ticket ID: `{record['id']}`\n"
            f"- Title: {title}\n"
            f"- Status: {record['status']}.\n\n"
            "Our support team will review it and update you shortly."
        )
    except Exception as e:
        reply = f"Sorry, I encountered an error while filing your support ticket: {str(e)}"
        
    return {
        "messages": [AIMessage(content=reply, name="query_agent")],
        "pending_action_details": None,
        "next": "supervisor"
    }
