temporal server start-dev

uv run python -m src.app.temporal.worker

cd agent
uv run uvicorn src.app.main:app --reload --port 8000

----------------------------------------------------------------------
Rag ques ans working snapshot --->

INFO:     127.0.0.1:62162 - "POST /api/v1/agent/chat/stream HTTP/1.1" 200 OK
[PASSED GUARDRAIL] PASSED user query: 'what is the exact nutrients in your all products , i want see facts . and why to book your products ?
what extra benefits i have'
INFO:AgentGuardrailService:PASSED user query: 'what is the exact nutrients in your all products , i want see facts . and why to book your products ?
what extra benefits i have'
17:58:17.227 LangGraph
INFO:AgentChatApi:AGENT CALLED: supervisor_router
17:58:17.571   supervisor_router
17:58:17.574     RunnableSequence
17:58:17.576       ChatOpenAI
17:58:18.458       PydanticToolsParser
INFO:SupervisorAgent:[SUPERVISOR ROUTER] Selected parallel sub-agents: ['rag_agent'] | Reasoning: User requests detailed nutrient facts for all products and benefits of booking them. This requires catalog information. No booking or support ticket needed.      
17:58:18.463     route_next
17:58:18.468   rag_agent
INFO:AgentChatApi:AGENT CALLED: rag_agent
17:58:18.476 optimize_query
INFO:QueryOptimizer:OpenAI gpt-4.1-mini generated expansions in <300ms: ['nutritional content of dairy and livestock feed products', 'benefits of booking VRSA AGROTECH animal nutrition products', 'detailed nutrient facts and advantages of livestock supplements']
17:58:20.366 Multi-query expansions generated
17:58:20.368 hybrid_retrieval_parallel
INFO:RetrievalService:Initiating parallel hybrid search for 3 queries...
17:58:20.375   Parallel hybrid search starting
INFO:EmbeddingService:[Step 4 - Embedding] Generating dense embeddings using Cohere embed-multilingual-v3.0 (1024d)...
17:58:21.255   hybrid-search-parallel
INFO:pinecone.index:Querying index with top_k=15
INFO:pinecone.index:Querying index with top_k=15
INFO:pinecone.index:Querying index with top_k=15
INFO:RerankingService:Fusing 3 parallel query result lists using local RRF (k=60)...
INFO:RerankingService:Local RRF completed. Fused to top 5 results.

================================================================================
BM25 HYBRID RETRIEVAL RESULTS (Original Query: 'what is the exact nutrients in your all products , i want see facts . and why to book your products ?
what extra benefits i have')
================================================================================
[1] [Score: 0.0474] # Table of Contents
[2] [Score: 0.0310] # 01 · About VRSA AGROTECH  VRSA AGROTECH is an animal health and nutrition company developing feed additives, mineral sources and liquid nutraceutica...
[3] [Score: 0.0308] # Step 2 — Rumen-Level Action  Fermentation metabolites and prebiotics support the growth of beneficial, fibre-digesting rumen bacteria, improving the...
[4] [Score: 0.0294] The company works with equine nutritionists, trainers and veterinary consultants to formulate products aimed at supporting performance, recovery and s...
[5] [Score: 0.0294] # Vision  To be India's most trusted multi-species animal nutrition partner by building a portfolio that treats buffalo, dairy cattle, poultry and hor...
================================================================================

INFO:RetrievalService:Retrieved and reranked 5 chunks from Pinecone.
17:58:23.197   Parallel retrieval complete
             LangGraph
17:58:23.212   supervisor_sales_agent
INFO:AgentChatApi:AGENT CALLED: supervisor_sales_agent
17:58:23.217     ChatOpenAI
INFO:SemanticCacheService:[Semantic Cache STORED from RAG Vector] User=7Zd9xcNhWt5ADAIWHzC6SNC5S1wdDixi, Hash=7e96099c, ItemId=32c80d2feb0d

=================================================================
 REAL EXECUTION METRICS [Query: 'what is the exact nutrients in your all products ,...']
   • Total E2E Latency:          34.05 s
   • TTFT (Time to First Token): 18102.6 ms
   • Sub-Agents Executed (3):   ['supervisor_router', 'rag_agent', 'supervisor_sales_agent']
   • Verified Facts Synthesized: 1
=================================================================

INFO:DeepEvalServerEvaluator:Running background DeepEval evaluation for query: 'what is the exact nutrients in your all ...'
INFO:     127.0.0.1:61883 - "GET /api/v1/agent/threads?user_id=7Zd9xcNhWt5ADAIWHzC6SNC5S1wdDixi HTTP/1.1" 200 OK
INFO:     127.0.0.1:57460 - "GET /api/v1/agent/memory?user_id=7Zd9xcNhWt5ADAIWHzC6SNC5S1wdDixi HTTP/1.1" 200 OK
INFO:     127.0.0.1:61883 - "GET /api/v1/agent/memory?user_id=7Zd9xcNhWt5ADAIWHzC6SNC5S1wdDixi HTTP/1.1" 200 OK
INFO:     127.0.0.1:57460 - "GET /api/v1/agent/memory?user_id=7Zd9xcNhWt5ADAIWHzC6SNC5S1wdDixi HTTP/1.1" 200 OK
INFO:     127.0.0.1:61883 - "GET /api/v1/agent/memory?user_id=7Zd9xcNhWt5ADAIWHzC6SNC5S1wdDixi HTTP/1.1" 200 OK
INFO:     127.0.0.1:57460 - "GET /api/v1/agent/memory?user_id=7Zd9xcNhWt5ADAIWHzC6SNC5S1wdDixi HTTP/1.1" 200 OK
INFO:     127.0.0.1:61883 - "GET /api/v1/agent/memory?user_id=7Zd9xcNhWt5ADAIWHzC6SNC5S1wdDixi HTTP/1.1" 200 OK

======================================================================
 LIVE CHAT DEEPEVAL RESULTS [Query: 'what is the exact nutrients in your all products , i want see facts . and why to book your products ?
what extra benefits i have']
   [PASSED] FaithfulnessMetric: Score = 0.9
        Reason: The score is 0.90 because the actual output makes unsupported claims about TrioSan Gold containing calcium salts of bypass fats, being a triple-action fat and SNF booster, and improving energy density without compromising rumen function, which are not backed by the retrieval context.
   [PASSED] AnswerRelevancyMetric: Score = 1.0
        Reason: The score is 1.00 because the response directly addresses the inquiry about the nutrients in the products and the benefits of booking them, with no irrelevant statements present.
   [FAILED] ContextualPrecisionMetric: Score = 0.5889
        Reason: The score is 0.59 because while there are relevant nodes that provide insights into the nutrients and benefits of the products, such as the second node discussing fermentation metabolites and the fifth node outlining the company's specialized approach, there are also irrelevant nodes ranked higher, like the first node which states that it does not provide relevant information about nutrients. This affects the overall ranking and contextual precision.
   [PASSED] ContextualRecallMetric: Score = 0.8889
        Reason: The score is 0.89 because the detailed breakdown of nutrients and benefits in the expected output closely aligns with the company's focus on specialized products and tailored nutrition as outlined in node 1 and node 4 of the retrieval context, while the inquiry about dosage and orders does not directly connect to the core product information.
   [PASSED] ToolCorrectnessMetric: Score = 1.0
        Reason: [
         Tool Calling Reason: All expected tools ['rag_agent'] were called (order not considered).
         Tool Selection Reason: No available tools were provided to assess tool selection criteria
]

======================================================================
