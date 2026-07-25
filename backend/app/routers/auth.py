"""Auth router — simple login for dashboard supervision access."""

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Hardcoded credentials for the prototype
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
ADMIN_TOKEN = "admin-token"
ADMIN_NAME = "Administrador"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    name: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """Simple login: accept admin/admin and return a static token."""
    if body.username != ADMIN_USERNAME or body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return LoginResponse(token=ADMIN_TOKEN, name=ADMIN_NAME)


def require_admin(authorization: str | None = Header(None)) -> None:
    """Dependency that checks the Authorization header for the admin token."""
    if authorization is None:
        raise HTTPException(status_code=401, detail="Se requiere autenticación")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token inválido")
