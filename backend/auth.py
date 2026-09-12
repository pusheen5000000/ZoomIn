"""Demo-account login for our app. Session cookie; not a real identity provider."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import DEMO_PASSWORD, DEMO_USER

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


def current_username(request: Request) -> str | None:
    return request.session.get("username")


def require_login(request: Request) -> str:
    user = current_username(request)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in")
    return user


@router.post("/login")
def login(body: LoginBody, request: Request) -> dict[str, str]:
    user_ok = body.username.strip().lower() == DEMO_USER.strip().lower()
    pass_ok = body.password == DEMO_PASSWORD
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="That email or password is wrong.")
    request.session["username"] = DEMO_USER
    return {"username": DEMO_USER, "status": "signed_in"}


@router.post("/logout")
def logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"status": "signed_out"}


@router.get("/me")
def me(request: Request) -> dict[str, str | bool]:
    user = current_username(request)
    return {"authenticated": bool(user), "username": user or ""}
