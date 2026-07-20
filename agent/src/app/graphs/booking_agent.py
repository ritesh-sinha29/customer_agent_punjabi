from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from src.app.core.config import settings
from src.app.graphs.state import AgentState
from src.app.tools.booking_tools import get_booking_updates, create_booking, get_canonical_product_name

class BookingExtraction(BaseModel):
    product_name: Optional[str] = Field(
        None, description="The name of the product the user wants to book (e.g., 'Horsa', 'TrioSan', 'Buffalo Power')."
    )
    quantity: Optional[int] = Field(
        None, description="The integer quantity of the product. None if not specified."
    )
    is_ready: bool = Field(
        False, description="Set to True ONLY if both product_name and quantity are clearly identified in the request."
    )
    list_bookings_requested: bool = Field(
        False, description="Set to True if the user is asking to list, show, check, or view their existing bookings."
    )

async def booking_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Booking Agent: Resolves product listing requests directly or extracts parameters
    for creating a booking and passes them to the execute_booking node via HITL state.
    """
    messages = state["messages"]
    user_id = state.get("user_id", "guest_user")
    
    # 1. Initialize LLM
    llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=settings.OPENAI_API_KEY, temperature=0.0, streaming=True)
    structured_llm = llm.with_structured_output(BookingExtraction)
    
    # 2. Extract user intent
    system_instruction = (
        "You are the Booking Specialist for VRSA AGROTECH.\n"
        "Analyze the user conversation and extract details about product booking requests:\n"
        "1. Identify if they want to book/order a product and extract product name and quantity.\n"
        "2. Identify if they want to check or list their existing bookings/orders.\n"
    )
    
    extraction = await structured_llm.ainvoke(
        [{"role": "system", "content": system_instruction}] + messages,
        config
    )
    
    # Case A: User wants to view existing bookings
    if extraction.list_bookings_requested:
        try:
            bookings = get_booking_updates(user_id=user_id)
            if not bookings:
                reply = "You do not have any bookings at the moment."
            else:
                reply = "Here are your recent bookings:\n"
                for idx, b in enumerate(bookings, 1):
                    reply += f"{idx}. **Product**: {b['product_name']}, **Qty**: {b['qty']}, **Status**: {b['status']} (Created: {b['created_at'].strftime('%Y-%m-%d') if b.get('created_at') else 'N/A'})\n"
        except Exception as e:
            reply = f"Failed to retrieve bookings: {str(e)}"
            
        return {
            "messages": [AIMessage(content=reply, name="booking_agent")],
            "next": "supervisor"
        }
        
    # Case B: User wants to book a product and we have the parameters
    if extraction.is_ready and extraction.product_name and extraction.quantity:
        try:
            # Validate and map to canonical name first
            canonical_name = get_canonical_product_name(extraction.product_name)
            
            # Save proposed booking details in state for HITL validation
            pending_action = {
                "action": "create_booking",
                "product_name": canonical_name,
                "quantity": extraction.quantity
            }
            
            confirm_message = (
                f"I've prepared a booking request for **{extraction.quantity}x {canonical_name}**. "
                "Would you like to confirm and place this booking?"
            )
            
            return {
                "messages": [AIMessage(content=confirm_message, name="booking_agent")],
                "pending_action_details": pending_action,
                "next": "execute_booking"
            }
            
        except ValueError as ve:
            # Handle invalid product name validation error gracefully
            reply = (
                f"I could not identify the product '{extraction.product_name}'. "
                "Please specify one of our valid products: Horsa-550X-Turbo, TrioSan Gold, "
                "MaxaPro-DS Dairy, MaxaPro Liquid, Buffalo-Power 2X, or Buffalo-F 1.5X."
            )
            return {
                "messages": [AIMessage(content=reply, name="booking_agent")],
                "next": "supervisor"
            }
            
    # Case C: More info needed from user
    clarification_prompt = (
        "You are the Booking Agent at VRSA AGROTECH. The user wants to book a product, but you are missing "
        "either the product name or the quantity. Reply politely asking them for the missing details. "
        "Keep it concise."
    )
    reply_response = await llm.ainvoke(
        [{"role": "system", "content": clarification_prompt}] + messages,
        config
    )
    return {
        "messages": [AIMessage(content=reply_response.content, name="booking_agent")],
        "next": "supervisor"
    }

async def execute_booking_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Booking write execution node. This node is placed behind an interrupt barrier (HITL).
    It only runs when approved by the user/system.
    """
    pending = state.get("pending_action_details")
    user_id = state.get("user_id", "guest_user")
    
    # If approval wasn't granted or details got cleared
    if not pending or pending.get("action") != "create_booking":
        return {
            "messages": [AIMessage(content="Booking cancelled or no booking details found.", name="booking_agent")],
            "pending_action_details": None,
            "next": "supervisor"
        }
        
    product_name = pending["product_name"]
    quantity = pending["quantity"]
    
    try:
        record = create_booking(user_id=user_id, product_name=product_name, qty=quantity)
        reply = (
            f"🎉 **Booking confirmed!** Your order for **{quantity}x {product_name}** has been placed successfully. "
            f"Booking ID: `{record['id']}`."
        )
    except Exception as e:
        reply = f"Sorry, I encountered an error while finalizing your booking: {str(e)}"
        
    return {
        "messages": [AIMessage(content=reply, name="booking_agent")],
        "pending_action_details": None,
        "next": "supervisor"
    }
