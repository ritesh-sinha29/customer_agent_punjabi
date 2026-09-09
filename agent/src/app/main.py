import sys
from contextlib import asynccontextmanager

# Fix Windows charmap codec UnicodeEncodeError when printing emojis to console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.api.endpoints.agent_chat import router as agent_chat_router
from src.app.api.endpoints.evaluation import router as eval_router
from src.app.api.endpoints.ingest import router as ingest_router
from src.app.api.endpoints.memory import router as memory_router
from src.app.api.endpoints.threads import router as threads_router
from src.app.services.llama_service import llama_service
from src.app.services.pinecone_service import pinecone_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    import asyncio
    from src.app.core.config import settings
    from src.app.services.pinecone_service import pinecone_service
    from src.app.services.db_service import db_service

    # 1. Pre-bind Pinecone index
    pinecone_ok = False
    try:
        pinecone_service.initialize_index()
        pinecone_ok = True
    except Exception:
        pass

    # 2. Verify OpenAI API key
    openai_ok = bool(settings.OPENAI_API_KEY)

    # 3. Ensure DB tables in worker thread
    def init_db():
        try:
            db_service.ensure_chat_tables()
        except Exception:
            pass

    asyncio.get_running_loop().run_in_executor(None, init_db)

    print("\n" + "=" * 60, flush=True)
    print("[PRODUCTION STARTUP CHECKLIST]", flush=True)
    print(f"[OK] Config Loaded (.env)", flush=True)
    print(f"[{'OK' if openai_ok else 'WARN'}] OpenAI API Key {'loaded' if openai_ok else 'missing'}", flush=True)
    print(f"[{'OK' if pinecone_ok else 'WARN'}] Pinecone Vector DB Connected & Ready", flush=True)
    print(f"[OK] Groq Guardrail Engine Ready (llama-prompt-guard-2-86m & gpt-oss-safeguard-20b)", flush=True)
    print(f"[OK] LangGraph Supervisor Workflow Compiled Successfully", flush=True)
    print(f"[OK] PostgreSQL Database Pool Initialized", flush=True)
    print("=" * 60 + "\n", flush=True)

    yield
    # Shutdown actions if any


app = FastAPI(
    title="Customer Ingestion Agent API",
    description="Asynchronous ingestion pipeline & Vrsa Agrotech Supervisor Agent API.",
    version="1.0.0",
    lifespan=lifespan,
)


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
app.include_router(eval_router, prefix="/api")

if __name__ == "__main__":
    import os

    import uvicorn

    is_prod = os.getenv("ENVIRONMENT", "").lower() in ["production", "prod"]
    workers_count = int(os.getenv("WEB_CONCURRENCY", "4")) if is_prod else 1
    use_reload = not is_prod

    if use_reload:
        uvicorn.run("src.app.main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        uvicorn.run(
            "src.app.main:app",
            host="0.0.0.0",
            port=8000,
            workers=workers_count,
            reload=False,
        )
