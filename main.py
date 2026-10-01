"""PocketSmart AI - FastAPI application entry point.

Run with:   python main.py      (or)      uvicorn main:app --reload
"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import database
from app.config import BASE_DIR, settings
from app.routes import auth, pages, planners
from app.security import RedirectToLogin
from app.templating import templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pocketsmart")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables, folders and report configuration."""
    database.init_db()
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if settings.GEMINI_API_KEY:
        logger.info("Gemini enabled (model: %s)", settings.GEMINI_MODEL)
    else:
        logger.warning("GEMINI_API_KEY missing - app will serve sample (fallback) recommendations.")
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(planners.router)


@app.exception_handler(RedirectToLogin)
async def redirect_to_login(request: Request, exc: RedirectToLogin):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """Friendly HTML error page for browsers, JSON for API clients."""
    wants_html = "text/html" in request.headers.get("accept", "") and request.method == "GET"
    if wants_html and exc.status_code in (404, 403):
        from app.security import get_user_from_request
        return templates.TemplateResponse(
            request, "error.html",
            {"user": get_user_from_request(request), "code": exc.status_code, "message": exc.detail},
            status_code=exc.status_code,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.get("/health")
async def health():
    return {"status": "ok", "gemini_configured": bool(settings.GEMINI_API_KEY)}


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
