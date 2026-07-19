from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.api.endpoints.ingest import router as ingest_router
from src.app.api.endpoints.agent_chat import router as agent_chat_router
from src.app.services.llama_service import llama_service
from src.app.services.pinecone_service import pinecone_service

app = FastAPI(
    title="Customer Ingestion Agent API",
    description="Asynchronous ingestion pipeline: LlamaParse layout extraction, semantic chunking, and Pinecone vector store loading.",
    version="1.0.0",
)

# Configure CORS for Next.js client interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to client domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    # Verify connections
    pinecone_ok = pinecone_service.check_connection()
    llama_ok = llama_service.check_connection()

    is_healthy = pinecone_ok and llama_ok

    return {
        "status": "healthy" if is_healthy else "degraded",
        "details": {
            "pinecone": "connected" if pinecone_ok else "disconnected",
            "llama_cloud": "connected" if llama_ok else "disconnected",
        },
    }


# Include routing
app.include_router(ingest_router, prefix="/api")
app.include_router(agent_chat_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
