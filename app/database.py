# app/database.py
import ssl
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from core.settings import settings

# Base directory for resolving file paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Build SSL context only if enabled in settings
ssl_context = None
if settings.db_ssl_enabled:
    ca_path = None

    # 1. Check custom CA file from environment variable if provided
    if settings.db_ssl_ca_file:
        custom_path = Path(settings.db_ssl_ca_file)
        if not custom_path.is_absolute():
            custom_path = BASE_DIR / custom_path
        if custom_path.is_file():
            ca_path = str(custom_path)
        else:
            print(f"[SSL WARNING] DB_SSL_CA_FILE '{settings.db_ssl_ca_file}' not found. Falling back to system CAs.")

    # 2. Check local fallback file if present
    if not ca_path:
        local_default = BASE_DIR / "core" / "ssl" / "ca.pem"
        if local_default.is_file():
            ca_path = str(local_default)

    # 3. Create context: with specific CA file if found, otherwise system/certifi default
    try:
        if ca_path:
            ssl_context = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cafile=ca_path,
            )
        else:
            try:
                import certifi
                ssl_context = ssl.create_default_context(
                    purpose=ssl.Purpose.SERVER_AUTH,
                    cafile=certifi.where(),
                )
            except Exception:
                ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
    except Exception as e:
        print(f"[SSL INIT WARNING] Could not configure strict SSL context: {e}")
        ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

# Ensure the URL uses asyncpg driver
SQLALCHEMY_DATABASE_URL = settings.database_url
is_postgres = SQLALCHEMY_DATABASE_URL.startswith("postgresql")
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

connect_args = {}
if is_postgres:
    if settings.db_ssl_enabled and ssl_context:
        connect_args["ssl"] = ssl_context
    connect_args["server_settings"] = {
        "application_name": "fastapi_app",
    }

# Create async engine with SSL and connection pooling
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,  # Set to True for SQL logging
    connect_args=connect_args,
    # future=True,
)

# Use async_sessionmaker (recommended over sessionmaker for async)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


# Dependency for FastAPI routes
async def get_db():
    """
    Dependency that provides a database session to route handlers.
    Automatically handles session cleanup.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Alternative: Manual session management
async def get_db_with_commit():
    """
    Alternative dependency that auto-commits on success.
    Use this if you want automatic transaction handling.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
