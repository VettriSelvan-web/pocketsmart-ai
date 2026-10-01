"""Register / login / logout / token / session endpoints."""
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm

from .. import database, security
from ..config import settings
from ..schemas import validate_registration
from ..templating import templates

router = APIRouter()


def _set_cookie(response, token: str) -> None:
    response.set_cookie(
        settings.COOKIE_NAME, token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True, samesite="lax", path="/",
    )


@router.get("/register")
async def register_page(request: Request, user=Depends(security.get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "register.html", {"user": None, "error": None, "form": {}})


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    username, email = username.strip(), email.strip().lower()
    form = {"username": username, "email": email}
    error = validate_registration(username, email, password, confirm_password)
    if not error:
        if database.get_user_by_username(username):
            error = "That username is already taken."
        elif database.get_user_by_email(email):
            error = "An account with that email already exists."
    if not error:
        try:
            database.create_user(username, email, security.hash_password(password))
        except sqlite3.IntegrityError:
            error = "Username or email already registered."
    if error:
        return templates.TemplateResponse(
            request, "register.html", {"user": None, "error": error, "form": form}, status_code=400
        )
    return RedirectResponse("/login?registered=1", status_code=303)


@router.get("/login")
async def login_page(request: Request, registered: int = 0, user=Depends(security.get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    msg = "Account created! Please sign in." if registered else None
    return templates.TemplateResponse(request, "login.html", {"user": None, "error": None, "message": msg})


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = database.get_user_by_username(username.strip())
    if not user or not security.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request, "login.html",
            {"user": None, "error": "Incorrect username or password.", "message": None},
            status_code=401,
        )
    response = RedirectResponse("/dashboard", status_code=303)
    _set_cookie(response, security.create_access_token(user))
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(settings.COOKIE_NAME, path="/")
    return response


@router.post("/token")
async def token(form: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 password flow -> returns a JWT for API clients (Swagger 'Authorize' etc.)."""
    user = database.get_user_by_username(form.username.strip())
    if not user or not security.verify_password(form.password, user["password_hash"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": security.create_access_token(user), "token_type": "bearer"}


@router.get("/session-info")
async def session_info(user=Depends(security.get_optional_user)):
    if not user:
        return {"logged_in": False}
    return {
        "logged_in": True,
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "token_expires_at": user.get("token_exp"),
    }


@router.get("/session-data")
async def session_data(user=Depends(security.require_user)):
    recent = database.list_recommendations(user["id"], limit=5)
    return {
        "user_id": user["id"],
        "username": user["username"],
        "counts_by_category": database.count_by_category(user["id"]),
        "recent": [
            {"id": r["id"], "category": r["category"], "title": r["title"],
             "budget": r["budget"], "created_at": r["created_at"]}
            for r in recent
        ],
    }
