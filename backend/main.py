"""
台股觀測站 - FastAPI 應用入點
Taiwan Stock Observer - Main Application Entry Point
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import settings
from app.database import engine, init_db, get_db
from app.api.v1 import stocks

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    應用生命週期管理
    - 啟動：初始化資料庫
    - 關閉：清理資源
    """
    logger.info("🚀 應用啟動中...")
    
    # 啟動事件：初始化資料庫
    try:
        await init_db()
        logger.info("✅ 資料庫初始化成功")
    except Exception as e:
        logger.error(f"❌ 資料庫初始化失敗: {e}")
    
    yield
    
    logger.info("🛑 應用關閉中...")


# 建立 FastAPI 應用
app = FastAPI(
    title="台股觀測站 API",
    description="台灣股票市場監測和投資組合管理平台",
    version="1.0.0",
    lifespan=lifespan,
)


# 配置 CORS（跨域資源共享）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # 本地開發
        "http://localhost:3000",   # 備用開發埠
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ] if settings.DEBUG else settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 包含路由
app.include_router(stocks.router, prefix="/api/v1", tags=["stocks"])


# API 文檔自訂
def custom_openapi():
    """自訂 OpenAPI 文檔"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="台股觀測站 API",
        version="1.0.0",
        description="完整的台灣股票市場 API",
        routes=app.routes,
    )
    
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# 健康檢查端點
@app.get("/health")
async def health_check() -> dict:
    """
    健康檢查端點
    用於監控應用是否正常執行
    """
    return {
        "status": "healthy",
        "app": "台股觀測站",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }


# 根路由
@app.get("/")
async def root() -> dict:
    """根路由 - API 說明"""
    return {
        "message": "歡迎使用台股觀測站 API",
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
        "api_version": "1.0.0",
    }


# 全局異常處理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局異常處理"""
    logger.error(f"未捕獲的異常: {exc}", exc_info=True)
    return {
        "detail": "伺服器內部錯誤",
        "status_code": 500,
    }


if __name__ == "__main__":
    import uvicorn
    
    # 啟動開發伺服器
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
