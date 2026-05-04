"""
台股觀測站 - FastAPI 應用入口點
"""
import logging
import ssl
import certifi
import urllib.request
import json
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from datetime import datetime, timezone

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

def _ssl_ctx() -> ssl.SSLContext:
    """建立使用 certifi 憑證庫的 SSL context"""
    return ssl.create_default_context(cafile=certifi.where())


async def sync_quotes_job():
    """每日自動同步行情（上市 + 上櫃）"""
    logger.info("⏰ 開始自動同步行情...")
    ctx = _ssl_ctx()

    # ── 上市行情 ──
    try:
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

                    # 上市成交量單位為「股」
                    vol_str = row[2].replace(",", "").strip()
                    try:
                        volume = int(float(vol_str)) if vol_str else None
                    except (ValueError, TypeError):
                        volume = None

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
                        stock.volume = volume
                        stock.trade_date = trade_date
                        stock.updated_at = datetime.now(timezone.utc)
                        updated += 1
                except Exception as e:
                    logger.error(f"更新上市 {symbol} 失敗: {e}")

            await db.commit()
            logger.info(f"✅ 上市行情同步完成: {updated} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 同步上市行情失敗: {e}")

    # ── 上櫃行情 ──
    try:
        url2 = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        with urllib.request.urlopen(url2, context=ctx, timeout=30) as resp2:
            otc_data = json.loads(resp2.read().decode('utf-8'))

        async for db in get_db():
            updated2 = 0
            for item in otc_data:
                symbol = item.get("SecuritiesCompanyCode", "").strip()
                if not symbol.isdigit():
                    continue
                try:
                    def safe_float(val, default=None):
                        v = str(val).replace(",", "").strip()
                        if v in ("--", "", "0", "N/A"):
                            return default
                        try:
                            return float(v)
                        except (ValueError, TypeError):
                            return default

                    close   = safe_float(item.get("Close", ""))
                    open_p  = safe_float(item.get("Open", ""))
                    high    = safe_float(item.get("High", ""))
                    low     = safe_float(item.get("Low", ""))

                    change_str = str(item.get("Change", "")).replace(",", "").replace("+", "").strip()
                    change = None
                    if change_str not in ("--", "", "X", "N/A"):
                        try:
                            change = float(change_str)
                        except (ValueError, TypeError):
                            pass

                    change_pct = round(change / (close - change) * 100, 2) if change and close and (close - change) != 0 else None

                    # 上櫃 TradeVolume 單位為「張」(1張=1000股)，乘以 1000 換算為股數
                    vol_str = str(item.get("TradeVolume", "")).replace(",", "").strip()
                    try:
                        volume = int(float(vol_str)) * 1000 if vol_str else None
                    except (ValueError, TypeError):
                        volume = None

                    stmt = select(Stock).where(Stock.symbol == symbol)
                    result = await db.execute(stmt)
                    stock = result.scalar_one_or_none()
                    if stock:
                        stock.open_price  = open_p
                        stock.high_price  = high
                        stock.low_price   = low
                        stock.close_price = close
                        stock.change_amount  = change
                        stock.change_percent = change_pct
                        stock.volume      = volume
                        stock.updated_at  = datetime.now(timezone.utc)
                        updated2 += 1
                except Exception as e:
                    logger.error(f"更新上櫃 {symbol} 失敗: {e}")

            await db.commit()
            logger.info(f"✅ 上櫃行情同步完成: {updated2} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 同步上櫃行情失敗: {e}")


async def sync_sectors_job():
    """每週自動同步產業分類"""
    logger.info("⏰ 開始自動同步產業...")
    try:
        ctx = _ssl_ctx()

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
                            stock.updated_at = datetime.now(timezone.utc)
                            updated += 1
            await db.commit()
            logger.info(f"✅ 產業同步完成: {updated} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 自動同步產業失敗: {e}")


async def sync_pe_job():
    """每日自動同步本益比、淨值比（上市 + 上櫃）"""
    logger.info("⏰ 開始自動同步本益比...")
    ctx = _ssl_ctx()

    # ── 上市本益比 ──
    try:
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
                        stock.updated_at = datetime.now(timezone.utc)
                        updated += 1
                except Exception as e:
                    logger.error(f"更新上市本益比 {symbol} 失敗: {e}")

            await db.commit()
            logger.info(f"✅ 上市本益比同步完成: {updated} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 同步上市本益比失敗: {e}")

    # ── 上櫃本益比 ──
    try:
        url2 = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"
        with urllib.request.urlopen(url2, context=ctx, timeout=30) as resp2:
            otc_data = json.loads(resp2.read().decode('utf-8'))

        async for db in get_db():
            updated2 = 0
            for item in otc_data:
                symbol = item.get("SecuritiesCompanyCode", "").strip()
                if not symbol.isdigit():
                    continue
                try:
                    def safe_float2(val):
                        v = str(val).replace(",", "").strip()
                        return float(v) if v not in ('-', '--', '', '0', 'N/A') else None

                    pe = safe_float2(item.get("PriceEarningRatio", ""))
                    pb = safe_float2(item.get("PriceBookRatio", ""))

                    stmt = select(Stock).where(Stock.symbol == symbol)
                    result = await db.execute(stmt)
                    stock = result.scalar_one_or_none()
                    if stock:
                        stock.pe_ratio = pe
                        stock.pb_ratio = pb
                        stock.updated_at = datetime.now(timezone.utc)
                        updated2 += 1
                except Exception as e:
                    logger.error(f"更新上櫃本益比 {symbol} 失敗: {e}")

            await db.commit()
            logger.info(f"✅ 上櫃本益比同步完成: {updated2} 筆")
            break

    except Exception as e:
        logger.error(f"❌ 同步上櫃本益比失敗: {e}")


