"""Login/logout/session-check for the LearningEngine UI.

The browser never holds internal_api_token directly anymore: it POSTs the UI
login password here and gets back a short-lived signed session cookie instead
(see dependencies.SESSION_COOKIE_NAME / session_tokens.py). This replaces
baking VITE_INTERNAL_TOKEN into the frontend's JS bundle — a secret shipped to
every visitor's browser isn't a secret. The cookie is httpOnly (unreadable by
JS, so an XSS can't exfiltrate it) and SameSite=strict (the frontend and API
are same-origin in every deployment — nginx proxies /api — so this costs
nothing and blocks cross-site submission of /auth/login or /auth/logout).
"""

import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from learning_engine.api.v1.dependencies import SESSION_COOKIE_NAME, verify_internal_token
from learning_engine.config import settings
from learning_engine.infrastructure.security.session_tokens import create_session_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class AuthResult(BaseModel):
    ok: bool = True


def _password_ok(password: str) -> bool:
    """Same fail-closed-outside-development shape as dependencies._internal_token_ok."""
    if not settings.ui_login_password:
        if settings.app_env == "development":
            return True
        logger.error(
            "UI_LOGIN_PASSWORD is not set and APP_ENV=%s — rejecting all UI logins",
            settings.app_env,
        )
        return False
    return hmac.compare_digest(password, settings.ui_login_password)


@router.post("/login", response_model=AuthResult)
async def login(body: LoginRequest, response: Response) -> AuthResult:
    if not _password_ok(body.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_session_token(settings.internal_api_token)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="strict",
        max_age=12 * 3600,
        path="/",
    )
    return AuthResult()


@router.post("/logout", response_model=AuthResult)
async def logout(response: Response) -> AuthResult:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return AuthResult()


@router.get(
    "/session", response_model=AuthResult, dependencies=[Depends(verify_internal_token)]
)
async def session_check() -> AuthResult:
    """200 iff the caller already has a valid session (cookie or raw internal
    token). The frontend calls this on load to decide login screen vs. app."""
    return AuthResult()
