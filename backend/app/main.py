"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.chat import router as chat_router
from .api.knowledge import router as knowledge_router
from .api.history import router as history_router
from .core.config import CORS_ORIGINS, HOST, PORT

app = FastAPI(
    title="执行辅助Agent API",
    description="电商活动规则解析与执行辅助Agent后端服务",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(history_router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
