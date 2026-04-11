"""
股票 API 路由
Stock API Endpoints
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import StockResponse, StockQuoteResponse, KlineDailyResponse
from app.models import Stock
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

# 建立路由器
router = APIRouter(
    prefix="/stocks",
    tags=["stocks"],
    responses={
        404: {"description": "股票未找到"},
        500: {"description": "伺服器錯誤"},
    },
)


# ==================== 股票查詢端點 ====================

@router.get("/{symbol}/quote")
async def get_stock_quote(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    獲取股票實時行情
    
    - **symbol**: 股票代碼（如 "2330"）
    
    返回：
    - price: 當前價格
    - change: 漲跌點數
    - change_percent: 漲跌百分比
    - volume: 成交量
    """
    try:
        # 獲取服務實例
        service = StockService(db)
        
        # 從資料庫查詢股票
        stock = await service.get_stock_by_symbol(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")
        
        # 從外部 API 獲取行情
        quote = await service.fetch_quote_from_twse(symbol)
        if not quote:
            raise HTTPException(
                status_code=500,
                detail=f"無法獲取股票行情: {symbol}"
            )
        
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
    """
    獲取股票基本資訊
    
    - **symbol**: 股票代碼
    
    返回股票的詳細資訊：名稱、產業、基本面指標等
    """
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
    """
    獲取股票 K線資料
    
    - **symbol**: 股票代碼
    - **period**: 時間週期（1m, 5m, 15m, 1h, 1d）
    - **limit**: 返回筆數（最多 500）
    - **start_date**: 開始日期（可選）
    - **end_date**: 結束日期（可選）
    """
    try:
        service = StockService(db)
        
        # 驗證股票是否存在
        stock = await service.get_stock_by_symbol(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")
        
        # 獲取 K線資料
        klines = await service.get_klines(
            symbol=symbol,
            period=period,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
        
        if not klines:
            return {
                "symbol": symbol,
                "period": period,
                "klines": [],
                "message": "尚無 K線資料",
            }
        
        # 轉換為 Schema
        klines_data = [
            KlineDailyResponse.from_orm(kline).dict()
            for kline in klines
        ]
        
        return {
            "symbol": symbol,
            "period": period,
            "count": len(klines_data),
            "klines": klines_data,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取 K線失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


# ==================== 股票列表端點 ====================

@router.get("")
async def list_stocks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    獲取股票列表
    
    - **skip**: 跳過的筆數（分頁）
    - **limit**: 返回筆數
    """
    try:
        service = StockService(db)
        stocks = await service.get_all_stocks(skip=skip, limit=limit)
        
        stocks_data = [
            StockResponse.from_orm(stock).dict()
            for stock in stocks
        ]
        
        return {
            "total": len(stocks_data),
            "skip": skip,
            "limit": limit,
            "stocks": stocks_data,
        }
    
    except Exception as e:
        logger.error(f"獲取股票列表失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


@router.get("/search/{keyword}")
async def search_stocks(
    keyword: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    搜尋股票
    
    - **keyword**: 搜尋關鍵字（代碼或名稱）
    """
    try:
        if len(keyword) < 1:
            raise HTTPException(
                status_code=400,
                detail="搜尋關鍵字不能為空"
            )
        
        service = StockService(db)
        stocks = await service.search_stocks(keyword)
        
        stocks_data = [
            StockResponse.from_orm(stock).dict()
            for stock in stocks
        ]
        
        return {
            "keyword": keyword,
            "count": len(stocks_data),
            "stocks": stocks_data,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜尋股票失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


# ==================== 績效分析端點 ====================

@router.get("/{symbol}/performance")
async def get_stock_performance(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    獲取股票績效
    
    - **symbol**: 股票代碼
    - **start_date**: 開始日期（可選）
    - **end_date**: 結束日期（可選）
    
    返回：
    - gain: 收益金額
    - gain_percent: 收益百分比
    - volatility: 波動率
    """
    try:
        service = StockService(db)
        
        # 驗證股票是否存在
        stock = await service.get_stock_by_symbol(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票不存在: {symbol}")
        
        # 計算績效
        performance = await service.calculate_stock_performance(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
        
        if not performance:
            raise HTTPException(
                status_code=400,
                detail="無法計算績效，可能缺少足夠的 K線資料"
            )
        
        return performance
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"計算績效失敗: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")


# ==================== 健康檢查 ====================

@router.get("/health/check")
async def health_check() -> dict:
    """股票 API 健康檢查"""
    return {
        "status": "healthy",
        "service": "stocks",
        "timestamp": "2024-01-15T10:00:00Z",
    }


if __name__ == "__main__":
    print("✅ 股票 API 路由已載入")
