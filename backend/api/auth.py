"""Authentication dependencies shared by privacy-sensitive API routes."""
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from backend.config import settings
from backend.database import get_db
from backend.models import Company, User
from backend.schemas import CompanyRegister, TokenOut, UserLogin, UserOut, UserRegister
from backend.services.security import create_access_token, hash_password, verify_password
from backend.services.email_service import send_registration_email

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), db: AsyncSession = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Cần đăng nhập.")
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ hoặc đã hết hạn.")
    user = (await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tài khoản không còn hoạt động.")
    return user


def require_roles(*roles: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền thực hiện thao tác này.")
        return user
    return dependency


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được đăng ký.")
    normalized_phone = func.regexp_replace(User.phone_number, "[^0-9]", "", "g")
    phone_in_use = (await db.execute(
        select(User.id).where(normalized_phone == payload.phone_number)
    )).scalar_one_or_none()
    if phone_in_use is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Số điện thoại đã được đăng ký.")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        password_hash=hash_password(payload.password),
        data_policy_accepted_at=datetime.now(timezone.utc),
        data_policy_version="2026.2",
    )
    db.add(user)
    await db.flush()
    background_tasks.add_task(send_registration_email, user.email, user.full_name)
    return TokenOut(access_token=create_access_token(user.id, user.role), user_id=user.id, name=user.full_name, email=user.email, role=user.role)


@router.post("/register-company", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register_company(payload: CompanyRegister, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Create a company and its first partner account in one transaction."""
    existing_user = (await db.execute(select(User.id).where(User.email == payload.email))).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được đăng ký.")
    existing_company = (await db.execute(select(Company.id).where(Company.name == payload.company_name))).scalar_one_or_none()
    if existing_company is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tên doanh nghiệp đã được đăng ký.")
    normalized_phone = func.regexp_replace(User.phone_number, "[^0-9]", "", "g")
    phone_in_use = (await db.execute(select(User.id).where(normalized_phone == payload.phone_number))).scalar_one_or_none()
    if phone_in_use is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Số điện thoại đã được đăng ký.")
    company = Company(
        name=payload.company_name,
        website=payload.company_website,
        industry=payload.company_industry,
        location=payload.company_location,
        is_partner=True,
    )
    db.add(company)
    await db.flush()
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        password_hash=hash_password(payload.password),
        role="partner",
        company_id=company.id,
        data_policy_accepted_at=datetime.now(timezone.utc),
        data_policy_version="2026.2",
    )
    db.add(user)
    await db.flush()
    background_tasks.add_task(send_registration_email, user.email, user.full_name)
    return TokenOut(access_token=create_access_token(user.id, user.role), user_id=user.id, name=user.full_name, email=user.email, role=user.role)


@router.post("/login", response_model=TokenOut)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email hoặc mật khẩu không đúng.")
    return TokenOut(access_token=create_access_token(user.id, user.role), user_id=user.id, name=user.full_name, email=user.email, role=user.role)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
