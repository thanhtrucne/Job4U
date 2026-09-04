"""FastAPI application entry point."""
import logging
import logging.config
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

from backend.config import settings
from backend.database import create_tables
from backend.websocket.ws_manager import manager
from backend.api import jobs, companies, categories, search, auth, profiles, matching, documents, applications, dashboard, admin, partner, career_guides


# ── System Encoding & Logging ──────────────────────────────────────────────────
import sys

# Fix UnicodeEncodeError for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

os.makedirs("logs", exist_ok=True)

# Using standard basicConfig for simpler global override as requested
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/api.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# ── Scheduler ─────────────────────────────────────────────────────────────────

scheduler = AsyncIOScheduler()


async def scheduled_crawl():
    from backend.services.crawler_service import run_crawler_task
    logger.info("Scheduled crawler started")
    await run_crawler_task()


async def scheduled_document_expiry():
    from backend.api.documents import expire_documents
    from backend.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        count = await expire_documents(db)
        await db.commit()
    if count:
        logger.info("Marked %s document(s) as expired.", count)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    logger.info("Starting up...")
    
    if settings.AUTO_CREATE_TABLES:
        logger.warning("AUTO_CREATE_TABLES=true: use only for disposable local development databases.")
        await create_tables()
    else:
        logger.info("Schema auto-create disabled; apply migrations/001_portal_privacy.sql before startup.")
    scheduler.add_job(
        scheduled_crawl,
        "interval",
        minutes=settings.CRAWL_INTERVAL_MINUTES,
        id="auto_crawl",
    )
    scheduler.add_job(scheduled_document_expiry, "interval", hours=24, id="document_expiry")
    scheduler.start()
    logger.info(f"Scheduler started. Crawl every {settings.CRAWL_INTERVAL_MINUTES} min.")
    yield
    scheduler.shutdown()
    logger.info("Shutting down...")



# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Credentials must never be combined with a wildcard origin.
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(jobs.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(matching.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(partner.router, prefix="/api")
app.include_router(career_guides.router, prefix="/api")
app.include_router(career_guides.admin_router, prefix="/api")


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── Stats public shortcut ──────────────────────────────────────────────────────

@app.get("/api/stats")
async def public_stats_shortcut():
    from backend.database import AsyncSessionLocal
    from sqlalchemy import select, func
    from backend.models import Job, Company, Category
    async with AsyncSessionLocal() as db:
        total_jobs = (await db.execute(select(func.count()).select_from(Job).where(Job.is_active == True))).scalar() or 0
        total_companies = (await db.execute(select(func.count()).select_from(Company))).scalar() or 0
        total_categories = (await db.execute(select(func.count()).select_from(Category))).scalar() or 0
    return {
        "total_jobs": total_jobs,
        "total_companies": total_companies,
        "total_categories": total_categories,
    }


# ── Templates (admin dashboard) ───────────────────────────────────────────────

_templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
os.makedirs(_templates_path, exist_ok=True)
templates = Jinja2Templates(directory=_templates_path)


# Admin routes removed as per user request


# ── Static frontend ────────────────────────────────────────────────────────────

frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
