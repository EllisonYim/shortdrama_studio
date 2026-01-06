from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path
from src.utils.config_loader import config_loader

# Default to SQLite if not configured
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "short_drama.db"
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_PATH}"

# Get URL from config
DATABASE_URL = config_loader.get("database.url", DEFAULT_DB_URL)

# Handle relative path for SQLite if user configured it manually but relatively
if DATABASE_URL.startswith("sqlite:///"):
    # Check if it's a relative path (sqlite:///./data/...)
    path_part = DATABASE_URL.replace("sqlite:///", "")
    if not Path(path_part).is_absolute():
        # Resolve relative to project root
        project_root = Path(__file__).resolve().parents[2]
        abs_path = (project_root / path_part).resolve()
        # Ensure dir exists
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f"sqlite:///{abs_path}"
    else:
        # Absolute path, ensure dir exists
        Path(path_part).parent.mkdir(parents=True, exist_ok=True)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL, connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
