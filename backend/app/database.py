"""SQLAlchemy engine + session。"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

DATABASE_URL = (
    f"mysql+pymysql://{settings.db_user}:{settings.db_pass}"
    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}?charset=utf8mb4"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供一个 DB session 并在请求结束时关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
