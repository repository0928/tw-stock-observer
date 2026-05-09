"""
大盤指數 API
回傳加權指數、台指期、櫃買指數、VIX 恐慌指數
"""
import asyncio
import logging
import ssl
import certifi
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["market"])

# SSL context for aiohttp
def _ssl_ctx():
    ctx = ssl.create_default_context(cafile=certifi.where())
    return ctx


async def _fetch(session: aiohttp.ClientSession, url: str, headers: dict = None) -> Optional[dict]:
    try:
        async with session.get(
            url,
            headers=headers or {},
            timeout=aiohttp.ClientTimeout(total=10),
            ssl=_ssl_ctx(),
        ) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f"fetch {url} 失敗: {e}")
    return None


async def _get_taiex() -> dict:
    """加權指數 — TWSE 官方 API"""
    url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw&json=1&delay=0"
    headers = {"Referer": "https://mis.twse.com.tw/"}
    async with aiohttp.ClientSession() as session:
        data = await _fetch(session, url, headers)
    try:
        item = data["msgArray"][0]
        price = float(item.get("z") or item.get("y") or 0)
        prev  = float(item.get("y", 0))
        change = round(price - prev, 2)
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {
            "name": "加權指數",
            "code": "TAIEX",
            "price": price,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception:
        pass
    return {"name": "加權指數", "code": "TAIEX", "price": None, "change": None, "change_pct": None}


async def _get_tpex() -> dict:
    """櫃買指數 — TPEX 官方 API"""
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    async with aiohttp.ClientSession() as session:
        data = await _fetch(session, url)
    try:
        # TPEX API 回傳陣列，找指數欄位
        if isinstance(data, list) and data:
            # 找 code = "OTC" 或第一筆市場統計
            pass
    except Exception:
        pass

    # 改用 TPEX 指數專用 API
    url2 = "https://mis.tpex.org.tw/api/getOTC.jsp?json=1&delay=0"
    async with aiohttp.ClientSession() as session:
        data2 = await _fetch(session, url2)
    try:
        item = data2["msgArray"][0]
        price = float(item.get("z") or item.get("y") or 0)
        prev  = float(item.get("y", 0))
        change = round(price - prev, 2)
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {
            "name": "櫃買指數",
            "code": "TPEx",
            "price": price,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception:
        pass
    return {"name": "櫃買指數", "code": "TPEx", "price": None, "change": None, "change_pct": None}


async def _get_futures() -> dict:
    """台指期 — TAIFEX 期交所 API"""
    url = "https://mis.taifex.com.tw/futures/api/getQuoteList"
    payload_url = (
        "https://mis.taifex.com.tw/futures/api/getQuoteList"
        "?MarketType=0&CommodityID=TX&ContractDate=&RowCount=1&OrderType=asc&IsShowRestrained=0"
    )
    async with aiohttp.ClientSession() as session:
        data = await _fetch(session, payload_url)
    try:
        item = data["RTList"][0]
        price = float(item.get("CLastPrice", 0))
        prev  = float(item.get("CYesterdayPrice", 0) or item.get("COpenPrice", 0))
        change = round(price - prev, 2)
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {
            "name": "台指期",
            "code": "FITX",
            "price": price,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception:
        pass
    return {"name": "台指期", "code": "FITX", "price": None, "change": None, "change_pct": None}


async def _get_vix() -> dict:
    """VIX 恐慌指數 — Yahoo Finance"""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=2d"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        data = await _fetch(session, url, headers)
    try:
        result = data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        price = round(closes[-1], 2)
        prev  = round(closes[-2], 2) if len(closes) >= 2 else price
        change = round(price - prev, 2)
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {
            "name": "VIX 恐慌指數",
            "code": "VIX",
            "price": price,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception:
        pass
    return {"name": "VIX 恐慌指數", "code": "VIX", "price": None, "change": None, "change_pct": None}


@router.get("/indices")
async def get_market_indices() -> dict:
    """取得大盤四大指數：加權指數、台指期、櫃買指數、VIX 恐慌指數"""
    taiex, futures, tpex, vix = await asyncio.gather(
        _get_taiex(),
        _get_futures(),
        _get_tpex(),
        _get_vix(),
    )
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "indices": [taiex, futures, tpex, vix],
    }
