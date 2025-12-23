from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from .config import settings
from typing import AsyncGenerator, Optional

# Create async engine (only if database_url is provided)
engine: Optional[object] = None
if settings.database_url:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_recycle=300,
    )

# Create async session factory (only if engine exists)
AsyncSessionLocal: Optional[async_sessionmaker] = None
if engine:
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    if not AsyncSessionLocal:
        raise RuntimeError(
            "Database not configured. Please set DATABASE_URL in your .env file. "
            "Get it from Supabase Dashboard → Settings → Database → Connection string"
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize database tables"""
    if not engine:
        raise RuntimeError("Database engine not initialized. Set DATABASE_URL in .env")
    async with engine.begin() as conn:
        # Import all models to ensure they are registered
        from app.models import Base
        await conn.run_sync(Base.metadata.create_all) 