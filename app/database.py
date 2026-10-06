import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Please check your .env file."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False
)


class Base(DeclarativeBase):
    """Parent class of all database models."""
    pass


def get_db():
    """Create one database session for each request."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()