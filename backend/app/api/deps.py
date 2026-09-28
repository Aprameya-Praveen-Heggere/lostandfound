from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_token
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try: user_id = decode_token(credentials.credentials)
    except Exception: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account unavailable")
    from app.models import Institution
    institution = db.get(Institution, user.institution_id)
    if not institution or not institution.is_active: raise HTTPException(status.HTTP_403_FORBIDDEN, "Institution is inactive")
    return user


def officer(user: User = Depends(current_user)) -> User:
    if user.role not in (Role.OFFICER, Role.ADMIN): raise HTTPException(status.HTTP_403_FORBIDDEN, "Officer access required")
    return user


def admin(user: User = Depends(current_user)) -> User:
    if user.role != Role.ADMIN: raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user

def platform_admin(user: User = Depends(current_user)) -> User:
    if not user.is_platform_admin: raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator access required")
    return user
