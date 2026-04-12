"""
股票業務邏輯服務層
Stock Service - Business Logic Layer
"""

import logging
import aiohttp
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models import Stock, KlineDaily
from app.schemas import StockResponse, StockQuoteResponse, KlineDailyResponse
from app.config import settings

logger = logging.getLogger(__name__)


class StockService:
    """股票服務類"""
    
    def __init__(self, db: AsyncSession):
        """初始化服務"""
        self.db = db
        self.twse_base_url = settings.TWSE_API_BASE_URL
        self.yahoo_base_url = settings.YAHOO_FINANCE_BASE_URL
        self.timeout = settings.TWSE_API_TIMEOUT
    
    # ==================== 股票查詢 ====================
    
    async def get_stock_by_symbol(self, symbol: str) -> Optional[Stock]:
        """根據代碼獲取股票"""
        try:
            stmt = select(Stock).where(Stock.symbol == symbol)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"查詢股票失敗 {symbol}: {e}")
            return None
    
    async def get_all_stocks(self, skip: int = 0, limit: int = 100) -> List[Stock]:
        """獲取所有股票列表"""
        try:
            stmt = (
                select(Stock)
                .where(Stock.is_active == True)
                .order_by(Stock.symbol)
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"獲取股票列表失敗: {e}")
            return []
    
    async def search_stocks(self, keyword: str) -> List[Stock]:
        """搜尋股票"""
        try:
            keyword = f"%{keyword}%"
            stmt = select(Stock).where(
                and_(
                    Stock.is_active == True,
                    (Stock.symbol.ilike(keyword)) | (Stock.name.ilike(keyword))
                )
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"搜尋股票失敗: {e}")
            return []
    
    # ==================== TWSE/TPEX 同步 ====================

    async def sync_stocks_from_twse(self) -> Dict:
        """
        從台灣證交所同步所有上市股票清單
        來源: https://opendata.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
        """
        added = 0
        updated = 0
        failed = 0

        try:
            url = "https://opendata.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        logger.error(f"TWSE API 回應錯誤: {response.status}")
                        return {"added": 0, "updated": 0, "failed": 0, "error": "TWSE API 錯誤"}
                    
                    data = await response.json()

            for item in data:
                try:
                    symbol = item.get("Code", "").strip()
                    name = item.get("Name", "").strip()
                    
                    if not symbol or not name:
                        continue
                    
                    # 只取純數字股票代碼（排除ETF、權證等）
                    if not symbol.isdigit():
                        continue

                    existing = await self.get_stock_by_symbol(symbol)
                    
                    if existing:
                        existing.name = name
                        existing.market_type = "上市"
                        existing.is_active = True
                        existing.updated_at = datetime.utcnow()
                        updated += 1
                    else:
                        stock = Stock(
                            symbol=symbol,
                            name=name,
                            market_type="上市",
                            is_active=True,
                            is_suspended=False,
                        )
                        self.db.add(stock)
                        added += 1

                except Exception as e:
                    logger.error(f"處理上市股票失敗 {item}: {e}")
                    failed += 1

            await self.db.commit()
            logger.info(f"上市股票同步完成: 新增 {added}, 更新 {updated}, 失敗 {failed}")

        except Exception as e:
            logger.error(f"同步上市股票失敗: {e}")
            await self.db.rollback()
            return {"added": 0, "updated": 0, "failed": 0, "error": str(e)}

        # 同步上櫃股票
        added_tpex, updated_tpex, failed_tpex = await self._sync_tpex_stocks()
        
        return {
            "twse": {"added": added, "updated": updated, "failed": failed},
            "tpex": {"added": added_tpex, "updated": updated_tpex, "failed": failed_tpex},
            "total_added": added + added_tpex,
            "total_updated": updated + updated_tpex,
        }

    async def _sync_tpex_stocks(self):
        """從櫃買中心同步所有上櫃股票"""
        added = 0
        updated = 0
        failed = 0

        try:
            url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        logger.error(f"TPEX API 回應錯誤: {response.status}")
                        return 0, 0, 0
                    
                    data = await response.json()

            for item in data:
                try:
                    symbol = item.get("SecuritiesCompanyCode", "").strip()
                    name = item.get("CompanyName", "").strip()

                    if not symbol or not name:
                        continue
                    
                    if not symbol.isdigit():
                        continue

                    existing = await self.get_stock_by_symbol(symbol)
                    
                    if existing:
                        existing.name = name
                        existing.market_type = "上櫃"
                        existing.is_active = True
                        existing.updated_at = datetime.utcnow()
                        updated += 1
                    else:
                        stock = Stock(
                            symbol=symbol,
                            name=name,
                            market_type="上櫃",
                            is_active=True,
                            is_suspended=False,
                        )
                        self.db.add(stock)
                        added += 1

                except Exception as e:
                    logger.error(f"處理上櫃股票失敗 {item}: {e}")
                    failed += 1

            await self.db.commit()
            logger.info(f"上櫃股票同步完成: 新增 {added}, 更新 {updated}, 失敗 {failed}")

        except Exception as e:
            logger.error(f"同步上櫃股票失敗: {e}")
            await self.db.rollback()

        return added, updated, failed

    # ==================== 實時行情 ====================
    
    async def fetch_quote_from_twse(self, symbol: str) -> Optional[Dict]:
        """從 TWSE API 獲取實時行情"""
        try:
            url = f"{self.twse_base_url}/api/v1/stockInfo"
            params = {"stockNo": symbol}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("msgArray"):
                            return self._parse_twse_quote(data["msgArray"][0], symbol)
        except Exception as e:
            logger.error(f"從 TWSE 獲取行情失敗 {symbol}: {e}")
        
        return None
    
    def _parse_twse_quote(self, data: Dict, symbol: str) -> Optional[Dict]:
        """解析 TWSE 行情資料"""
        try:
            return {
                "symbol": symbol,
                "name": data.get("n", ""),
                "price": Decimal(str(data.get("z", 0))),
                "change": Decimal(str(data.get("tlong", 0))),
                "change_percent": Decimal(str(data.get("it", 0))),
                "volume": int(data.get("t", 0)),
                "high": Decimal(str(data.get("h", 0))),
                "low": Decimal(str(data.get("l", 0))),
                "open": Decimal(str(data.get("o", 0))),
                "close": Decimal(str(data.get("z", 0))),
                "bid": Decimal(str(data.get("f", 0))),
                "ask": Decimal(str(data.get("a", 0))),
                "timestamp": datetime.now(),
            }
        except Exception as e:
            logger.error(f"解析 TWSE 行情失敗: {e}")
            return None
    
    # ==================== K線資料 ====================
    
    async def get_klines(
        self,
        symbol: str,
        period: str = "1d",
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[KlineDaily]:
        """獲取 K線資料"""
        try:
            stmt = select(KlineDaily).where(KlineDaily.symbol == symbol)
            
            if start_date:
                stmt = stmt.where(KlineDaily.date >= start_date)
            if end_date:
                stmt = stmt.where(KlineDaily.date <= end_date)
            
            stmt = stmt.order_by(desc(KlineDaily.date)).limit(limit)
            
            result = await self.db.execute(stmt)
            klines = result.scalars().all()
            return list(reversed(klines))
        
        except Exception as e:
            logger.error(f"獲取 K線失敗 {symbol}: {e}")
            return []
    
    async def save_kline(self, kline_data: Dict) -> Optional[KlineDaily]:
        """保存 K線資料"""
        try:
            stmt = select(KlineDaily).where(
                and_(
                    KlineDaily.symbol == kline_data["symbol"],
                    KlineDaily.date == kline_data["date"],
                )
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                for key, value in kline_data.items():
                    setattr(existing, key, value)
                kline = existing
            else:
                kline = KlineDaily(**kline_data)
                self.db.add(kline)
            
            await self.db.commit()
            return kline
        
        except Exception as e:
            logger.error(f"保存 K線失敗: {e}")
            await self.db.rollback()
            return None
    
    # ==================== 股票管理 ====================
    
    async def create_stock(self, stock_data: Dict) -> Optional[Stock]:
        """建立新股票"""
        try:
            existing = await self.get_stock_by_symbol(stock_data["symbol"])
            if existing:
                logger.warning(f"股票已存在: {stock_data['symbol']}")
                return existing
            
            stock = Stock(**stock_data)
            self.db.add(stock)
            await self.db.commit()
            await self.db.refresh(stock)
            return stock
        
        except Exception as e:
            logger.error(f"建立股票失敗: {e}")
            await self.db.rollback()
            return None
    
    async def update_stock(self, symbol: str, update_data: Dict) -> Optional[Stock]:
        """更新股票資訊"""
        try:
            stock = await self.get_stock_by_symbol(symbol)
            if not stock:
                return None
            
            for key, value in update_data.items():
                if value is not None:
                    setattr(stock, key, value)
            
            stock.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(stock)
            return stock
        
        except Exception as e:
            logger.error(f"更新股票失敗: {e}")
            await self.db.rollback()
            return None
    
    # ==================== 績效計算 ====================
    
    async def calculate_stock_performance(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[Dict]:
        """計算股票績效"""
        try:
            klines = await self.get_klines(symbol, start_date=start_date, end_date=end_date)
            
            if not klines or len(klines) < 2:
                return None
            
            first_kline = klines[0]
            last_kline = klines[-1]
            
            start_price = float(first_kline.open)
            end_price = float(last_kline.close)
            
            gain = end_price - start_price
            gain_percent = (gain / start_price * 100) if start_price > 0 else 0
            
            daily_returns = []
            for i in range(1, len(klines)):
                prev_close = float(klines[i-1].close)
                curr_close = float(klines[i].close)
                if prev_close > 0:
                    daily_returns.append((curr_close - prev_close) / prev_close)
            
            if daily_returns:
                import statistics
                volatility = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
            else:
                volatility = 0
            
            return {
                "symbol": symbol,
                "start_price": Decimal(str(start_price)),
                "end_price": Decimal(str(end_price)),
                "gain": Decimal(str(gain)),
                "gain_percent": Decimal(str(gain_percent)),
                "volatility": Decimal(str(volatility)),
                "trading_days": len(klines),
            }
        
        except Exception as e:
            logger.error(f"計算績效失敗 {symbol}: {e}")
            return None


async def get_stock_service(db: AsyncSession) -> StockService:
    """取得股票服務實例"""
    return StockService(db)


if __name__ == "__main__":
    print("✅ 股票服務模組已載入")