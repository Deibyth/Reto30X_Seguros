import time

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text

from app.database import get_db
from app.security import Login, authenticate, operator, require_csrf, require_permission

router = APIRouter(prefix="/api/auth", tags=["operator-auth"])
boundary_router = APIRouter(prefix="/api/multichannel", tags=["multichannel-security"])


@router.post("/login")
async def login(payload: Login, request: Request, response: Response, db=Depends(get_db)):
    actor, (session, csrf) = await authenticate(payload, response, db)
    secure = request.app.state.settings.environment != "testing"
    response.set_cookie("operator_session", session, httponly=True, secure=secure, samesite="strict", max_age=24 * 3600)
    return {"operator": actor, "csrf_token": csrf}


@router.get("/me")
async def me(actor=Depends(operator)):
    return {"id": actor["operator_id"], "username": actor["username"], "permissions": actor["permissions"].split(",")}


@router.post("/logout", status_code=204)
async def logout(response: Response, actor=Depends(require_csrf), db=Depends(get_db)):
    from app.security import record_audit
    try:
        await record_audit(db, actor["operator_id"], "logout", actor["username"], "success")
        await db.execute(text("UPDATE operator_sessions SET revoked_at=:now WHERE id=:id"), {"now": int(time.time()), "id": actor["id"]})
        await db.commit()
    except Exception as error:
        await db.rollback()
        from fastapi import HTTPException
        raise HTTPException(503, "Security audit unavailable") from error
    response.delete_cookie("operator_session")


@router.get("/access")
async def access(actor=Depends(require_permission("multichannel:read"))):
    return {"access": True, "company": "single-company"}


boundary_router.add_api_route("/access", access, methods=["GET"])
