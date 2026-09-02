import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.user import User
from app.services.email_service import generate_verification_code, send_verification_email

SECRET_KEY = os.getenv(
    "SECRET_KEY", "closed-loop-super-secret-key-for-development-tokens"
)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)) -> str:
    payload = data.copy()
    expire = int(time.time()) + int(expires_delta.total_seconds())
    payload["exp"] = expire
    raw_payload = json.dumps(payload).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_payload).decode("utf-8").rstrip("=")
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{b64_payload}.{signature}"


def verify_access_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64_payload, signature = parts
        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        padded_b64 = b64_payload + "=" * (-len(b64_payload) % 4)
        raw_payload = base64.urlsafe_b64decode(padded_b64.encode("utf-8"))
        payload = json.loads(raw_payload.decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


# Schemas
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    organization_name: Optional[str] = None


class RegisterResponse(BaseModel):
    message: str
    email: str
    organization_name: str
    requires_verification: bool = True


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class ResendCodeRequest(BaseModel):
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    uuid: str
    name: str
    email: str
    role: str
    account_id: int
    is_active: bool
    is_verified: bool = True
    created_at: datetime
    organization_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ")[1]
    payload = verify_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = int(payload["sub"])
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled. Please contact your organization administrator.",
        )
    if not getattr(user, "is_verified", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified. Please verify your email to access your account.",
        )
    return user


def get_optional_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ")[1]
        payload = verify_access_token(token)
        if not payload or "sub" not in payload:
            return None
        user_id = int(payload["sub"])
        user = db.get(User, user_id)
        if user and user.is_active and getattr(user, "is_verified", True):
            return user
        return None
    except Exception:
        return None


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permissions required for this action.",
        )
    return current_user


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    clean_name = data.name.strip() if data.name else ""
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with your details: Full name is required.",
        )

    clean_email = data.email.lower().strip() if data.email else ""
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with your details: Please provide a valid email address.",
        )

    if not data.password or len(data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with your details: Password must be at least 6 characters long.",
        )

    existing = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with your details: An account with this email address already exists. Please log in or use a different email.",
        )

    code = generate_verification_code()
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    # 1. Create a dedicated new Organization / Account instance
    org_name = (
        data.organization_name.strip()
        if data.organization_name and data.organization_name.strip()
        else f"{clean_name}'s Organization"
    )
    new_account = Account(name=org_name)
    db.add(new_account)
    db.flush()

    # 2. Create the User as unverified Admin of this new organization
    user = User(
        name=clean_name,
        email=clean_email,
        password_hash=hash_password(data.password),
        account_id=new_account.id,
        role="admin",
        is_active=True,
        is_verified=False,
        verification_code=code,
        verification_code_expires_at=expires_at,
    )
    db.add(user)
    db.flush()

    # 3. Associate owner_id on account
    new_account.owner_id = user.id

    db.commit()
    db.refresh(user)
    db.refresh(new_account)

    # 4. Dispatch verification email
    send_verification_email(clean_email, clean_name, code)

    return {
        "message": "A 6-digit verification code has been sent to your email.",
        "email": user.email,
        "organization_name": new_account.name,
        "requires_verification": True,
    }


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    clean_email = data.email.lower().strip()
    clean_code = data.code.strip()

    user = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found. Please register first.",
        )

    if user.is_verified:
        # Already verified: generate login token
        account = db.get(Account, user.account_id)
        org_name = account.name if account else "Organization"
        token = create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "account_id": user.account_id,
            }
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "uuid": user.uuid,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "account_id": user.account_id,
                "is_active": user.is_active,
                "is_verified": True,
                "created_at": user.created_at,
                "organization_name": org_name,
            },
        }

    if not user.verification_code or user.verification_code != clean_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 6-digit verification code. Please check your email and try again.",
        )

    if user.verification_code_expires_at and datetime.utcnow() > user.verification_code_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please click 'Resend Code' to receive a new one.",
        )

    # Verification successful! Mark verified and clear code
    user.is_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None
    db.commit()
    db.refresh(user)

    account = db.get(Account, user.account_id)
    org_name = account.name if account else "Organization"

    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "account_id": user.account_id,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "uuid": user.uuid,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "account_id": user.account_id,
            "is_active": user.is_active,
            "is_verified": True,
            "created_at": user.created_at,
            "organization_name": org_name,
        },
    }


@router.post("/resend-code")
def resend_verification_code(data: ResendCodeRequest, db: Session = Depends(get_db)):
    clean_email = data.email.lower().strip()
    user = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address.",
        )

    if user.is_verified:
        return {"message": "Your email is already verified. You can sign in immediately."}

    code = generate_verification_code()
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    user.verification_code = code
    user.verification_code_expires_at = expires_at
    db.commit()

    send_verification_email(user.email, user.name, code)

    return {
        "message": f"A new 6-digit verification code has been sent to {user.email}.",
        "email": user.email,
    }


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    clean_email = data.email.lower().strip()
    user = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
    if not user or user.password_hash != hash_password(data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled. Please contact your organization administrator.",
        )

    if not getattr(user, "is_verified", True):
        # Trigger code send and notify user to verify
        code = generate_verification_code()
        user.verification_code = code
        user.verification_code_expires_at = datetime.utcnow() + timedelta(minutes=15)
        db.commit()
        send_verification_email(user.email, user.name, code)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. A 6-digit verification code has been sent to your email. Please verify to sign in.",
        )

    account = db.get(Account, user.account_id)
    org_name = account.name if account else "Organization"

    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "account_id": user.account_id,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "uuid": user.uuid,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "account_id": user.account_id,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
            "organization_name": org_name,
        },
    }


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.get(Account, current_user.account_id)
    org_name = account.name if account else "Organization"
    return {
        "id": current_user.id,
        "uuid": current_user.uuid,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "account_id": current_user.account_id,
        "is_active": current_user.is_active,
        "is_verified": getattr(current_user, "is_verified", True),
        "created_at": current_user.created_at,
        "organization_name": org_name,
    }


@router.post("/logout")
def logout():
    return {"message": "Logged out successfully"}
