import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add project root to python path to resolve imports correctly
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Fix Windows console print for Unicode
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from langchain_core.messages import HumanMessage
from src.app.graphs.graph import agent_graph
from src.app.tools.booking_tools import get_booking_updates
from src.app.tools.query_tools import get_user_queries

async def test_flow():
    thread_id = f"test-thread-{uuid.uuid4().hex}"
    user_id = f"test-user-{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}
    
    print("\n--- 1. Testing RAG Agent Routing ---")
    # Ask about feed or general recommendation
    query = "What feed is best for dairy cattle to prevent milk fever?"
    print(f"User: {query}")
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "user_id": user_id
    }
    state = await agent_graph.ainvoke(initial_state, config)
    last_msg = state["messages"][-1].content
    print(f"Agent reply:\n{last_msg}")
    
    print("\n--- 2. Testing Booking Agent Routing & Interrupt (HITL) ---")
    query = "I want to book 5 bags of Horsa 550"
    print(f"User: {query}")
    # Run the graph
    state = await agent_graph.ainvoke({"messages": [HumanMessage(content=query)]}, config)
    
    # Check if graph paused
    current_state = await agent_graph.aget_state(config)
    print(f"Next expected node: {current_state.next}")
    print(f"Pending action details: {current_state.values.get('pending_action_details')}")
    
    # Assert interrupt
    assert current_state.next and "execute_booking" in current_state.next[0]
    
    print("\n--- 3. Testing Booking Approval (HITL Resume) ---")
    # Resume with approval
    state = await agent_graph.ainvoke(None, config)
    last_msg = state["messages"][-1].content
    print(f"Agent reply:\n{last_msg}")
    
    # Check if booking exists in Postgres DB
    bookings = get_booking_updates(user_id=user_id)
    print(f"Postgres verification: Found {len(bookings)} bookings for {user_id}")
    assert len(bookings) == 1
    assert bookings[0]["product_name"] == "Horsa-550X-Turbo"
    assert bookings[0]["qty"] == 5

    print("\n--- 4. Testing Query Agent Routing & Interrupt (HITL) ---")
    thread_id_2 = f"test-thread-2-{uuid.uuid4().hex}"
    config_2 = {"configurable": {"thread_id": thread_id_2}}
    query = "I want to file a support ticket because the motor pump is broken. Please open a query."
    print(f"User: {query}")
    state = await agent_graph.ainvoke({"messages": [HumanMessage(content=query)], "user_id": user_id}, config_2)
    
    # Check if graph paused
    current_state = await agent_graph.aget_state(config_2)
    print(f"Next expected node: {current_state.next}")
    print(f"Pending action details: {current_state.values.get('pending_action_details')}")
    
    # Assert interrupt
    assert current_state.next and "execute_query" in current_state.next[0]
    
    print("\n--- 5. Testing Query Cancellation (HITL Resume with cancel) ---")
    # Resume with cancellation by setting pending_action_details to None
    await agent_graph.aupdate_state(config_2, {"pending_action_details": None})
    state = await agent_graph.ainvoke(None, config_2)
    last_msg = state["messages"][-1].content
    print(f"Agent reply:\n{last_msg}")
    
    # Check if any queries exist in DB (should be 0)
    queries = get_user_queries(user_id=user_id)
    print(f"Postgres verification: Found {len(queries)} queries for {user_id}")
    assert len(queries) == 0

    print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_flow())
