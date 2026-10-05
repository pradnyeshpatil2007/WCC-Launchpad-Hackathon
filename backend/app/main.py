"""FastAPI application for AutoShorts: startup preflight, CORS, jobs router, and media router."""

import sys
if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.jobs import router as jobs_router
from app.api.media import router as media_router
from app.config import get_settings
from app.jobs.repo import JobRepo
from app.preflight import run_preflight


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: database initialization and live external service preflight."""
    settings = get_settings()
    # 1. Initialize SQLite schema
    repo = JobRepo()
    await repo.init_db()

    # 2. Run live preflight probes
    try:
        report = await run_preflight()
        if not report.is_healthy:
            print(f"[-] Preflight warning: System degraded or unhealthy: {report.errors}")
        else:
            print("[+] Preflight check: All external services verified healthy.")
    except Exception as exc:
        print(f"[-] Preflight probe error: {exc}")

    yield
    await repo.close()


app = FastAPI(
    title="AutoShorts API",
    description="Multi-agent educational vertical video generation pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

# CORS configuration
origins = [
    settings.FRONTEND_ORIGIN,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

# Mount API Routers
app.include_router(jobs_router)
app.include_router(media_router)


@app.get("/health")
async def health_check():
    """System health probe endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler guaranteeing no internal secrets or traces leak."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred.",
                "retryable": False,
            }
        },
    )
