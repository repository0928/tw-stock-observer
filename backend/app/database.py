"""
資料庫連接管理
Database Connection and Session Management
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)

# ==================== 資料庫配置 ====================

# ORM Base（所有模型都要繼承這個）
Base = declarative_base()

# 建立非同步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # 開發環境下打印 SQL 語句
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # 連接前檢查連接是否有效
)

# 建立非同步會話工廠
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ==================== 資料庫初始化 ====================

async def init_db():
    """
    初始化資料庫
    - 建立所有表（如果不存在）
    - 可選：插入初始數據
    """
    try:
        # 建立所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ 資料庫表建立成功")
    except Exception as e:
        logger.error(f"❌ 資料庫初始化失敗: {e}")
        raise


async def check_db_connection():
    """
    檢查資料庫連接
    用於健康檢查
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"❌ 資料庫連接失敗: {e}")
        return False


# ==================== 依賴注入 ====================

async def get_db() -> AsyncGenerator:
    """
    資料庫會話依賴注入
    在 FastAPI 路由中使用：
    
    @router.get("/items")
    async def get_items(db: AsyncSession = Depends(get_db)):
        ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"資料庫錯誤: {e}")
            raise
        finally:
            await session.close()


# ==================== 資料庫清理 ====================

async def close_db():
    """關閉資料庫連接"""
    await engine.dispose()
    logger.info("資料庫連接已關閉")


# ==================== ORM Base Models ====================

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid


class BaseModel(Base):
    """
    基礎模型類
    所有 ORM 模型都應繼承此類
    """
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


if __name__ == "__main__":
    import asyncio
    
    async def main():
        # 初始化資料庫
        await init_db()
        
        # 檢查連接
        is_connected = await check_db_connection()
        print(f"資料庫連接狀態: {'✅ 正常' if is_connected else '❌ 失敗'}")
    
    asyncio.run(main())
