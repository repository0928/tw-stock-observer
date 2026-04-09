"""
環境配置管理
Configuration Management for Different Environments
"""

import os
from typing import List
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    應用設置類
    支援從環境變數讀取配置
    """
    
    # ==================== 應用設置 ====================
    APP_NAME: str = "台股觀測站"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # ==================== API 設置 ====================
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_PREFIX: str = "/api/v1"
    
    # ==================== 資料庫設置 ====================
    DB_DRIVER: str = "postgresql+asyncpg"
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "tw_stock_observer")
    
    # 建立資料庫 URL
    @property
    def DATABASE_URL(self) -> str:
        """動態建立資料庫連接字符串"""
        return (
            f"{self.DB_DRIVER}://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    # 連接池設置
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    
    # ==================== Redis 設置 ====================
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    @property
    def REDIS_URL(self) -> str:
        """動態建立 Redis 連接字符串"""
        if self.REDIS_PASSWORD:
            return (
                f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}"
                f":{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # ==================== 快取設置 ====================
    CACHE_TTL_QUOTE: int = int(os.getenv("CACHE_TTL_QUOTE", "300"))  # 5 分鐘
    CACHE_TTL_KLINE: int = int(os.getenv("CACHE_TTL_KLINE", "3600"))  # 1 小時
    CACHE_TTL_PROFILE: int = int(os.getenv("CACHE_TTL_PROFILE", "86400"))  # 1 天
    
    # ==================== JWT 設置 ====================
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")
    )
    
    # ==================== CORS 設置 ====================
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173"
    )
    ALLOWED_HOSTS: str = os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1"
    )
    
    # ==================== 外部 API 設置 ====================
    # TWSE（台灣證交所）API
    TWSE_API_BASE_URL: str = "https://opendata.twse.com.tw"
    TWSE_API_TIMEOUT: int = int(os.getenv("TWSE_API_TIMEOUT", "30"))
    TWSE_RETRY_COUNT: int = int(os.getenv("TWSE_RETRY_COUNT", "3"))
    
    # Yahoo Finance API
    YAHOO_FINANCE_BASE_URL: str = "https://query1.finance.yahoo.com"
    YAHOO_FINANCE_TIMEOUT: int = int(os.getenv("YAHOO_FINANCE_TIMEOUT", "30"))
    
    # ==================== 日誌設置 ====================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # ==================== 郵件設置 ====================
    MAIL_ENABLED: bool = os.getenv("MAIL_ENABLED", "false").lower() == "true"
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    
    # ==================== 監控設置 ====================
    SENTRY_ENABLED: bool = os.getenv("SENTRY_ENABLED", "false").lower() == "true"
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    
    class Config:
        """Pydantic 配置"""
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    取得全域設置
    使用 lru_cache 確保只初始化一次
    """
    return Settings()


# 全域設置實例
settings = get_settings()


# ==================== 設置驗證 ====================
def validate_settings():
    """驗證設置是否正確"""
    
    # 驗證環境
    if settings.ENVIRONMENT not in ["development", "staging", "production"]:
        raise ValueError(f"無效的環境設置: {settings.ENVIRONMENT}")
    
    # 驗證資料庫連接字符串
    if "localhost" in settings.DATABASE_URL and settings.ENVIRONMENT == "production":
        raise ValueError("生產環境不能使用本地資料庫")
    
    # 驗證 SECRET_KEY
    if settings.SECRET_KEY == "dev-secret-key-change-in-production":
        if settings.ENVIRONMENT == "production":
            raise ValueError("必須在生產環境中設置 SECRET_KEY")
    
    return True


# 應用啟動時驗證設置
if __name__ != "__main__":
    try:
        validate_settings()
    except ValueError as e:
        import logging
        logging.warning(f"設置警告: {e}")
