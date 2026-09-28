import logging
import time
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from collections import defaultdict, deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from app.api.v1.router import router
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import BackgroundJobRecord
from app.workers.tasks import run_job

logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}')
requests: dict[str, deque] = defaultdict(deque)

async def job_loop():
    while True:
        try:
            with SessionLocal() as db:
                ids=list(db.scalars(select(BackgroundJobRecord.id).where(BackgroundJobRecord.status.in_(["PENDING","RETRY"]),BackgroundJobRecord.run_after<=datetime.now(timezone.utc)).limit(10)).all())
            for job_id in ids:await asyncio.to_thread(run_job,job_id)
        except Exception:logging.exception("background_job_loop_error")
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app:FastAPI):
    task=asyncio.create_task(job_loop()) if settings.environment!="test" else None
    yield
    if task:
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass

app = FastAPI(title="Findora API", version="2.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json",lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def request_controls(request: Request, call_next):
    started = time.perf_counter(); path = request.url.path
    if path.endswith(("/auth/login", "/auth/register")):
        key = f"{request.client.host if request.client else 'unknown'}:{path}"; now = time.time(); bucket = requests[key]
        while bucket and bucket[0] < now - 60: bucket.popleft()
        if len(bucket) >= 10: return JSONResponse({"detail": "Too many attempts. Try again shortly."}, 429)
        bucket.append(now)
    try: response = await call_next(request)
    except Exception:
        logging.exception("unhandled_request_error path=%s", path)
        return JSONResponse({"detail": "An unexpected error occurred"}, 500)
    response.headers["X-Content-Type-Options"] = "nosniff"; response.headers["X-Frame-Options"] = "DENY"
    logging.info("request method=%s path=%s status=%s duration_ms=%.1f", request.method, path, response.status_code, (time.perf_counter()-started)*1000)
    return response


@app.get("/api/v1/health")
def health(): return {"status": "healthy", "service": "findora-api"}
@app.get("/api/v1/ready")
def ready():
    try:
        with SessionLocal() as db: db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception: return JSONResponse({"status": "not_ready"}, 503)


app.include_router(router, prefix="/api/v1")
