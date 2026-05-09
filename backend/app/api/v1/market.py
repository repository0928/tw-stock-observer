"""
大盤指數 API
回傳加權指數、台指期（近月）、櫃買指數、VIX 恐慌指數
"""
import asyncio
import json
import logging
import ssl
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import certifi
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["market"])


def _ssl_ctx():
    return ssl.create_default_context(cafile=certifi.where())


async def _get(session: aiohttp.ClientSession, url: str, headers: dict = None) -> Optional[dict]:
    try:
        async with session.get(
            url, headers=headers or {},
            timeout=aiohttp.ClientTimeout(total=10),
            ssl=_ssl_ctx(),
        ) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f"GET {url} 失敗: {e}")
    return None


async def _post(session: aiohttp.ClientSession, url: str, payload: dict) -> Optional[dict]:
    try:
        async with session.post(
            url, json=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=aiohttp.ClientTimeout(total=10),
            ssl=_ssl_ctx(),
        ) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f"POST {url} 失敗: {e}")
    return None


async def _get_taiex() -> dict:
    """加權指數 — TWSE mis API"""
    url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw&json=1&delay=0"
    headers = {"Referer": "https://mis.twse.com.tw/", "User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as s:
        data = await _get(s, url, headers)
    try:
        item = data["msgArray"][0]
        price = float(item.get("z") or item.get("y") or 0)
        prev  = float(item.get("y", 0))
        change = round(price - prev, 2)
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {"name": "加權指數", "code": "TAIEX", "price": price, "change": change, "change_pct": change_pct}
    except Exception:
        pass
    return {"name": "加權指數", "code": "TAIEX", "price": None, "change": None, "change_pct": None}


async def _get_tpex() -> dict:
    """櫃買指數 — TWSE mis API (otc_o00)"""
    url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=otc_o00.tw&json=1&delay=0"
    headers = {"Referer": "https://mis.twse.com.tw/", "User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as s:
        data = await _get(s, url, headers)
    try:
        item = data["msgArray"][0]
        price = float(item.get("z") or item.get("y") or 0)
        prev  = float(item.get("y", 0))
        change = round(price - prev, 2)
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {"name": "櫃買指數", "code": "TPEx", "price": price, "change": change, "change_pct": change_pct}
    except Exception:
        pass
    return {"name": "櫃買指數", "code": "TPEx", "price": None, "change": None, "change_pct": None}


async def _get_futures() -> dict:
    """台指期（近月合約）— TAIFEX POST API"""
    url = "https://mis.taifex.com.tw/futures/api/getQuoteList"
    payload = {
        "MarketType": "0", "CommodityID": "TX", "ContractDate": "",
        "RowCount": "10", "OrderType": "asc", "IsShowRestrained": "0",
    }
    async with aiohttp.ClientSession() as s:
        data = await _post(s, url, payload)
    try:
        items = data["RtData"]["QuoteList"]
        # 排除現貨參考（TXF-S），選成交量最大的近月合約
        futures = [i for i in items if i.get("SymbolID", "").endswith("-F")]
        if not futures:
            return {"name": "台指期", "code": "FITX", "price": None, "change": None, "change_pct": None}
        # 取成交量最大者（近月）
        best = max(futures, key=lambda x: int(x.get("CTotalVolume") or 0))
        price = float(best.get("CLastPrice") or 0)
        prev  = float(best.get("CRefPrice") or best.get("COpenPrice") or 0)
        change = round(price - prev, 2)
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {"name": "台指期", "code": "FITX", "price": price, "change": change, "change_pct": change_pct}
    except Exception:
        pass
    return {"name": "台指期", "code": "FITX", "price": None, "change": None, "change_pct": None}


async def _get_vix() -> dict:
    """VIX 恐慌指數 — Yahoo Finance"""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=2d"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as s:
        data = await _get(s, url, headers)
    try:
        result = data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        price = round(closes[-1], 2)
        prev  = round(closes[-2], 2) if len(closes) >= 2 else price
        change = round(price - prev, 2)
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {"name": "VIX 恐慌指數", "code": "VIX", "price": price, "change": change, "change_pct": change_pct}
    except Exception:
        pass
    return {"name": "VIX 恐慌指數", "code": "VIX", "price": None, "change": None, "change_pct": None}


@router.get("/indices")
async def get_market_indices() -> dict:
    """取得四大指數：加權指數、台指期、櫃買指數、VIX"""
    taiex, futures, tpex, vix = await asyncio.gather(
        _get_taiex(), _get_futures(), _get_tpex(), _get_vix(),
    )
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "indices": [taiex, futures, tpex, vix],
    }
