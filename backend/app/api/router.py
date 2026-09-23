from __future__ import annotations

from fastapi import APIRouter

from .v1 import (
    applications,
    auth,
    certificates,
    cv,
    email,
    jobs,
    kg,
    portfolio,
    profile,
    skills,
)

api_router = APIRouter(prefix="/v1")
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)
api_router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"],
)
api_router.include_router(
    certificates.router,
    prefix="/certificates",
    tags=["Certificates"],
)
api_router.include_router(
    profile.router,
    prefix="/profile",
    tags=["Profile"],
)
api_router.include_router(
    jobs.router,
    prefix="/jobs",
    tags=["Jobs"],
)
api_router.include_router(
    applications.router,
    prefix="/applications",
    tags=["Applications"],
)
api_router.include_router(
    email.router,
    prefix="/email",
    tags=["Email"],
)
api_router.include_router(
    skills.router,
    prefix="/skills",
    tags=["Skills"],
)
api_router.include_router(
    cv.router,
    prefix="/cv",
    tags=["CV"],
)
api_router.include_router(
    kg.router,
    prefix="/kg",
    tags=["Knowledge Graph"],
)
