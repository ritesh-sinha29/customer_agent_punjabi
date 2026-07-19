

INFO:     127.0.0.1:53093 - "POST /api/v1/agent/chat/stream HTTP/1.1" 200 OK
ERROR:AgentChatApi:Failed to initialize Langfuse callback handler: LangchainCallbackHandler.__init__() got an unexpected keyword argument 'secret_key'
R:\python\customer_agent\agent\.venv\Lib\site-packages\pydantic\main.py:475: UserWarning: Pydantic serializer warnings:
  PydanticSerializationUnexpectedValue(Expected `none` - serialized value may not be as expected [field_name='parsed', input_value=RouterOutput(next_node='r...tise of the rag_agent.'), input_type=RouterOutput])
  return self.__pydantic_serializer__.to_python(
23:42:34.762 optimize_query_hf
23:42:34.764   query-optimization
23:42:34.765     qwen-query-rewrite
INFO:QueryOptimizer:Optimizing query: 'How can I increase the milk quality and fat content?' via Qwen...
23:42:34.785   Sending prompt to Hugging Face Qwen
ERROR:QueryOptimizer:Hugging Face API call failed: [Errno 11001] getaddrinfo failed. Trying fallback to OpenAI...
23:42:34.861   Hugging Face API error, attempting OpenAI fallback
INFO:QueryOptimizer:OpenAI gpt-4o-mini generated response: ["increase milk quality fat content dairy cows", "enhance fat content milk production cattle", "improve milk quality supplements for dairy cows"]
23:42:36.061 hybrid_retrieval_parallel
INFO:RetrievalService:Initiating parallel hybrid search for 3 queries...
23:42:36.066   Parallel hybrid search starting
INFO:EmbeddingService:[Step 4 - Embedding] Generating dense embeddings using Jina (1024d)...
INFO:EmbeddingService:[Step 4 - Embedding] Generating sparse TF vectors locally for 3 chunks...
23:42:36.723   hybrid-search-parallel
INFO:pinecone.index:Querying index with top_k=15
INFO:pinecone.index:Querying index with top_k=15
INFO:pinecone.index:Querying index with top_k=15
INFO:RerankingService:Sending 19 candidates to Jina Reranker...
INFO:RerankingService:Jina Reranking succeeded.
INFO:RetrievalService:Retrieved and reranked 4 chunks from Pinecone.
23:42:38.792   Parallel retrieval complete