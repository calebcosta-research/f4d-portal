from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

from model import Base

load_dotenv()


def _build_engine():
    """Create the SQLAlchemy engine for the configured backend.

    db_backend=sqlite  -> local single-file SQLite database (development).
    db_backend=mssql   -> SQL Server via pyodbc (production); the default,
                          so omitting the variable preserves prior behavior.
    """
    backend = os.environ.get("db_backend", "mssql").lower()

    if backend == "sqlite":
        database = os.environ.get("sqlite_path", "f4d.db")
        return create_engine(f"sqlite:///{database}")

    username = os.environ.get("sql_username")
    password = os.environ.get("sql_password")
    host = os.environ.get("sql_host")
    database = os.environ.get("sql_database")
    port = os.environ.get("sql_port")

    connection_string = (
        f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}"
        f"?driver={quote_plus('ODBC Driver 17 for SQL Server')}"
        f"&fast_executemany=true"
    )
    return create_engine(connection_string)


def create_session():
    engine = _build_engine()

    # Ensure tables exist (idempotent).
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    return Session()
