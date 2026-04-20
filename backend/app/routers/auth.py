from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.auth import get_current_user, issue_jwt, verify_password
from app.config import COOKIE_NAME, COOKIE_SECURE, JWT_EXP_HOURS
from app.db import get_session
from app.models import User
from app.schemas import LoginIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == body.username.strip())).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = issue_jwt(user)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=JWT_EXP_HOURS * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return {
        "ok": True,
        "token": token,
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS)
        ).isoformat(),
        "user": UserOut.model_validate(user),
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
