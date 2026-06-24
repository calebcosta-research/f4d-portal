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
    db_backend=mssql   -> SQL Server / Azure SQL (production); the default,
                          so omitting the variable preserves prior behavior.

    For mssql, the Python driver is chosen by sql_driver:
      sql_driver=pyodbc  (default) -> needs the system ODBC Driver installed
                                      (local dev / on-prem).
      sql_driver=pymssql           -> self-contained driver, no system ODBC
                                      package. Used on Azure App Service, whose
                                      Python image has no ODBC driver.
    """
    backend = os.environ.get("db_backend", "postgres").lower()

    if backend == "sqlite":
        database = os.environ.get("sqlite_path", "f4d.db")
        return create_engine(f"sqlite:///{database}")

    # Both server backends need a host; if it's missing the env vars aren't
    # reaching the process (e.g. Posit Connect Vars not set/applied). Fail with
    # a clear, diagnostic message instead of a cryptic driver import error.
    if not os.environ.get("sql_host"):
        raise RuntimeError(
            "Database is not configured. Set these environment variables "
            "(Posit Connect: content Settings > Vars): db_backend=postgres, "
            "sql_host, sql_username, sql_password, sql_database, sql_port=5432. "
            f"Currently seen -> db_backend={backend!r}, "
            f"sql_host={os.environ.get('sql_host')!r}, "
            f"sql_database={os.environ.get('sql_database')!r}."
        )

    if backend == "postgres":
        # Azure Database for PostgreSQL (flexible server). psycopg2 is a
        # self-contained wheel, so this works on App Service with no system
        # driver. Azure requires TLS, hence sslmode=require. Set db_schema
        # blank for postgres so tables land in the default 'public' schema.
        username = os.environ.get("sql_username")
        password = quote_plus(os.environ.get("sql_password", ""))
        host = os.environ.get("sql_host")
        database = os.environ.get("sql_database", "postgres")
        port = os.environ.get("sql_port", "5432")
        connection_string = (
            f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
            f"?sslmode=require"
        )
        return create_engine(connection_string, pool_pre_ping=True, pool_recycle=1800,
                             connect_args={"connect_timeout": 10})

    username = os.environ.get("sql_username")
    password = quote_plus(os.environ.get("sql_password", ""))
    host = os.environ.get("sql_host")
    database = os.environ.get("sql_database")
    port = os.environ.get("sql_port", "1433")
    driver = os.environ.get("sql_driver", "pyodbc").lower()

    if driver == "pymssql":
        # Self-contained driver (Azure App Service). TLS is negotiated
        # automatically, which Azure SQL requires.
        connection_string = (
            f"mssql+pymssql://{username}:{password}@{host}:{port}/{database}"
        )
        return create_engine(connection_string, pool_pre_ping=True, pool_recycle=1800)

    connection_string = (
        f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}"
        f"?driver={quote_plus('ODBC Driver 17 for SQL Server')}"
        f"&fast_executemany=true"
    )
    return create_engine(connection_string, pool_pre_ping=True, pool_recycle=1800)


# One engine (with a connection pool) and one session factory per process.
# Previously this module built a brand-new engine AND ran create_all() on EVERY
# create_session() call — and the app calls it many times per page render, so
# against a remote DB that was dozens of redundant round-trips per click. We now
# build the engine once and create tables once.
_engine = None
_Session = None


def create_session():
    global _engine, _Session
    if _Session is None:
        _engine = _build_engine()
        # Ensure tables exist (runs once per process, not per session).
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(bind=_engine)
    return _Session()
