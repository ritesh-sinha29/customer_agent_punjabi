from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.api.endpoints.ingest import router as ingest_router
from src.app.api.endpoints.agent_chat import router as agent_chat_router
from src.app.api.endpoints.threads import router as threads_router
from src.app.api.endpoints.memory import router as memory_router
from src.app.services.llama_service import llama_service
from src.app.services.pinecone_service import pinecone_service

app = FastAPI(
    title="Customer Ingestion Agent API",
    description="Asynchronous ingestion pipeline & Vrsa Agrotech Supervisor Agent API.",
    version="1.0.0",
)

@app.on_event("startup")
def startup_event():
    try:
        from src.app.services.db_service import db_service
        db_service.ensure_chat_tables()
    except Exception as e:
        print(f"[Startup Warning] Could not initialize database tables: {e}")
    print("server started ready to receive query !")

# Configure CORS for Next.js client interaction across localhost and 127.0.0.1
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
async def health_check():
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

# Include routing under /api prefix
app.include_router(ingest_router, prefix="/api")
app.include_router(agent_chat_router, prefix="/api")
app.include_router(threads_router, prefix="/api")
app.include_router(memory_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
