from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from src.app.core.config import settings
from src.app.graphs.state import AgentState

class RouterOutput(BaseModel):
    next_node: Literal["rag_agent", "booking_agent", "query_agent", "FINISH"] = Field(
        description="The next agent to route to, or FINISH if we have fully addressed the request."
    )
    reasoning: str = Field(
        description="Brief reasoning for routing decision."
    )

async def supervisor_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Supervisor Agent: Reviews the conversation history and selects the appropriate 
    specialist node to run next, or terminates when the request is fully handled.
    """
    messages = state["messages"]
    
    # Standard LLM setup
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=settings.OPENAI_API_KEY,
        temperature=0.0
    )
    structured_llm = llm.with_structured_output(RouterOutput)
    
    system_prompt = (
        "You are the central Coordinator/Supervisor for VRSA AGROTECH customer service.\n"
        "Your job is to read the conversation and decide which specialist agent to call next:\n\n"
        "1. 'rag_agent': Use this specialist for queries about company products, recommendations of animal feed/nutrition, "
        "   animal use cases, product ingredients, instructions, and standard Q&A. This agent retrieves grounded files.\n"
        "2. 'booking_agent': Use this specialist when the user wants to book/order products, check order status, or list their bookings.\n"
        "3. 'query_agent': Use this specialist when the user wants to file a support ticket, raise a query, or view their support queries.\n"
        "4. 'FINISH': Use this when the specialist has completed their task and returned a final answer, or if the user is just "
        "   engaging in simple chitchat/greetings/social banter that can be handled directly by finishing.\n\n"
        "Analyze the message flow. If a specialist agent has just returned an answer that resolves the last query, select FINISH.\n"
    )
    
    # Call the router model
    payload = [{"role": "system", "content": system_prompt}] + messages
    decision = await structured_llm.ainvoke(payload, config)
    
    # Return the routing state change
    return {
        "next": decision.next_node
    }
