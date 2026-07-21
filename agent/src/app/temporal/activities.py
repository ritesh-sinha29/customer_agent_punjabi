from temporalio import activity

from src.app.pipelines.ingest_pipeline import ingest_pipeline


@activity.defn
async def ingest_document_activity(
    file_url: str,
    file_key: str,
    user_id: str,
    tenant: str = "default",
    permissions: list[str] = None,
    version: str = "1.0.0",
    job_id: str = None,
) -> dict:
    """
    Temporal Activity that executes the document ingestion pipeline.
    """
    activity.logger.info(
        f"Running Ingestion pipeline for user {user_id}, file: {file_key}, tenant: {tenant}"
    )
    result = await ingest_pipeline.run(
        file_url=file_url,
        file_key=file_key,
        user_id=user_id,
        tenant=tenant,
        permissions=permissions or ["read:all"],
        version=version,
        job_id=job_id,
    )
    return result


@activity.defn
async def update_failure_status_activity(job_id: str, error_message: str) -> None:
    """
    Temporal Activity that marks the job status as failed in Redis.
    """
    from src.app.core.status_manager import status_manager

    activity.logger.info(f"Marking job {job_id} as failed in Redis: {error_message}")
    status_manager.update_status(job_id, 0, error_message, status="failed")


@activity.defn
async def fetch_user_conversation_activity(user_id: str, thread_id: str) -> dict:
    """
    Fetches the recent conversation messages in a thread and the existing user memory profile.
    """
    from src.app.services.db_service import db_service
    import json

    activity.logger.info(f"Fetching conversation history for user {user_id}, thread {thread_id}")
    
    # 1. Fetch latest messages (up to 15)
    messages_query = (
        "SELECT role, content FROM chat_message WHERE thread_id = %s ORDER BY created_at ASC LIMIT 15"
    )
    messages_rows = db_service.execute_query(messages_query, (thread_id,))
    messages = [{"role": row["role"], "content": row["content"]} for row in messages_rows]

    # 2. Fetch existing memory facts
    memory_query = "SELECT semantic_facts FROM user_memory WHERE user_id = %s"
    memory_row = db_service.execute_query(memory_query, (user_id,))
    
    current_facts = []
    if memory_row:
        current_facts = memory_row[0].get("semantic_facts") or []

    return {
        "messages": messages,
        "current_facts": current_facts
    }


@activity.defn
async def check_message_usefulness_groq_activity(messages: list) -> bool:
    """
    Calls Groq to classify if conversation messages contain useful user facts.
    """
    from src.app.services.groq_service import groq_service
    return await groq_service.check_usefulness(messages)


@activity.defn
async def consolidate_user_memory_activity(messages: list, current_facts: list) -> dict:
    """
    Calls Groq to consolidate semantic facts and generate an episodic summary.
    """
    from src.app.services.groq_service import groq_service
    return await groq_service.consolidate_memory(messages, current_facts)


@activity.defn
async def embed_and_save_user_memory_activity(user_id: str, semantic_facts: list, episodic_summary: str) -> None:
    """
    Generates Jina embeddings for facts, updates Pinecone (user_memory namespace),
    and updates the database user_memory record.
    """
    from src.app.services.db_service import db_service
    from src.app.services.embedding_service import embedding_service
    from src.app.services.pinecone_service import pinecone_service
    import json

    activity.logger.info(f"Embedding and saving memory for user {user_id}")

    # 1. Embed semantic facts and upsert to Pinecone
    if semantic_facts:
        try:
            embeddings = await embedding_service.get_dense_embeddings(semantic_facts)
            
            # Clean old user vectors
            pinecone_service.delete_by_user_id(user_id=user_id, namespace="user_memory")
            
            # Prepare vectors
            pinecone_vectors = []
            for idx, fact in enumerate(semantic_facts):
                vector_id = f"fact-{user_id}-{idx}"
                metadata = {
                    "user_id": user_id,
                    "text": fact,
                    "type": "semantic_memory"
                }
                pinecone_vectors.append({
                    "id": vector_id,
                    "values": embeddings[idx],
                    "metadata": metadata
                })
            
            if pinecone_vectors:
                # Ensure the index is ready and upsert
                pinecone_service.upsert_vectors(pinecone_vectors, namespace="user_memory")
                activity.logger.info(f"Upserted {len(pinecone_vectors)} semantic memory vectors to Pinecone.")
        except Exception as pe:
            activity.logger.error(f"Failed to upsert memory vectors to Pinecone: {pe}")

    # 2. Save facts and append summary to PostgreSQL
    try:
        # Fetch current episodic summaries to append
        current_summaries = []
        memory_row = db_service.execute_query("SELECT episodic_summaries FROM user_memory WHERE user_id = %s", (user_id,))
        if memory_row:
            current_summaries = memory_row[0].get("episodic_summaries") or []
        
        if episodic_summary:
            current_summaries.append(episodic_summary)

        # Upsert user_memory
        upsert_query = """
        INSERT INTO user_memory (user_id, semantic_facts, episodic_summaries, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            semantic_facts = EXCLUDED.semantic_facts,
            episodic_summaries = EXCLUDED.episodic_summaries,
            updated_at = NOW();
        """
        db_service.execute_insert(
            upsert_query,
            (user_id, json.dumps(semantic_facts), json.dumps(current_summaries))
        )
        activity.logger.info("Saved user memory facts and episodic summaries to PostgreSQL successfully.")
    except Exception as dbe:
        activity.logger.error(f"Failed to save user memory to Postgres: {dbe}")
        raise dbe

