"""
Stock API Endpoints
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, asc, desc, nullslast
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
    # 基本面進階指標
    "core_profit_ratio", "free_cash_flow_ps", "interest_coverage",
}

# 允許布林篩選的欄位
BOOLEAN_FILTER_FIELDS = {"is_attention", "is_disposed", "is_etf", "is_active", "is_suspended", "roe_quality", "margin_surge"}

# 允許透過 {field}_contains 篩選的字串欄位
STRING_FILTER_FIELDS = {"name", "symbol", "sector", "industry", "revenue_note"}

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


# 允許伺服器端排序的欄位白名單
SORTABLE_FIELDS = NUMERIC_FILTER_FIELDS | {"symbol", "name", "sector", "market_type", "updated_at"}


@router.get("")
async def list_stocks(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    market_type: Optional[str] = None,
    sector: Optional[str] = None,
    sort_by: Optional[str] = Query(None, description="排序欄位"),
    sort_order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    symbols: Optional[str] = Query(None, description="逗號分隔的股票代號清單（Screener 白名單過濾）"),
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
        if symbols:
            symbol_list = [s.strip() for s in symbols.split(',') if s.strip()]
            if symbol_list:
                conditions.append(Stock.symbol.in_(symbol_list))

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

        # ── 排序 ──────────────────────────────────────────────────
        if sort_by and sort_by in SORTABLE_FIELDS and hasattr(Stock, sort_by):
            col = getattr(Stock, sort_by)
            # NULL 值永遠排在最後
            order_clause = nullslast(desc(col)) if sort_order == "desc" else nullslast(asc(col))
        else:
            order_clause = asc(Stock.symbol)

        stmt = (
            select(Stock)
            .where(*conditions)
            .order_by(order_clause)
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

# ==================== Goodinfo 財務資料同步端點 ====================

@router.post("/{symbol}/sync-financial")
async def sync_stock_financial(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    從 Goodinfo 爬取單一股票的 ROE、ROA、負債比率，並更新至資料庫。

    - **symbol**: 台股代碼，例如 `2330`

    > ⚠️ Goodinfo 有反爬蟲機制，請勿短時間內大量呼叫。
    """
    try:
        service = StockService(db)
        stock = await service.get_stock_by_symbol(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")

        result = await service.sync_financial_from_goodinfo(symbol)
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步財務資料失敗 {symbol}: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.post("/sync-financial-batch")
async def sync_financial_batch(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None,
    limit: int = Query(50, ge=1, le=2000),
    delay_seconds: float = Query(3.5, ge=1.0, le=30.0),
    background: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    批量從 Goodinfo 同步財務資料（ROE、ROA、負債比率）。

    - **symbols**: 指定股票代碼清單（JSON body），不填則取資料庫前 `limit` 筆股票
    - **limit**: 最多同步幾筆（預設 50，全量請帶 2000）
    - **delay_seconds**: 每次請求間隔秒數（預設 3.5，避免被封鎖）
    - **background**: true = 立即回傳，背景非同步執行（適合全量同步）

    > 全量 1800 檔 × 3.5 秒 ≈ 8 小時，建議 background=true。
    """
    from app.database import get_db as _get_db
    from app.services.stock_service import StockService as _StockService

    async def _run_full_sync(syms, lim, delay):
        """背景執行：自行建立獨立 db session"""
        try:
            async for _db in _get_db():
                svc = _StockService(_db)
                result = await svc.sync_financial_batch_from_goodinfo(
                    symbols=syms, limit=lim, delay_seconds=delay
                )
                logger.info(f"背景財務同步完成: {result}")
                break
        except Exception as e:
            logger.error(f"背景財務同步失敗: {e}")

    if background:
        background_tasks.add_task(_run_full_sync, symbols, limit, delay_seconds)
        return {
            "status": "started",
            "message": f"背景同步已啟動，最多同步 {limit} 筆，每筆間隔 {delay_seconds} 秒",
        }

    try:
        service = StockService(db)
        result = await service.sync_financial_batch_from_goodinfo(
            symbols=symbols,
            limit=limit,
            delay_seconds=delay_seconds,
        )
        return {"status": "completed", **result}

    except Exception as e:
        logger.error(f"批量財務資料同步失敗: {e}")
        raise HTTPException(status_code=500, detail=f"批量同步失敗: {str(e)}")


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


# ==================== 季度財務篩選端點（Screener） ====================

@router.post("/sync-quarterly-financials")
async def sync_quarterly_financials(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None,
    limit: int = Query(100, ge=1, le=2000),
    delay_seconds: float = Query(2.0, ge=1.0, le=30.0),
    background: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    手動觸發季度財務資料同步（首次部署補齊歷史資料用）。

    - **symbols**: 指定股票代碼清單（JSON body），不填則取資料庫前 `limit` 筆
    - **limit**: 最多同步幾筆（預設 100，全量請帶 2000）
    - **delay_seconds**: 每支股票間隔秒數（預設 2.0）
    - **background**: true = 立即回傳，背景非同步執行（全量同步建議使用）
    """
    from app.database import get_db as _get_db
    from app.services.goodinfo_scraper import fetch_goodinfo_financial
    from app.models import Stock, StockQuarterlyFinancial
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from decimal import Decimal
    import asyncio as _asyncio

    async def _run(syms, lim, delay):
        try:
            async for _db in _get_db():
                if syms:
                    target_symbols = syms
                else:
                    s = select(Stock.symbol).where(
                        Stock.is_active == True, Stock.is_etf == False
                    ).order_by(Stock.symbol).limit(lim)
                    r = await _db.execute(s)
                    target_symbols = [row[0] for row in r.fetchall()]

                success = failed = 0
                for i, sym in enumerate(target_symbols):
                    if i > 0:
                        await _asyncio.sleep(delay)
                    try:
                        data = await fetch_goodinfo_financial(sym)
                        for q in data.get("quarterly", []):
                            ins = pg_insert(StockQuarterlyFinancial).values(
                                symbol=sym, year=q["year"], quarter=q["quarter"],
                                gross_margin=q.get("gross_margin"),
                                operating_margin=q.get("operating_margin"),
                                net_income=q.get("net_income"),
                                revenue=q.get("revenue"),
                                contract_liabilities=q.get("contract_liabilities"),
                                inventories=q.get("inventories"),
                                updated_at=datetime.now(timezone.utc),
                            ).on_conflict_do_update(
                                index_elements=["symbol", "year", "quarter"],
                                set_={
                                    "gross_margin": q.get("gross_margin"),
                                    "operating_margin": q.get("operating_margin"),
                                    "net_income": q.get("net_income"),
                                    "revenue": q.get("revenue"),
                                    "contract_liabilities": q.get("contract_liabilities"),
                                    "inventories": q.get("inventories"),
                                    "updated_at": datetime.now(timezone.utc),
                                },
                            )
                            await _db.execute(ins)

                        # 計算 TTM 存貨周轉率
                        inv_turnover = await _calc_inv_turnover(_db, sym)
                        if inv_turnover is not None:
                            stock_s = select(Stock).where(Stock.symbol == sym)
                            stock_r = await _db.execute(stock_s)
                            stk = stock_r.scalar_one_or_none()
                            if stk:
                                stk.inventory_turnover = Decimal(str(inv_turnover))

                        if (i + 1) % 50 == 0:
                            await _db.commit()
                            logger.info(f"季度同步進度: {i+1}/{len(target_symbols)}")
                        success += 1
                    except Exception as e:
                        logger.error(f"季度同步 {sym} 失敗: {e}")
                        failed += 1

                await _db.commit()
                logger.info(f"✅ 季度財務同步完成: 成功 {success}，失敗 {failed}")
                break
        except Exception as e:
            logger.error(f"❌ 背景季度同步失敗: {e}")

    async def _calc_inv_turnover(_db, symbol):
        from app.models import StockQuarterlyFinancial
        from sqlalchemy import desc as _desc
        stmt = (
            select(StockQuarterlyFinancial)
            .where(StockQuarterlyFinancial.symbol == symbol)
            .order_by(_desc(StockQuarterlyFinancial.year), _desc(StockQuarterlyFinancial.quarter))
            .limit(4)
        )
        res = await _db.execute(stmt)
        rows = res.scalars().all()
        if not rows:
            return None
        latest = rows[0]
        if not latest.inventories or latest.inventories == 0:
            return None
        ttm_cogs = 0.0
        vq = 0
        for row in rows:
            if row.revenue is None or row.gross_margin is None:
                continue
            ttm_cogs += float(row.revenue) * (1 - float(row.gross_margin) / 100)
            vq += 1
        if vq == 0:
            return None
        return round(ttm_cogs * (4 / vq) / float(latest.inventories), 2)

    if background:
        background_tasks.add_task(_run, symbols, limit, delay_seconds)
        return {"status": "started", "message": f"背景季度同步已啟動，最多同步 {limit} 筆"}

    try:
        await _run(symbols, limit, delay_seconds)
        return {"status": "completed", "message": "季度財務同步完成"}
    except Exception as e:
        logger.error(f"季度財務同步失敗: {e}")
        raise HTTPException(status_code=500, detail=f"同步失敗: {str(e)}")


@router.get("/screener/gross-margin-rising")
async def screener_gross_margin_rising(
    min_margin: float = Query(30.0, description="每季毛利率下限（%）"),
    quarters: int = Query(4, ge=2, le=8, description="需要連續幾季"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：最近 N 季毛利率均 ≥ min_margin，且逐季嚴格遞增。
    使用單一 SQL Window Function，避免 N+1 查詢問題。
    """
    from sqlalchemy import text

    try:
        # 單一 SQL：用 ROW_NUMBER() 取各股最近 N 季，再做 PIVOT + 過濾
        sql = text("""
            WITH ranked AS (
                SELECT symbol, year, quarter, gross_margin,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol
                           ORDER BY year DESC, quarter DESC
                       ) AS rn
                FROM stock_quarterly_financials
                WHERE gross_margin IS NOT NULL
            ),
            pivoted AS (
                SELECT
                    symbol,
                    COUNT(*)                                             AS cnt,
                    MIN(gross_margin)                                    AS min_gm,
                    MAX(CASE WHEN rn = 1 THEN gross_margin END)         AS gm1,
                    MAX(CASE WHEN rn = 2 THEN gross_margin END)         AS gm2,
                    MAX(CASE WHEN rn = 3 THEN gross_margin END)         AS gm3,
                    MAX(CASE WHEN rn = 4 THEN gross_margin END)         AS gm4,
                    MAX(CASE WHEN rn = 5 THEN gross_margin END)         AS gm5,
                    MAX(CASE WHEN rn = 6 THEN gross_margin END)         AS gm6,
                    MAX(CASE WHEN rn = 7 THEN gross_margin END)         AS gm7,
                    MAX(CASE WHEN rn = 8 THEN gross_margin END)         AS gm8
                FROM ranked
                WHERE rn <= :quarters
                GROUP BY symbol
            )
            SELECT symbol, gm1, gm2, gm3, gm4, gm5, gm6, gm7, gm8
            FROM pivoted
            WHERE cnt = :quarters
              AND min_gm >= :min_margin
        """)
        res = await db.execute(sql, {"quarters": quarters, "min_margin": min_margin})
        candidates = res.fetchall()

        matched_symbols = []
        for row in candidates:
            sym = row[0]
            gms = [row[i+1] for i in range(quarters) if row[i+1] is not None]
            if len(gms) < quarters:
                continue
            gms_f = [float(g) for g in gms]
            # 嚴格遞增（gm1 最新，gm2 次新，…）
            if all(gms_f[i] > gms_f[i+1] for i in range(len(gms_f)-1)):
                matched_symbols.append(sym)

        return {
            "count": len(matched_symbols),
            "symbols": matched_symbols,
        }
    except Exception as e:
        logger.error(f"screener gross-margin-rising 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/net-income-outpace-revenue")
async def screener_net_income_outpace_revenue(
    quarters: int = Query(1, ge=1, le=4, description="最近幾季均需符合（預設 1 = 最新季）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：淨利年增率 > 營收年增率（利潤率擴張）。
    使用單一 SQL，自我 JOIN 取得去年同季，避免 N+1 查詢問題。
    """
    from sqlalchemy import text

    try:
        # 單一 SQL：self-join 取各股最新 N 季及去年同季，計算 YoY 並比較
        sql = text("""
            WITH ranked AS (
                SELECT symbol, year, quarter, net_income, revenue,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol
                           ORDER BY year DESC, quarter DESC
                       ) AS rn
                FROM stock_quarterly_financials
                WHERE net_income IS NOT NULL AND revenue IS NOT NULL
            ),
            recent AS (
                SELECT r.symbol, r.year, r.quarter, r.net_income, r.revenue, r.rn,
                       p.net_income AS prev_ni, p.revenue AS prev_rev
                FROM ranked r
                JOIN stock_quarterly_financials p
                  ON p.symbol = r.symbol
                 AND p.year   = r.year - 1
                 AND p.quarter = r.quarter
                 AND p.net_income IS NOT NULL
                 AND p.revenue IS NOT NULL
                WHERE r.rn <= :quarters
                  AND p.net_income <> 0
                  AND p.revenue    <> 0
            ),
            check_pass AS (
                SELECT symbol,
                       COUNT(*) AS matched_qtrs,
                       BOOL_AND(
                           (r.net_income - r.prev_ni) / ABS(r.prev_ni)
                           > (r.revenue - r.prev_rev) / ABS(r.prev_rev)
                       ) AS all_pass
                FROM recent r
                GROUP BY symbol
            )
            SELECT symbol
            FROM check_pass
            WHERE matched_qtrs = :quarters AND all_pass = TRUE
        """)
        res = await db.execute(sql, {"quarters": quarters})
        matched_symbols = [row[0] for row in res.fetchall()]

        return {
            "count": len(matched_symbols),
            "symbols": matched_symbols,
        }
    except Exception as e:
        logger.error(f"screener net-income-outpace-revenue 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/contract-liabilities-growth")
async def screener_contract_liabilities_growth(
    min_qoq_pct: float = Query(20.0, description="單季 QoQ 增幅門檻（%，條件 B）"),
    consecutive: int = Query(3, ge=2, le=8, description="連續季增幾季（條件 A）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：合約負債「連續 N 季增加（條件 A）」OR「單季 QoQ ≥ min_qoq_pct%（條件 B）」。
    使用單一 SQL Window Function，避免 N+1 查詢問題。
    """
    from sqlalchemy import text

    try:
        need = consecutive + 1  # 連續判斷需多取 1 季作為起始基準

        sql = text("""
            WITH ranked AS (
                SELECT symbol, year, quarter, contract_liabilities,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol
                           ORDER BY year DESC, quarter DESC
                       ) AS rn
                FROM stock_quarterly_financials
                WHERE contract_liabilities IS NOT NULL
            ),
            pivoted AS (
                SELECT
                    symbol,
                    COUNT(*)                                                     AS cnt,
                    MAX(CASE WHEN rn = 1 THEN contract_liabilities END)          AS cl1,
                    MAX(CASE WHEN rn = 2 THEN contract_liabilities END)          AS cl2,
                    MAX(CASE WHEN rn = 3 THEN contract_liabilities END)          AS cl3,
                    MAX(CASE WHEN rn = 4 THEN contract_liabilities END)          AS cl4,
                    MAX(CASE WHEN rn = 5 THEN contract_liabilities END)          AS cl5,
                    MAX(CASE WHEN rn = 6 THEN contract_liabilities END)          AS cl6,
                    MAX(CASE WHEN rn = 7 THEN contract_liabilities END)          AS cl7,
                    MAX(CASE WHEN rn = 8 THEN contract_liabilities END)          AS cl8,
                    MAX(CASE WHEN rn = 9 THEN contract_liabilities END)          AS cl9
                FROM ranked
                WHERE rn <= :need
                GROUP BY symbol
            )
            SELECT symbol, cl1, cl2, cl3, cl4, cl5, cl6, cl7, cl8, cl9
            FROM pivoted
            WHERE cnt >= 2 AND cl1 IS NOT NULL AND cl2 IS NOT NULL
        """)
        res = await db.execute(sql, {"need": need})
        candidates = res.fetchall()

        matched_symbols = []
        for row in candidates:
            sym = row[0]
            # collect available cl values (cl1=newest)
            cl_vals = [float(row[i+1]) for i in range(need) if row[i+1] is not None]
            if len(cl_vals) < 2:
                continue

            # 條件 B：最新一季 QoQ ≥ min_qoq_pct
            cond_b = False
            if cl_vals[1] != 0:
                qoq = (cl_vals[0] - cl_vals[1]) / abs(cl_vals[1]) * 100
                cond_b = qoq >= min_qoq_pct

            # 條件 A：連續 consecutive 季嚴格遞增
            cond_a = False
            if len(cl_vals) >= consecutive + 1:
                cond_a = all(cl_vals[i] > cl_vals[i+1] for i in range(consecutive))

            if cond_a or cond_b:
                matched_symbols.append(sym)

        return {
            "count": len(matched_symbols),
            "symbols": matched_symbols,
        }
    except Exception as e:
        logger.error(f"screener contract-liabilities-growth 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/roe-quality")
async def screener_roe_quality(
    min_roe: float = Query(15.0, description="ROE 下限（%）"),
    min_op_margin: float = Query(10.0, description="營業利益率下限（%）"),
    min_gm: float = Query(30.0, description="毛利率下限（%）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：ROE 品質股（高效率且穩健獲利）。

    條件：
    - ROE >= min_roe（預設 15%）
    - 營業利益率 >= min_op_margin（預設 10%）— 排除靠業外灌水的 ROE
    - 毛利率 >= min_gm（預設 30%）— 確保有護城河
    - 本業獲利佔比 >= 70%（若已計算）

    說明：
    由於需要跨年 ROE 歷史資料，此篩選以「當期多維度品質交叉驗證」
    替代純粹的「連續 3 年 ROE > 15%」，實際效果相近。
    """
    try:
        conditions = [
            Stock.is_active == True,
            Stock.roe >= min_roe,
            Stock.operating_margin >= min_op_margin,
            Stock.gross_margin >= min_gm,
        ]
        stmt = select(Stock.symbol).where(*conditions).order_by(Stock.roe.desc())
        result = await db.execute(stmt)
        symbols = [r[0] for r in result.fetchall()]

        return {
            "count": len(symbols),
            "symbols": symbols,
            "criteria": {
                "roe_min": min_roe,
                "operating_margin_min": min_op_margin,
                "gross_margin_min": min_gm,
            },
        }
    except Exception as e:
        logger.error(f"screener roe-quality 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/core-profit")
async def screener_core_profit(
    min_ratio: float = Query(80.0, description="本業獲利佔比下限（%）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：本業獲利佔比 >= min_ratio%。
    本業獲利佔比 = 營業利益 / 稅後淨利 × 100，
    高於 80% 代表獲利主要來自本業，非業外一次性灌水。
    """
    try:
        conditions = [
            Stock.is_active == True,
            Stock.core_profit_ratio >= min_ratio,
        ]
        stmt = select(Stock.symbol).where(*conditions).order_by(
            Stock.core_profit_ratio.desc()
        )
        result = await db.execute(stmt)
        symbols = [r[0] for r in result.fetchall()]

        return {"count": len(symbols), "symbols": symbols}
    except Exception as e:
        logger.error(f"screener core-profit 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/{symbol}/revenue-history")
async def get_revenue_history(
    symbol: str,
    months: int = Query(6, ge=2, le=24, description="取最近幾個月"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    取得個股最近 N 個月月營收年增率歷史，用於 Sparkline 趨勢圖。
    若無歷史表資料，回傳當前單月資料。
    """
    from sqlalchemy import text as _text
    try:
        # 嘗試從歷史表取資料
        stmt = _text("""
            SELECT year_month, revenue_yoy, revenue_mom
            FROM stock_revenue_monthly
            WHERE symbol = :symbol
            ORDER BY year_month DESC
            LIMIT :months
        """)
        result = await db.execute(stmt, {"symbol": symbol.upper(), "months": months})
        rows = result.fetchall()

        if rows:
            history = [
                {"year_month": r[0], "revenue_yoy": float(r[1]) if r[1] else None, "revenue_mom": float(r[2]) if r[2] else None}
                for r in reversed(rows)  # 由舊到新排列
            ]
            return {"symbol": symbol, "months": len(history), "history": history}

        # fallback：回傳當前單月資料
        stock_stmt = select(Stock).where(Stock.symbol == symbol.upper())
        stock_result = await db.execute(stock_stmt)
        stock = stock_result.scalar_one_or_none()
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")

        history = []
        if stock.revenue_yoy is not None:
            history = [{"year_month": stock.trade_date[:7] if stock.trade_date else "--",
                        "revenue_yoy": float(stock.revenue_yoy),
                        "revenue_mom": float(stock.revenue_mom) if stock.revenue_mom else None}]
        return {"symbol": symbol, "months": len(history), "history": history}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得月營收歷史失敗 {symbol}: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/operating-margin-rising")
async def screener_operating_margin_rising(
    min_margin: float = Query(10.0, description="每季營業利益率下限（%）"),
    quarters: int = Query(4, ge=2, le=8, description="需要連續幾季"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：最近 N 季營業利益率均 ≥ min_margin，且逐季嚴格遞增（走勢向上）。
    邏輯與 gross-margin-rising 相同，使用 stock_quarterly_financials.operating_margin。
    """
    from sqlalchemy import text

    try:
        sql = text("""
            WITH ranked AS (
                SELECT symbol, year, quarter, operating_margin,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol
                           ORDER BY year DESC, quarter DESC
                       ) AS rn
                FROM stock_quarterly_financials
                WHERE operating_margin IS NOT NULL
            ),
            pivoted AS (
                SELECT
                    symbol,
                    COUNT(*)                                                AS cnt,
                    MIN(operating_margin)                                   AS min_om,
                    MAX(CASE WHEN rn = 1 THEN operating_margin END)         AS om1,
                    MAX(CASE WHEN rn = 2 THEN operating_margin END)         AS om2,
                    MAX(CASE WHEN rn = 3 THEN operating_margin END)         AS om3,
                    MAX(CASE WHEN rn = 4 THEN operating_margin END)         AS om4,
                    MAX(CASE WHEN rn = 5 THEN operating_margin END)         AS om5,
                    MAX(CASE WHEN rn = 6 THEN operating_margin END)         AS om6,
                    MAX(CASE WHEN rn = 7 THEN operating_margin END)         AS om7,
                    MAX(CASE WHEN rn = 8 THEN operating_margin END)         AS om8
                FROM ranked
                WHERE rn <= :quarters
                GROUP BY symbol
            )
            SELECT symbol, om1, om2, om3, om4, om5, om6, om7, om8
            FROM pivoted
            WHERE cnt = :quarters
              AND min_om >= :min_margin
        """)
        res = await db.execute(sql, {"quarters": quarters, "min_margin": min_margin})
        candidates = res.fetchall()

        matched_symbols = []
        for row in candidates:
            sym = row[0]
            oms = [row[i + 1] for i in range(quarters) if row[i + 1] is not None]
            if len(oms) < quarters:
                continue
            oms_f = [float(o) for o in oms]
            # 嚴格遞增（om1 最新，om2 次新，…）
            if all(oms_f[i] > oms_f[i + 1] for i in range(len(oms_f) - 1)):
                matched_symbols.append(sym)

        return {
            "count": len(matched_symbols),
            "symbols": matched_symbols,
            "criteria": {"min_margin": min_margin, "quarters": quarters},
        }
    except Exception as e:
        logger.error(f"screener operating-margin-rising 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/revenue-yoy-consecutive")
async def screener_revenue_yoy_consecutive(
    months: int = Query(3, ge=2, le=12, description="需連續幾個月年增率為正"),
    min_yoy: float = Query(0.0, description="年增率下限（%，預設 0 即為正成長）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：月營收年增率連續 N 個月 ≥ min_yoy%。
    使用 stock_revenue_monthly 表，單一 SQL Window Function。
    """
    from sqlalchemy import text

    try:
        sql = text("""
            WITH ranked AS (
                SELECT symbol, year_month, revenue_yoy,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol
                           ORDER BY year_month DESC
                       ) AS rn
                FROM stock_revenue_monthly
                WHERE revenue_yoy IS NOT NULL
            ),
            check_pass AS (
                SELECT symbol,
                       COUNT(*)                              AS cnt,
                       BOOL_AND(revenue_yoy >= :min_yoy)    AS all_pass
                FROM ranked
                WHERE rn <= :months
                GROUP BY symbol
            )
            SELECT symbol
            FROM check_pass
            WHERE cnt = :months AND all_pass = TRUE
            ORDER BY symbol
        """)
        res = await db.execute(sql, {"months": months, "min_yoy": min_yoy})
        matched_symbols = [row[0] for row in res.fetchall()]

        return {
            "count": len(matched_symbols),
            "symbols": matched_symbols,
            "criteria": {"months": months, "min_yoy": min_yoy},
        }
    except Exception as e:
        logger.error(f"screener revenue-yoy-consecutive 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


if __name__ == "__main__":
    print("✅ 股票 API 路由已載入")


# ── 技術面篩選端點 ─────────────────────────────────────────────────────────────

@router.get("/screener/ma20-breakout")
async def screener_ma20_breakout(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：股價站上 MA20（最新收盤 > SMA20，且 5 日內有穿越）。
    """
    from sqlalchemy import text
    try:
        sql = text("""
            WITH latest AS (
                SELECT DISTINCT ON (symbol)
                    symbol, date, close, sma_20
                FROM klines_daily
                WHERE sma_20 IS NOT NULL
                ORDER BY symbol, date DESC
            ),
            prev5 AS (
                SELECT k.symbol,
                       BOOL_OR(k.close <= k.sma_20) AS had_below
                FROM klines_daily k
                JOIN (
                    SELECT symbol, date AS latest_date
                    FROM latest
                ) l ON k.symbol = l.symbol
                WHERE k.date >= (l.latest_date::date - INTERVAL '5 days')::text
                  AND k.date < l.latest_date
                GROUP BY k.symbol
            )
            SELECT l.symbol
            FROM latest l
            JOIN prev5 p ON l.symbol = p.symbol
            WHERE l.close > l.sma_20
              AND p.had_below = TRUE
            ORDER BY l.symbol
        """)
        res = await db.execute(sql)
        symbols = [r[0] for r in res.fetchall()]
        return {"count": len(symbols), "symbols": symbols, "criteria": {"type": "ma20_breakout"}}
    except Exception as e:
        logger.error(f"screener ma20-breakout 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/ma60-above")
async def screener_ma60_above(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：收盤站上 MA60（多頭格局）。
    """
    from sqlalchemy import text
    try:
        sql = text("""
            SELECT DISTINCT ON (symbol) symbol
            FROM klines_daily
            WHERE sma_50 IS NOT NULL
              AND close > sma_50
            ORDER BY symbol, date DESC
        """)
        res = await db.execute(sql)
        symbols = [r[0] for r in res.fetchall()]
        return {"count": len(symbols), "symbols": symbols, "criteria": {"type": "ma60_above"}}
    except Exception as e:
        logger.error(f"screener ma60-above 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/rsi-oversold")
async def screener_rsi_oversold(
    threshold: float = Query(30.0, ge=10.0, le=45.0, description="RSI 超賣門檻（預設 30）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：RSI14 低於門檻（超賣訊號）。
    """
    from sqlalchemy import text
    try:
        sql = text("""
            SELECT DISTINCT ON (symbol) symbol, rsi_14
            FROM klines_daily
            WHERE rsi_14 IS NOT NULL
              AND rsi_14 < :threshold
            ORDER BY symbol, date DESC
        """)
        res = await db.execute(sql, {"threshold": threshold})
        rows = res.fetchall()
        symbols = [r[0] for r in rows]
        return {
            "count": len(symbols), "symbols": symbols,
            "criteria": {"type": "rsi_oversold", "threshold": threshold},
        }
    except Exception as e:
        logger.error(f"screener rsi-oversold 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/macd-bullish")
async def screener_macd_bullish(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：MACD 柱狀圖由負轉正（近 3 日內翻多）。
    """
    from sqlalchemy import text
    try:
        sql = text("""
            WITH ranked AS (
                SELECT symbol, date, macd_histogram,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM klines_daily
                WHERE macd_histogram IS NOT NULL
            ),
            check_flip AS (
                SELECT symbol,
                       MAX(CASE WHEN rn = 1 THEN macd_histogram END) AS today_hist,
                       MAX(CASE WHEN rn BETWEEN 2 AND 3 THEN macd_histogram END) AS prev_hist
                FROM ranked
                WHERE rn <= 3
                GROUP BY symbol
            )
            SELECT symbol
            FROM check_flip
            WHERE today_hist > 0
              AND prev_hist <= 0
            ORDER BY symbol
        """)
        res = await db.execute(sql)
        symbols = [r[0] for r in res.fetchall()]
        return {"count": len(symbols), "symbols": symbols, "criteria": {"type": "macd_bullish"}}
    except Exception as e:
        logger.error(f"screener macd-bullish 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/screener/golden-cross")
async def screener_golden_cross(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    篩選：MA20 在近 5 日穿越 MA50（黃金交叉）。
    """
    from sqlalchemy import text
    try:
        sql = text("""
            WITH ranked AS (
                SELECT symbol, date, sma_20, sma_50,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM klines_daily
                WHERE sma_20 IS NOT NULL AND sma_50 IS NOT NULL
            ),
            latest AS (
                SELECT symbol,
                       MAX(CASE WHEN rn = 1 THEN sma_20 END) AS ma20_now,
                       MAX(CASE WHEN rn = 1 THEN sma_50 END) AS ma50_now,
                       MAX(CASE WHEN rn BETWEEN 2 AND 5 THEN
                           CASE WHEN sma_20 <= sma_50 THEN 1 ELSE 0 END
                       END) AS had_below
                FROM ranked
                WHERE rn <= 5
                GROUP BY symbol
            )
            SELECT symbol
            FROM latest
            WHERE ma20_now > ma50_now
              AND had_below = 1
            ORDER BY symbol
        """)
        res = await db.execute(sql)
        symbols = [r[0] for r in res.fetchall()]
        return {"count": len(symbols), "symbols": symbols, "criteria": {"type": "golden_cross"}}
    except Exception as e:
        logger.error(f"screener golden-cross 失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")
