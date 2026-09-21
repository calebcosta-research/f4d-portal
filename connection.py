from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

from model import Base

load_dotenv()


def _setting(name, default=None):
    """Read a non-secret setting, ignoring surrounding whitespace.

    Values typed or pasted into a host's settings page easily pick up a stray
    space, and 'pymssql ' then silently fails a comparison with 'pymssql'.
    Credentials are read directly instead: whitespace in a password could be
    genuine.
    """
    value = os.environ.get(name)
    return default if value is None else value.strip()


def _build_engine():
    """Create the SQLAlchemy engine for the configured backend.

    db_backend=sqlite    -> local single-file SQLite database (development).
    db_backend=postgres  -> PostgreSQL (the code default).
    db_backend=mssql     -> SQL Server / Azure SQL.

    For mssql, sql_driver picks the Python driver:
      sql_driver=pyodbc  (default) -> needs a system ODBC driver installed.
      sql_driver=pymssql           -> self-contained, no system driver, but
                                      username/password only.

    With pyodbc, sql_auth picks how the app proves who it is:
      sql_auth=sql       (default) -> sql_username / sql_password.
      sql_auth=msi                 -> the host's Azure managed identity; no
                                      password stored anywhere. Needs ODBC
                                      Driver 17.3+ or 18 on the host. Set
                                      sql_msi_client_id for a user-assigned
                                      identity; omit it for system-assigned.
    """
    backend = _setting("db_backend", "postgres").lower()

    if backend == "sqlite":
        database = _setting("sqlite_path", "f4d.db")
        return create_engine(f"sqlite:///{database}")

    # Both server backends need a host; if it's missing the settings aren't
    # reaching the process. Fail with a clear, diagnostic message instead of a
    # cryptic driver error.
    if not _setting("sql_host"):
        raise RuntimeError(
            "Database is not configured: sql_host is not set. A server backend "
            "needs db_backend (mssql or postgres), sql_host, sql_database and "
            "sql_port, plus credentials -- sql_username and sql_password, or "
            "sql_auth=msi for an Azure managed identity. "
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
        host = _setting("sql_host")
        database = _setting("sql_database", "postgres")
        port = _setting("sql_port", "5432")
        connection_string = (
            f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
            f"?sslmode=require"
        )
        return create_engine(connection_string, pool_pre_ping=True, pool_recycle=1800,
                             connect_args={"connect_timeout": 10})

    username = os.environ.get("sql_username")
    password = quote_plus(os.environ.get("sql_password", ""))
    host = _setting("sql_host")
    database = _setting("sql_database")
    port = _setting("sql_port", "1433")
    driver = _setting("sql_driver", "pyodbc").lower()

    if driver == "pymssql":
        # Self-contained driver (Azure App Service). TLS is negotiated
        # automatically, which Azure SQL requires.
        connection_string = (
            f"mssql+pymssql://{username}:{password}@{host}:{port}/{database}"
        )
        return create_engine(connection_string, pool_pre_ping=True, pool_recycle=1800)

    auth = _setting("sql_auth", "sql").lower()

    if auth in ("msi", "managed_identity"):
        # Azure managed identity: the ODBC driver fetches a token from the
        # host's identity endpoint itself, so there is no password to store.
        # The raw ODBC string goes through odbc_connect verbatim -- building it
        # from URL parts instead makes SQLAlchemy add Trusted_Connection=Yes
        # when there's no username, which conflicts with Authentication=.
        odbc_driver = _setting("sql_odbc_driver", "ODBC Driver 18 for SQL Server")
        parts = [
            f"Driver={{{odbc_driver}}}",
            f"Server=tcp:{host},{port}",
            f"Database={database}",
            "Encrypt=yes",
            "TrustServerCertificate=no",
            # Generous enough for a serverless database resuming from pause.
            "Connection Timeout=30",
            "Authentication=ActiveDirectoryMsi",
        ]
        client_id = _setting("sql_msi_client_id")
        if client_id:
            parts.append(f"UID={client_id}")
        odbc = ";".join(parts) + ";"
        return create_engine(
            "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc),
            pool_pre_ping=True, pool_recycle=1800, fast_executemany=True,
        )

    # SQL username/password over pyodbc -- what the live Posit Connect
    # deployment uses. Keep this unchanged.
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
