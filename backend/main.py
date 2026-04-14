"""
台股觀測站 - FastAPI 應用入口點
"""
import logging
import ssl
import urllib.request
import json
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import engine, init_db, get_db
from app.api.V1 import stocks
from app.models import Stock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 同步函數 ====================

async def sync_quotes_job():
    """每日自動同步行情"""
    logger.info("⏰ 開始自動同步行情...")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # 上市行情
        url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json"
        with urllib.request.urlopen(url, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        rows = data.get("data", [])
        trade_date = data.get("date", "")

        async for db in get_db():
            updated = 0
            for row in rows:
                symbol = row[0].strip()
                if not symbol.isdigit():
                    continue
                try:
                    def parse(val):
                        v = val.replace(",", "").strip()
                        return float(v) if v not in ("--", "", "X") else None

                    close = parse(row[7])
                    change_str = row[8].replace(",", "").replace("+", "").strip()
                    change = float(change_str) if change_str not in ("--", "", "X") else None
                    change_pct = round(change / (close - change) * 100, 2) if change and close and (close - change) != 0 else None

                    stmt = select(Stock).where(Stock.symbol == symbol)
                    result = await db.execute(stmt)
                    stock = result.scalar_one_or_none()
                    if stock:
                        stock.open_price = parse(row[4])
                        stock.high_price = parse(row[5])
                        stock.low_price = parse(row[6])
                        stock.close_price = close
                        stock.change_amount = change
                        stock.change_percent = change_pct
                        vol = row[2].replace(",", "")
                        stock.volume = int(vol) if vol.isdigit() else None
                        stock.trade_date = trade_date
                        stock.updated_at = datetime.utcnow()
                        updated += 1
                except Exception as e:
                    logger.error(f"更新 {symbol} 失敗: {e}")

            await db.commit()
            logger.info(f"✅ 上市行情同步完成: {updated} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 自動同步行情失敗: {e}")


async def sync_sectors_job():
    """每週自動同步產業分類"""
    logger.info("⏰ 開始自動同步產業...")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        with urllib.request.urlopen(url, context=ctx, timeout=30) as resp:
            content = resp.read().decode('big5', errors='ignore')

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'lxml')

        async for db in get_db():
            updated = 0
            for row in soup.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue
                code_name = cols[0].text.strip()
                sector = cols[4].text.strip()
                if '\u3000' in code_name and sector:
                    symbol = code_name.split('\u3000')[0].strip()
                    if symbol.isdigit():
                        stmt = select(Stock).where(Stock.symbol == symbol)
                        result = await db.execute(stmt)
                        stock = result.scalar_one_or_none()
                        if stock:
                            stock.sector = sector
                            stock.updated_at = datetime.utcnow()
                            updated += 1
            await db.commit()
            logger.info(f"✅ 產業同步完成: {updated} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 自動同步產業失敗: {e}")