async def sync_financial_job():
    """每週自動從 Goodinfo 同步 ROE、ROA、負債比率"""
    logger.info("⏰ 開始自動同步 Goodinfo 財務資料（ROE / ROA / 負債比率）...")
    try:
        from app.services.goodinfo_scraper import fetch_goodinfo_financial
        from app.models import Stock
        from decimal import Decimal
        import asyncio

        async for db in get_db():
            # 取得所有啟用中的股票代碼
            stmt = select(Stock.symbol).where(Stock.is_active == True).order_by(Stock.symbol)
            result = await db.execute(stmt)
            symbols = [row[0] for row in result.fetchall()]
            logger.info(f"共 {len(symbols)} 支股票待同步財務資料")

            success = 0
            failed = 0
            for i, symbol in enumerate(symbols):
                try:
                    if i > 0:
                        await asyncio.sleep(2.0)  # FinMind API：每股票間隔 2 秒（加上內部 1 秒 = ~4 秒/股票，約 30 req/min，在免費額度內）

                    data = await fetch_goodinfo_financial(symbol)

                    stock_stmt = select(Stock).where(Stock.symbol == symbol)
                    stock_result = await db.execute(stock_stmt)
                    stock = stock_result.scalar_one_or_none()

                    if stock and any(v is not None for v in data.values()):
                        if data.get("roe") is not None:
                            stock.roe = Decimal(str(data["roe"]))
                        if data.get("roa") is not None:
                            stock.roa = Decimal(str(data["roa"]))
                        if data.get("debt_ratio") is not None:
                            stock.debt_ratio = Decimal(str(data["debt_ratio"]))
                        stock.financial_data_updated_at = datetime.now(timezone.utc)
                        success += 1

                    # 每 50 筆 commit 一次，減少記憶體壓力
                    if (i + 1) % 50 == 0:
                        await db.commit()
                        logger.info(f"  進度: {i+1}/{len(symbols)}，已成功 {success} 筆")

                except Exception as e:
                    logger.error(f"同步 {symbol} 財務資料失敗: {e}")
                    failed += 1

            await db.commit()
            logger.info(f"✅ Goodinfo 財務資料同步完成: 成功 {success}，失敗 {failed}")
            break

    except Exception as e:
        logger.error(f"❌ 自動同步 Goodinfo 財務資料失敗: {e}")


async def sync_eps_job():
    """每日自動同步 EPS、營收、淨利（上市 + 上櫃）"""
    logger.info("⏰ 開始自動同步 EPS / 營收 / 淨利...")
    try:
        ctx = _ssl_ctx()

        urls = [
            "https://openapi.twse.com.tw/v1/opendata/t187ap14_L",
            "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O",
        ]

        all_data = []
        for url in urls:
            try:
                with urllib.request.urlopen(url, context=ctx, timeout=30) as resp:
                    all_data.extend(json.loads(resp.read().decode('utf-8')))
            except Exception as e:
                logger.error(f"下載 {url} 失敗: {e}")

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
                    try:
                        revenue = int(float(revenue_str)) if revenue_str not in ("", "--") else None
                    except (ValueError, TypeError):
                        revenue = None

                    net_income_str = item.get("稅後淨利", "").strip()
                    try:
                        net_income = int(float(net_income_str)) if net_income_str not in ("", "--") else None
                    except (ValueError, TypeError):
                        net_income = None

                    stmt = select(Stock).where(Stock.symbol == symbol)
                    result = await db.execute(stmt)
                    stock = result.scalar_one_or_none()
                    if stock:
                        stock.eps = eps
                        stock.revenue = revenue
                        stock.net_income = net_income
                        stock.updated_at = datetime.now(timezone.utc)
                        updated += 1
                except Exception as e:
                    logger.error(f"更新 EPS {symbol} 失敗: {e}")

            await db.commit()
            logger.info(f"✅ EPS / 營收 / 淨利同步完成: {updated} 筆")
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

    # 每天 UTC 08:30（台灣 16:30，收盤後）同步行情
    scheduler.add_job(
        sync_quotes_job,
        CronTrigger(hour=8, minute=30, timezone="UTC"),
        id="sync_quotes",
        replace_existing=True,
    )

    # 每週一 UTC 01:00 同步產業分類
    scheduler.add_job(
        sync_sectors_job,
        CronTrigger(day_of_week="mon", hour=1, minute=0, timezone="UTC"),
        id="sync_sectors",
        replace_existing=True,
    )

    # 每天 UTC 09:00（台灣 17:00）同步本益比、淨值比
    scheduler.add_job(
        sync_pe_job,
        CronTrigger(hour=9, minute=0, timezone="UTC"),
        id="sync_pe",
        replace_existing=True,
    )

    # 每天 UTC 09:30（台灣 17:30）同步 EPS、營收、淨利
    scheduler.add_job(
        sync_eps_job,
        CronTrigger(hour=9, minute=30, timezone="UTC"),
        id="sync_eps",
        replace_existing=True,
    )

    # 每週日 UTC 16:10（台灣週一 00:10 凌晨）從 Goodinfo 同步 ROE / ROA / 負債比率
    # 1800 檔 × 3.5 秒 ≈ 8 小時，00:10 起跑可在週一 09:00 開盤前完成
    scheduler.add_job(
        sync_financial_job,
        CronTrigger(day_of_week="sun", hour=16, minute=10, timezone="UTC"),
        id="sync_financial",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("✅ 排程器已啟動")

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
    )
