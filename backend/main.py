import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path

from routers import accounts, browser, comments, groups, posts, scheduler as scheduler_router, posts_manager, templates
from services.storage import _ensure_files

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("services.fb_poster").setLevel(logging.DEBUG)

# Global APScheduler instance (imported by scheduler router)
scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")


def _reload_active_schedules():
    from datetime import datetime

    from routers.scheduler import VN_TZ, _register_schedule_job
    from services.storage import read_json

    for sc in read_json("schedules"):
        if sc.get("status") not in ("pending", "active"):
            continue
        try:
            raw = sc["scheduled_at"].replace("Z", "+00:00")
            scheduled_dt = datetime.fromisoformat(raw)
            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=VN_TZ)
            else:
                scheduled_dt = scheduled_dt.astimezone(VN_TZ)
            if sc.get("recurrence", "once") == "once" and scheduled_dt <= datetime.now(VN_TZ):
                continue
            _register_schedule_job(scheduler, sc, scheduled_dt)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_files()
    scheduler.start()
    _reload_active_schedules()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="FB Group Auto-Poster",
    description="Tự động đăng bài lên Facebook Groups",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def spa_route_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        # Check if the request is not for API/uploads and is a GET request
        if not request.url.path.startswith("/api") and not request.url.path.startswith("/uploads") and request.method == "GET":
            index_path = Path(__file__).parent.parent / "frontend" / "dist" / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
    return await http_exception_handler(request, exc)


# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded images
uploads_dir = Path(__file__).parent / "data" / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Routers
app.include_router(accounts.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(posts.router, prefix="/api")
app.include_router(scheduler_router.router, prefix="/api")
app.include_router(comments.router, prefix="/api")
app.include_router(posts_manager.router, prefix="/api")
app.include_router(browser.router, prefix="/api")
app.include_router(templates.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve Frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend" / "dist"
frontend_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

