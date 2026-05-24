import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from routers import accounts, groups, posts, scheduler as scheduler_router
from services.storage import _ensure_files

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("services.fb_poster").setLevel(logging.DEBUG)

# Global APScheduler instance (imported by scheduler router)
scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_files()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="FB Group Auto-Poster",
    description="Tự động đăng bài lên Facebook Groups",
    version="1.0.0",
    lifespan=lifespan,
)

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


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve Frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend" / "dist"
frontend_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

