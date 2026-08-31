import os

from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL is not configured. " "Please set DATABASE_URL in your .env file."
    )


ENVIRONMENT = os.getenv(
    "ENVIRONMENT",
    "development",
).lower()

DATABASE_ECHO = (
    os.getenv(
        "DATABASE_ECHO",
        "false",
    ).lower()
    == "true"
)


engine = create_engine(
    DATABASE_URL,
    # -----------------------------------------------------
    # Connection health
    #
    # Automatically checks whether a connection is still
    # alive before giving it to the application.
    # -----------------------------------------------------
    pool_pre_ping=True,
    # -----------------------------------------------------
    # Recycle old connections.
    #
    # This is useful for hosted databases that terminate
    # idle connections after a period of time.
    # -----------------------------------------------------
    pool_recycle=1800,
    # -----------------------------------------------------
    # SQL logging
    #
    # Enabled only when DATABASE_ECHO=true.
    # -----------------------------------------------------
    echo=DATABASE_ECHO,
    # -----------------------------------------------------
    # Don't expire ORM objects immediately after commit.
    #
    # This makes service-layer code easier to work with.
    # -----------------------------------------------------
    future=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    # Don't automatically flush before every query.
    autoflush=False,
    # Transactions are committed explicitly.
    autocommit=False,
    # Keep objects usable after commit.
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    """
    Provide a database session for an application request.

    The session is always closed after the request finishes.

    This will be used later by FastAPI endpoints:

        db: Session = Depends(get_db)
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
