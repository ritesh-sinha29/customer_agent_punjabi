from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from src.app.services.query_optimizer import query_optimizer
from src.app.services.retrieval_service import retrieval_service
from src.app.core.config import settings
from langchain_openai import ChatOpenAI
from src.app.graphs.state import AgentState

async def rag_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    RAG Agent: Performs query expansion/optimization, executes parallel dense+sparse 
    hybrid search, applies Jina/RRF reranking, and answers questions grounded in 
    VRSA Agrotech documentation.
    """
    # 1. Extract messages
    messages = state["messages"]
    if not messages:
        return {"next": "supervisor"}
        
    current_query = messages[-1].content
    
    # 2. Format past conversation history for the query optimizer
    chat_history = []
    for msg in messages[:-1]:
        role = "user" if msg.type == "human" else "assistant"
        chat_history.append({"role": role, "content": msg.content})
        
    user_id = state.get("user_id", "guest_user")
    
    # 3. Optimize the query (expands to 3 English variations)
    optimized_queries = query_optimizer.optimize_query(
        chat_history=chat_history,
        current_query=current_query,
        user_id=user_id
    )
    
    # 4. Perform parallel hybrid search and rerank
    chunks = await retrieval_service.retrieve_parallel(
        queries=optimized_queries,
        top_k=4,
        namespace="default",
        user_id=user_id,
        original_query=current_query
    )
    
    # 5. Format retrieved documents context
    context_str = ""
    for idx, match in enumerate(chunks, 1):
        text = match.get("metadata", {}).get("text", "")
        context_str += f"[{idx}] (Score: {match.get('score', 0.0):.4f}): {text}\n\n"
        
    # 6. Call the OpenAI model with grounded context
    system_prompt = (
        "You are an expert animal nutrition advisor at VRSA AGROTECH.\n"
        "Your task is to answer the user's questions about company products, animal recommendations, "
        "and nutritional advice based on the retrieved contexts below.\n\n"
        f"Retrieved Documentation:\n{context_str}\n"
        "Instructions:\n"
        "- Use the retrieved documentation to address the user's query.\n"
        "- Do not say that you do not know or that information is not available. Always provide a helpful and informative response using the retrieved context.\n"
        "- If the retrieved documentation does not explicitly cover the exact question (such as specific fat content numbers or milk quality details), connect the query to the general benefits of the relevant products in the context (like MaxaPro-DS Dairy supporting lactation efficiency, rumen health, and milk yield consistency or Buffalo-Power 2X supporting buffalo rumen efficiency and milk yield) and explain how these products can help the user's animal.\n"
        "- Be encouraging, professional, and helpful. Always provide a proper response.\n"
        "- Respond in a clear format. You must write your response in English only, even if the user asked their question in Punjabi or Hinglish."
    )
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=settings.OPENAI_API_KEY,
        temperature=0.0,
        streaming=True
    )
    
    # Pass config so that Langfuse callbacks and telemetry trace the LLM run
    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": current_query}
    ]
    response = await llm.ainvoke(prompt, config)
    
    # Return message and route back to supervisor
    return {
        "messages": [AIMessage(content=response.content, name="rag_agent")],
        "next": "supervisor"
    }
