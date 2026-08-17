from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, brain, chat, profile, payment, memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: index the book for meaning-based search. Fired as a background
    # task on purpose — it makes ~7 embedding calls, and the app has to answer
    # health checks immediately. Until it finishes, retrieval falls back to the
    # old keyword search, so the first messages after a deploy still work.
    import asyncio

    from app.services.brain import semantic_index

    index_task = asyncio.create_task(semantic_index.ensure_index())
    yield
    # Shutdown
    index_task.cancel()


app = FastAPI(
    title="Aprende a Querer API",
    description="AI-powered emotional coaching and relationship assessment",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "https://aprendeaquerer.com",
        "https://www.aprendeaquerer.com",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(brain.router)
app.include_router(chat.router)
app.include_router(profile.router)
app.include_router(payment.router)
app.include_router(memory.router)


@app.get("/")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/status")
async def status():
    from app.services.brain import knowledge_brain, semantic_index

    return {
        "status": "ok",
        "version": "2.0.0",
        "ai_provider": settings.AI_PROVIDER,
        # Surfaced so an empty knowledge brain is visible from outside instead
        # of failing silently (the corpus used to live outside the Docker image).
        "knowledge_chunks": len(knowledge_brain.list_knowledge_chunks()),
        "knowledge_source": str(knowledge_brain.canonical_chunks_path()),
        # Same reason: if the meaning-based index never built, the bot silently
        # degrades to the old word search. That has to be visible from outside.
        "semantic_search": semantic_index.index_status(),
    }
