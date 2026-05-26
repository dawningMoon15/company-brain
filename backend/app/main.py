"""
main.py — Company Brain FastAPI application entry point

Startup sequence:
  1. Import Base + engine from the database module
  2. Import all ORM models so SQLAlchemy registers their tables
  3. Call Base.metadata.create_all() to auto-create any missing tables
  4. Mount all routers (routes added here as the app grows)
"""

import logging

from fastapi import FastAPI

# ── Logging ───────────────────────────────────────────────────────────────────
# Show INFO-level logs from our own modules in the uvicorn console.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
)

# Auth router
from app.routes.auth import router as auth_router

# Workspace router
from app.routes.workspaces import router as workspaces_router

# Document router
from app.routes.documents import router as documents_router

# Database connection (engine + Base)
from app.db.database import Base, engine

# Import models so they are registered on Base before create_all runs
import app.models.user       # noqa: F401  (side-effect import — do not remove)
import app.models.workspace  # noqa: F401  (side-effect import — do not remove)
import app.models.document   # noqa: F401  (side-effect import — do not remove)

# ── Create tables ─────────────────────────────────────────────────────────────
# Creates tables that don't exist yet; skips tables that are already present.
# Replace with Alembic migrations when the schema matures.
Base.metadata.create_all(bind=engine)

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Company Brain API",
    description="Backend API for the Company Brain AI SaaS platform",
    version="0.1.0",
)


# ── Root health-check route ───────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"message": "Company Brain API running"}


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(documents_router)