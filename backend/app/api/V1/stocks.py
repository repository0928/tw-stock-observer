"""
Stock API Endpoints
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from app.database import get_db
from app.schemas import StockResponse, StockQuoteResponse, KlineDailyResponse, AnnouncementOut
from app.models import Stock, StockAnnouncement
from app.services.stock_service import StockService

# ==================== 通用篩選白名單 ====================
# 允許透過 {field}_min / {field}_max 篩選的數值欄位
# 新增欄位時，只需將欄位名稱加入此集合即可，無需修改任何其他邏輯
NUMERIC_FILTER_FIELDS = {
    # 行情
    "change_percent", "close_price", "open_price", "high_price", "low_price",
    "volume", "turnover_rate",
    # 估值
    "eps", "pe_ratio", "pb_ratio", "dividend_yield", "dividend_per_share",
    # 損益
    "revenue", "net_income",
    # 月營收
    "revenue_yoy", "revenue_mom",
    # 三大法人
    "foreign_net_buy", "investment_trust_net_buy", "dealer_net_buy",
    # 財報
    "gross_margin", "operating_margin", "net_margin",
    "roe", "roa", "debt_ratio",
    # 融資/融券
    "margin_long", "margin_short",
    # 股利
    "cash_dividend",
    # 預留擴充
    "market_cap", "book_value_per_share",
    "inventory_turnover", "receivable_turnover", "asset_turnover",
    "current_ratio", "quick_ratio",
}

# 允許布林篩選的欄位
BOOLEAN_FILTER_FIELDS = {"is_attention", "is_disposed", "is_etf", "is_active", "is_suspended"}

# 允許透過 {field}_contains 篩選的字串欄位
STRING_FILTER_FIELDS = {"name", "symbol", "sector", "industry"}

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/stocks",
    tags=["stocks"],
    responses={
        404: {"description": "股票未找到"},
        500: {"description": "伺服器錯誤"},
    },
)


# ==================== 同步端點 ====================

@router.post("/sync")
async def sync_stocks(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """從台灣證交所與櫃買中心同步所有上市/上櫃股票清單"""
    try:
        service = StockService(db)
        result = await service.sync_stocks_from_twse()
        return {
            "status": "success",
            "message": "股票同步完成",
            "result": result,
        }
    except Exception as e:
        logger.error(f"同步股票失敗: {e}")
        raise HTTPException(status_code=500, detail=f"同步失敗: {str(e)}")


# ==================== 股票列表端點 ====================

@router.get("/sectors")
async def list_sectors(db: AsyncSession = Depends(get_db)) -> dict:
    """取得所有產業列表"""
    try:
        stmt = select(distinct(Stock.sector)).where(
            Stock.is_active == True,
            Stock.sector != None
        ).order_by(Stock.sector)
        result = await db.execute(stmt)
        sectors = [row[0] for row in result.fetchall() if row[0]]
        return {"sectors": sectors}
    except Exception as e:
        logger.error(f"獲取產業列表失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("")
async def list_stocks(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    market_type: Optional[str] = None,
    sector: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """獲取股票列表

    支援通用數值篩選：{field}_min=值、{field}_max=值
    支援字串篩選：{field}_contains=值
    特殊篩選：close_at_high=true（收盤 = 最高）

    可用數值欄位：見 NUMERIC_FILTER_FIELDS 白名單
    """
    try:
        conditions = [Stock.is_active == True]
        if market_type:
            conditions.append(Stock.market_type == market_type)
        if sector:
            conditions.append(Stock.sector == sector)

        # ── 通用篩選解析 ──────────────────────────────────────────
        params = dict(request.query_params)
        for param, raw_value in params.items():
            # 數值欄位：{field}_min / {field}_max
            if param.endswith("_min"):
                field = param[:-4]
                if field in NUMERIC_FILTER_FIELDS and hasattr(Stock, field):
                    try:
                        conditions.append(getattr(Stock, field) >= float(raw_value))
                    except ValueError:
                        pass
            elif param.endswith("_max"):
                field = param[:-4]
                if field in NUMERIC_FILTER_FIELDS and hasattr(Stock, field):
                    try:
                        conditions.append(getattr(Stock, field) <= float(raw_value))
                    except ValueError:
                        pass
            # 字串欄位：{field}_contains
            elif param.endswith("_contains"):
                field = param[:-9]
                if field in STRING_FILTER_FIELDS and hasattr(Stock, field):
                    conditions.append(getattr(Stock, field).contains(raw_value))

            # 布林欄位：{field}=true / false
            elif param in BOOLEAN_FILTER_FIELDS and hasattr(Stock, param):
                if raw_value.lower() in ("true", "1"):
                    conditions.append(getattr(Stock, param) == True)
                elif raw_value.lower() in ("false", "0"):
                    conditions.append(getattr(Stock, param) == False)

        # 特殊篩選：收盤 = 最高（強勢收盤）
        if params.get("close_at_high") == "true":
            conditions.append(Stock.close_price != None)
            conditions.append(Stock.close_price == Stock.high_price)

        count_stmt = select(func.count()).select_from(Stock).where(*conditions)
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar()

        stmt = (
            select(Stock)
            .where(*conditions)
            .order_by(Stock.symbol)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        stocks = result.scalars().all()

        stocks_data = [StockResponse.from_orm(stock).dict() for stock in stocks]

        return {"total": total_count, "skip": skip, "limit": limit, "stocks": stocks_data}

    except Exception as e:
        logger.error(f"獲取股票列表失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/search/{keyword}")
async def search_stocks(
    keyword: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """搜尋股票"""
    try:
        if len(keyword) < 1:
            raise HTTPException(status_code=400, detail="搜尋關鍵字不能為空")

        service = StockService(db)
        stocks = await service.search_stocks(keyword)

        stocks_data = [StockResponse.from_orm(stock).dict() for stock in stocks]

        return {"keyword": keyword, "count": len(stocks_data), "stocks": stocks_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜尋股票失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


# ==================== 股票查詢端點 ====================

@router.get("/{symbol}/quote")
async def get_stock_quote(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """獲取股票實時行情"""
    try:
        service = StockService(db)
        stock = await service.get_stock_by_symbol(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")

        quote = await service.fetch_quote_from_twse(symbol)
        if not quote:
            raise HTTPException(status_code=500, detail=f"無法獲取股票行情: {symbol}")

        return quote

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取行情失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/{symbol}/info")
async def get_stock_info(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> StockResponse:
    """獲取股票基本資訊"""
    try:
        service = StockService(db)
        stock = await service.get_stock_by_symbol(symbol)

        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")

        return StockResponse.from_orm(stock)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取股票資訊失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/{symbol}/klines")
async def get_stock_klines(
    symbol: str,
    period: str = Query("1d", regex="^(1m|5m|15m|1h|1d)$"),
    limit: int = Query(100, ge=1, le=500),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """獲取股票 K線資料"""
    try:
        service = StockService(db)
        stock = await service.get_stock_by_symbol(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")

        klines = await service.get_klines(
            symbol=symbol,
            period=period,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )

        if not klines:
            return {"symbol": symbol, "period": period, "klines": [], "message": "尚無 K線資料"}

        klines_data = [KlineDailyResponse.from_orm(kline).dict() for kline in klines]

        return {"symbol": symbol, "period": period, "count": len(klines_data), "klines": klines_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取 K線失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/{symbol}/performance")
async def get_stock_performance(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """獲取股票績效"""
    try:
        service = StockService(db)
        stock = await service.get_stock_by_symbol(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")

        performance = await service.calculate_stock_performance(
            symbol=symbol, start_date=start_date, end_date=end_date,
        )

        if not performance:
            raise HTTPException(status_code=400, detail="無法計算績效，可能缺少足夠的 K線資料")

        return performance

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"計算績效失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/health/check")
async def health_check() -> dict:
    """股票 API 健康檢查"""
    return {"status": "healthy", "service": "stocks"}


# ==================== 重大訊息端點 ====================

@router.get("/{symbol}/announcements", response_model=List[AnnouncementOut])
async def get_stock_announcements(
    symbol: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[AnnouncementOut]:
    """取得指定股票的重大訊息（最新在前）"""
    try:
        stmt = (
            select(StockAnnouncement)
            .where(StockAnnouncement.symbol == symbol.upper())
            .order_by(StockAnnouncement.announce_date.desc(),
                      StockAnnouncement.id.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return [AnnouncementOut.from_orm(r) for r in rows]
    except Exception as e:
        logger.error(f"取得重大訊息失敗 {symbol}: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


if __name__ == "__main__":
    print("✅ 股票 API 路由已載入")
