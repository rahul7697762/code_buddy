# app/database.py
"""Database layer using SQLAlchemy for SQLite.
Provides engine, session factory, declarative base, and FastAPI dependency.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import Session
from typing import Generator

# SQLite database URL; using a relative path for the file.
SQLALCHEMY_DATABASE_URL = "sqlite:///./blog.db"

# Engine creation with echo for SQL logging and future flag.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,
    future=True,
    connect_args={"check_same_thread": False},
)

# Session factory.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

# Base class for model definitions.
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session.

    Yields:
        Session: SQLAlchemy session object.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
