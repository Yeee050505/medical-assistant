import logging
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import auth, chat, file, monitor, rag
from app.core.config import settings
from app.core.database import check_mysql
from app.core.gateway import install_gateway_middlewares
from app.core.response import http_exception_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for path in (settings.upload_dir, settings.rag_doc_dir):
        __import__("pathlib").Path(path).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="多模态医疗辅助问诊系统",
    description="RAG + 国内大模型 API 企业版，仅供药品科普参考",
    version="1.0.0",
    lifespan=lifespan,
)
install_gateway_middlewares(app)


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=http_exception_handler(request, exc),
    )


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(file.router, prefix="/api/v1/file", tags=["file"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["rag"])
app.include_router(monitor.router, prefix="/api/v1/monitor", tags=["monitor"])


@app.get("/api/v1/health")
async def health():
    components: dict[str, dict] = {}

    components["mysql"] = {"status": "up" if check_mysql() else "down"}

    try:
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        components["redis"] = {"status": "up"}
    except Exception:
        components["redis"] = {"status": "down"}

    try:
        async with httpx.AsyncClient(timeout=2) as cli:
            resp = await cli.get(f"{settings.qdrant_url}/readyz")
            components["qdrant"] = {"status": "up" if resp.status_code == 200 else "down"}
    except Exception:
        components["qdrant"] = {"status": "down"}

    components["llm"] = {
        "status": "mock" if settings.llm_provider == "mock" else "configured",
        "provider": settings.llm_provider,
    }

    degraded = [name for name, item in components.items() if item["status"] == "down"]
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "status": "degraded" if degraded else "up",
            "components": components,
        },
    }
