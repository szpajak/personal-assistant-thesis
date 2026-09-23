from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.security import create_access_token, hash_password, verify_password
from ...dependencies import get_current_user, get_db_session
from ...models.user import User
from ...schemas.user import Token, UserCreate, UserRead

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get the current logged in user."""
    return current_user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    response: Response,
    payload: UserCreate = Body(...),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Register a new user and set auth cookie."""
    # Check if user already exists
    query = select(User).where(User.email == payload.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Create new user
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Set auth cookie immediately after registration
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(hours=24),
    )
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
    )

    return user


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    email: str = Body(...),
    password: str = Body(...),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Login and set auth cookie."""
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(hours=24),
    )

    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        max_age=86400,
        samesite="lax",
        secure=False,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response) -> Any:
    """Clear the auth cookie."""
    response.delete_cookie(key="auth_token")
    return {"status": "ok"}
