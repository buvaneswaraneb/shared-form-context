from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings


def _async_url(url: str) -> str:
    # Neon/Vercel often supplies a postgresql:// URL, while SQLAlchemy's async
    # driver is asyncpg. Keep the setting convenient for both local and hosted use.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    # asyncpg names this parameter `ssl`; hosted providers commonly emit the
    # libpq spelling `sslmode` in their connection strings.
    url = url.replace("sslmode=require", "ssl=require")
    return url


settings = get_settings()
engine = create_async_engine(
    _async_url(settings.database_url),
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