async def sync_pe_job():
    """每日自動同步本益比、淨值比"""
    logger.info("⏰ 開始自動同步本益比...")
    try:
        import ssl
        import urllib.request
        import json
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        url = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?response=json"
        with urllib.request.urlopen(url, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        rows = data.get("data", [])

        async for db in get_db():
            updated = 0
            for row in rows:
                symbol = row[0].strip()
                if not symbol.isdigit():
                    continue
                try:
                    def safe_float(val):
                        v = val.replace(",", "").strip()
                        return float(v) if v not in ('-', '--', '', 'N/A') else None
                    
                    pe = safe_float(row[5])
                    pb = safe_float(row[6])
                    
                    stmt = select(Stock).where(Stock.symbol == symbol)
                    result = await db.execute(stmt)
                    stock = result.scalar_one_or_none()
                    if stock:
                        stock.pe_ratio = pe
                        stock.pb_ratio = pb
                        stock.updated_at = datetime.utcnow()
                        updated += 1
                except Exception as e:
                    logger.error(f"更新本益比 {symbol} 失敗: {e}")
            
            await db.commit()
            logger.info(f"✅ 本益比同步完成: {updated} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 自動同步本益比失敗: {e}")

async def sync_eps_job():
    """每月自動同步 EPS、營收、淨利"""
    logger.info("⏰ 開始自動同步 EPS...")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        urls = [
            "https://openapi.twse.com.tw/v1/opendata/t187ap14_L",
            "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O",
        ]

        all_data = []
        for url in urls:
            with urllib.request.urlopen(url, context=ctx, timeout=30) as resp:
                all_data.extend(json.loads(resp.read().decode('utf-8')))

        async for db in get_db():
            updated = 0
            for item in all_data:
                symbol = item.get("公司代號", item.get("SecuritiesCompanyCode", "")).strip()
                if not symbol.isdigit():
                    continue
                try:
                    eps_str = item.get("基本每股盈餘(元)", item.get("基本每股盈餘", "")).strip()
                    eps = float(eps_str) if eps_str not in ("", "--", "N/A") else None
                    revenue_str = item.get("營業收入", "").strip()
                    revenue = int(float(revenue_str)) if revenue_str not in ("", "--") else None
                    net_income_str = item.get("稅後淨利", "").strip()
                    net_income = int(float(net_income_str)) if net_income_str not in ("", "--") else None

                    stmt = select(Stock).where(Stock.symbol == symbol)
                    result = await db.execute(stmt)
                    stock = result.scalar_one_or_none()
                    if stock:
                        stock.eps = eps
                        stock.revenue = revenue
                        stock.net_income = net_income
                        stock.updated_at = datetime.utcnow()
                        updated += 1
                except Exception as e:
                    logger.error(f"更新 EPS {symbol} 失敗: {e}")

            await db.commit()
            logger.info(f"✅ EPS 同步完成: {updated} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 自動同步 EPS 失敗: {e}")

# ==================== 應用生命週期 ====================

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("🚀 應用啟動中...")

    try:
        await init_db()
        logger.info("✅ 資料庫初始化成功")
    except Exception as e:
        logger.error(f"❌ 資料庫初始化失敗: {e}")

    # 設定排程：每天下午 4:30 同步行情（台股收盤後）
    scheduler.add_job(
        sync_quotes_job,
        CronTrigger(hour=8, minute=30, timezone="UTC"),  # UTC 8:30 = 台灣 16:30
        id="sync_quotes",
        replace_existing=True,
    )

    # 每週一早上同步產業分類
    scheduler.add_job(
        sync_sectors_job,
        CronTrigger(day_of_week="mon", hour=1, minute=0, timezone="UTC"),
        id="sync_sectors",
        replace_existing=True,
    )

    # 每天下午 5:00 同步本益比（收盤後）
    scheduler.add_job(
        sync_pe_job,
        CronTrigger(hour=9, minute=0, timezone="UTC"),  # UTC 9:00 = 台灣 17:00
        id="sync_pe",
        replace_existing=True,
    )

    # 每月11日早上同步 EPS（財報每季更新）
    scheduler.add_job(
        sync_eps_job,
        CronTrigger(day=11, hour=2, minute=0, timezone="UTC"),
        id="sync_eps",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("✅ 排程器已啟動（每日 16:30 台灣時間同步行情）")

    yield

    scheduler.shutdown()
    logger.info("🛑 應用關閉中...")


# ==================== 建立應用 ====================

app = FastAPI(
    title="台股觀測站 API",
    description="台灣股票市場監測和投資組合管理平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ] if settings.DEBUG else settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router, prefix="/api/v1", tags=["stocks"])


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="台股觀測站 API",
        version="1.0.0",
        description="完整的台灣股票市場 API",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "app": "台股觀測站",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/")
async def root() -> dict:
    return {
        "message": "歡迎使用台股觀測站 API",
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
        "api_version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info",
    )#   t e s t  
 