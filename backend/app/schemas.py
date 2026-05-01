"""
Pydantic 資料驗證 Schema
Data Validation and Serialization Models
"""

from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ==================== 股票 Schema ====================

class StockBase(BaseModel):
    """股票基礎 Schema"""
    symbol: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1, max_length=255)
    english_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_type: Optional[str] = None


class StockCreate(StockBase):
    """建立股票 Schema"""
    pass


class StockUpdate(BaseModel):
    """更新股票 Schema"""
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    eps: Optional[Decimal] = None
    pe_ratio: Optional[Decimal] = None
    pb_ratio: Optional[Decimal] = None


class StockResponse(StockBase):
    """股票回應 Schema"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    is_active: bool
    is_suspended: bool
    eps: Optional[Decimal] = None
    pe_ratio: Optional[Decimal] = None
    pb_ratio: Optional[Decimal] = None
    close_price: Optional[Decimal] = None
    open_price: Optional[Decimal] = None
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    change_amount: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    volume: Optional[int] = None
    trade_date: Optional[str] = None
    turnover_rate: Optional[Decimal] = None

    # 月營收
    revenue_note: Optional[str] = None
    revenue_yoy: Optional[Decimal] = None
    revenue_mom: Optional[Decimal] = None

    # 三大法人
    foreign_net_buy: Optional[int] = None
    investment_trust_net_buy: Optional[int] = None
    dealer_net_buy: Optional[int] = None

    # 財報
    gross_margin: Optional[Decimal] = None
    operating_margin: Optional[Decimal] = None
    net_margin: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    roa: Optional[Decimal] = None
    debt_ratio: Optional[Decimal] = None

    # 融資/融券
    margin_long: Optional[int] = None
    margin_short: Optional[int] = None

    # 標記
    is_attention: Optional[bool] = None
    is_disposed: Optional[bool] = None
    is_etf: Optional[bool] = None

    # 股利
    ex_dividend_date: Optional[date] = None
    cash_dividend: Optional[Decimal] = None

    class Config:
        from_attributes = True


# ==================== 重大訊息 Schema ====================

class AnnouncementOut(BaseModel):
    """重大訊息回應 Schema"""
    id: int
    symbol: str
    announce_date: date
    subject: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class StockQuoteResponse(BaseModel):
    """股票行情回應 Schema"""
    symbol: str
    name: str
    price: Decimal
    change: Decimal
    change_percent: Decimal
    volume: int
    high: Decimal
    low: Decimal
    open: Decimal
    close: Decimal
    timestamp: datetime
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


# ==================== K線 Schema ====================

class KlineDailyBase(BaseModel):
    """日 K 線基礎 Schema"""
    symbol: str
    date: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: int


class KlineDailyCreate(KlineDailyBase):
    """建立日 K 線 Schema"""
    stock_id: UUID


class KlineDailyResponse(KlineDailyBase):
    """日 K 線回應 Schema"""
    id: UUID
    change: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    sma_20: Optional[Decimal] = None
    sma_50: Optional[Decimal] = None
    sma_200: Optional[Decimal] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== 使用者 Schema ====================

class UserBase(BaseModel):
    """使用者基礎 Schema"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    """建立使用者 Schema"""
    password: str = Field(..., min_length=8)
    
    @field_validator("password")
    def password_strong(cls, v):
        """驗證密碼強度"""
        if not any(c.isupper() for c in v):
            raise ValueError("密碼必須包含至少一個大寫字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密碼必須包含至少一個數字")
        return v


class UserUpdate(BaseModel):
    """更新使用者 Schema"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None


class UserResponse(UserBase):
    """使用者回應 Schema"""
    id: UUID
    email_verified: bool
    status: str
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ==================== 投資組合 Schema ====================

class PortfolioBase(BaseModel):
    """投資組合基礎 Schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    visibility: str = "private"
    budget: Optional[Decimal] = None
    target_return: Optional[Decimal] = None


class PortfolioCreate(PortfolioBase):
    """建立投資組合 Schema"""
    pass


class PortfolioUpdate(BaseModel):
    """更新投資組合 Schema"""
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    budget: Optional[Decimal] = None
    target_return: Optional[Decimal] = None


class PortfolioHoldingResponse(BaseModel):
    """投資組合持倉回應 Schema"""
    id: UUID
    symbol: str
    quantity: int
    purchase_price: Decimal
    purchase_date: str
    cost_basis: Decimal
    current_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    gain: Optional[Decimal] = None
    gain_percent: Optional[Decimal] = None
    status: str
    
    class Config:
        from_attributes = True


class PortfolioResponse(PortfolioBase):
    """投資組合回應 Schema"""
    id: UUID
    user_id: UUID
    current_value: Decimal
    cost_basis: Decimal
    gain: Decimal
    gain_percent: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
    holdings: List[PortfolioHoldingResponse] = []
    
    class Config:
        from_attributes = True


# ==================== 持倉 Schema ====================

class PortfolioHoldingBase(BaseModel):
    """持倉基礎 Schema"""
    symbol: str = Field(..., max_length=10)
    quantity: int = Field(..., gt=0)
    purchase_price: Decimal = Field(..., gt=0)
    purchase_date: str


class PortfolioHoldingCreate(PortfolioHoldingBase):
    """建立持倉 Schema"""
    pass


# ==================== 交易 Schema ====================

class TransactionBase(BaseModel):
    """交易基礎 Schema"""
    symbol: str = Field(..., max_length=10)
    transaction_type: str  # buy, sell, dividend
    quantity: Optional[int] = None
    price: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    fee: Decimal = 0
    tax: Decimal = 0


class TransactionCreate(TransactionBase):
    """建立交易 Schema"""
    pass


class TransactionResponse(TransactionBase):
    """交易回應 Schema"""
    id: UUID
    portfolio_id: UUID
    status: str
    execution_date: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== 告警 Schema ====================

class AlertBase(BaseModel):
    """告警基礎 Schema"""
    symbol: Optional[str] = None
    alert_type: str
    condition: dict
    is_active: bool = True
    notify_email: bool = True
    notify_push: bool = False


class AlertCreate(AlertBase):
    """建立告警 Schema"""
    pass


class AlertResponse(AlertBase):
    """告警回應 Schema"""
    id: UUID
    user_id: UUID
    is_triggered: bool
    last_triggered_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== 分析結果 Schema ====================

class TechnicalIndicatorsResponse(BaseModel):
    """技術指標回應 Schema"""
    symbol: str
    period: str
    timestamp: datetime
    sma_20: Optional[Decimal] = None
    sma_50: Optional[Decimal] = None
    sma_200: Optional[Decimal] = None
    rsi_14: Optional[Decimal] = None
    macd: Optional[Decimal] = None
    macd_signal: Optional[Decimal] = None
    macd_histogram: Optional[Decimal] = None


class PortfolioPerformanceResponse(BaseModel):
    """投資組合績效回應 Schema"""
    portfolio_id: UUID
    total_cost: Decimal
    total_value: Decimal
    total_gain: Decimal
    gain_percent: Decimal
    volatility: Optional[Decimal] = None
    sharpe_ratio: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None


# ==================== API 通用 Schema ====================

class ErrorResponse(BaseModel):
    """錯誤回應 Schema"""
    detail: str
    status_code: int
    error_code: Optional[str] = None


class SuccessResponse(BaseModel):
    """成功回應 Schema"""
    message: str
    data: Optional[dict] = None


class PaginationResponse(BaseModel):
    """分頁回應 Schema"""
    items: List[dict]
    total: int
    page: int
    per_page: int
    total_pages: int


if __name__ == "__main__":
    print("✅ 所有 Schema 已定義")
