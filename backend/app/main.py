from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, brain, chat, profile, payment, memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


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
    from app.services.brain import knowledge_brain

    return {
        "status": "ok",
        "version": "2.0.0",
        "ai_provider": settings.AI_PROVIDER,
        # Surfaced so an empty knowledge brain is visible from outside instead
        # of failing silently (the corpus used to live outside the Docker image).
        "knowledge_chunks": len(knowledge_brain.list_knowledge_chunks()),
        "knowledge_source": str(knowledge_brain.canonical_chunks_path()),
    }
