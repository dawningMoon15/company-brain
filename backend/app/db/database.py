"""
database.py — SQLAlchemy database connection module

Loads the DATABASE_URL from .env, creates the synchronous SQLAlchemy
engine + session factory, and exports Base for all ORM models.
"""

import os
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ── Load environment variables from .env ──────────────────────────────────────
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Check your .env file.")

# ── Strip Supabase-specific query params unsupported by psycopg2 ──────────────
# Supabase pooler URLs include ?pgbouncer=true which psycopg2 rejects.
_parsed = urlparse(DATABASE_URL)
_params = {k: v for k, v in parse_qs(_parsed.query).items() if k != "pgbouncer"}
_clean_query = urlencode({k: v[0] for k, v in _params.items()})
DATABASE_URL_CLEAN = urlunparse(_parsed._replace(query=_clean_query))

# ── Engine ────────────────────────────────────────────────────────────────────
# connect_args is kept empty here; add {"check_same_thread": False} only for SQLite
engine = create_engine(
    DATABASE_URL_CLEAN,
    echo=False,          # Set True to log all SQL statements during development
    pool_pre_ping=True,  # Reconnect automatically if the connection drops
)

# ── Session factory ───────────────────────────────────────────────────────────
# autocommit=False  → we control transactions explicitly
# autoflush=False   → prevents premature flushes before we're ready
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ── Declarative base ──────────────────────────────────────────────────────────
# All ORM models inherit from this Base so SQLAlchemy knows about them
Base = declarative_base()


# ── Dependency helper (for route injection later) ─────────────────────────────
def get_db():
    """
    Yields a database session and ensures it is closed after each request.
    Usage in a route:
        def my_route(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
