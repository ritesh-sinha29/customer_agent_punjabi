from langgraph.graph import StateGraph, START, END
from src.app.graphs.state import AgentState
from src.app.graphs.supervisor import supervisor_node
from src.app.graphs.rag_agent import rag_agent_node
from src.app.graphs.booking_agent import booking_agent_node, execute_booking_node
from src.app.graphs.query_agent import query_agent_node, execute_query_node
from src.app.graphs.checkpointer import get_redis_checkpointer

def create_agent_graph():
    builder = StateGraph(AgentState)
    
    # 1. Register all nodes in the graph
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("rag_agent", rag_agent_node)
    builder.add_node("booking_agent", booking_agent_node)
    builder.add_node("execute_booking", execute_booking_node)
    builder.add_node("query_agent", query_agent_node)
    builder.add_node("execute_query", execute_query_node)
    
    # 2. Define standard flow starting at supervisor
    builder.add_edge(START, "supervisor")
    
    # Supervisor conditional routing
    def route_supervisor(state: AgentState):
        nxt = state.get("next")
        if nxt == "FINISH" or not nxt:
            return END
        return nxt
        
    builder.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "rag_agent": "rag_agent",
            "booking_agent": "booking_agent",
            "query_agent": "query_agent",
            END: END
        }
    )
    
    # specialist nodes transition back
    builder.add_edge("rag_agent", "supervisor")
    
    # Booking agent conditional check for write approval transition
    def route_booking(state: AgentState):
        if state.get("next") == "execute_booking":
            return "execute_booking"
        return "supervisor"
    builder.add_conditional_edges("booking_agent", route_booking, ["execute_booking", "supervisor"])
    builder.add_edge("execute_booking", "supervisor")
    
    # Query agent conditional check for write approval transition
    def route_query(state: AgentState):
        if state.get("next") == "execute_query":
            return "execute_query"
        return "supervisor"
    builder.add_conditional_edges("query_agent", route_query, ["execute_query", "supervisor"])
    builder.add_edge("execute_query", "supervisor")
    
    # 3. Compile with the Upstash Redis Checkpointer and HITL interrupt barriers
    checkpointer = get_redis_checkpointer()
    
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["execute_booking", "execute_query"]
    )

agent_graph = create_agent_graph()
