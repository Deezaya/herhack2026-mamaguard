import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost/mamaguard"
)

# For production with Neon, use NullPool to avoid connection issues
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool if "neon" in DATABASE_URL else None,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
