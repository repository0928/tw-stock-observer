"""
SQLAlchemy ORM 資料模型
Data Models for the Application
"""

from datetime import datetime, date
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Date,
    Text,
    Index,
    ForeignKey,
    BIGINT,
    DECIMAL,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base, BaseModel


# ==================== 使用者相關模型 ====================

class User(BaseModel):
    """使用者模型"""
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    avatar_url = Column(String(512))
    
    # 驗證狀態
    email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # 帳戶狀態
    status = Column(String(20), default="active")  # active, suspended, deleted
    
    # 設置
    language = Column(String(10), default="zh-TW")
    timezone = Column(String(50), default="Asia/Taipei")
    
    # 通知偏好
    notification_email = Column(Boolean, default=True)
    notification_push = Column(Boolean, default=True)
    
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # 關係
    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_created_at", "created_at"),
    )


# ==================== 股票相關模型 ====================

class Stock(BaseModel):
    """股票模型"""
    __tablename__ = "stocks"
    
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    english_name = Column(String(255))
    
    # 分類
    sector = Column(String(100), index=True)
    industry = Column(String(100))
    market_type = Column(String(10))  # tse, otc
    
    # 上市資訊
    listing_date = Column(String(10))
    
    # 公司資訊
    capital_stock = Column(BIGINT)
    shares = Column(BIGINT)
    website = Column(String(255))
    
    # 財務資料
    revenue = Column(BIGINT)
    net_income = Column(BIGINT)
    eps = Column(DECIMAL(10, 2))
    pe_ratio = Column(DECIMAL(10, 2))
    pb_ratio = Column(DECIMAL(10, 2))
    dividend_per_share = Column(DECIMAL(10, 2))
    dividend_yield = Column(DECIMAL(6, 2))
    
    # 狀態
    is_active = Column(Boolean, default=True)
    is_suspended = Column(Boolean, default=False)
    suspension_reason = Column(String(255))
    
    financial_data_updated_at = Column(DateTime(timezone=True))

    # 當日行情
    close_price = Column(DECIMAL(10, 2))
    open_price = Column(DECIMAL(10, 2))
    high_price = Column(DECIMAL(10, 2))
    low_price = Column(DECIMAL(10, 2))
    change_amount = Column(DECIMAL(10, 2))
    change_percent = Column(DECIMAL(8, 2))
    volume = Column(BIGINT)
    trade_date = Column(String(10))
    turnover_rate = Column(DECIMAL(8, 4))           # 週轉率(%)

    # 月營收
    revenue_yoy = Column(DECIMAL(8, 2))             # 月營收年增率(%)
    revenue_mom = Column(DECIMAL(8, 2))             # 月營收月增率(%)

    # 三大法人（單位：張）
    foreign_net_buy = Column(BIGINT)                # 外資買賣超
    investment_trust_net_buy = Column(BIGINT)       # 投信買賣超
    dealer_net_buy = Column(BIGINT)                 # 自營商買賣超

    # 財報（季更新）
    gross_margin = Column(DECIMAL(8, 2))            # 毛利率(%)
    operating_margin = Column(DECIMAL(8, 2))        # 營業利益率(%)
    net_margin = Column(DECIMAL(8, 2))              # 淨利率(%)
    roe = Column(DECIMAL(8, 2))                     # 股東權益報酬率(%)
    roa = Column(DECIMAL(8, 2))                     # 資產報酬率(%)
    debt_ratio = Column(DECIMAL(8, 2))              # 負債比率(%)

    # 融資/融券
    margin_long = Column(Integer)                   # 融資餘額（張）
    margin_short = Column(Integer)                  # 融券餘額（張）

    # 注意/處置/ETF 標記
    is_attention = Column(Boolean, default=False)   # 注意股票
    is_disposed = Column(Boolean, default=False)    # 處置股票
    is_etf = Column(Boolean, default=False)         # ETF（代號 00 開頭）

    # 股利
    ex_dividend_date = Column(Date)                 # 除息日
    cash_dividend = Column(DECIMAL(8, 4))           # 現金股利（元/股）

    # 關係
    klines = relationship("KlineDaily", back_populates="stock", cascade="all, delete-orphan")
    announcements = relationship("StockAnnouncement", back_populates="stock",
                                 cascade="all, delete-orphan", order_by="StockAnnouncement.announce_date.desc()")
    
    __table_args__ = (
        Index("idx_stocks_symbol", "symbol"),
        Index("idx_stocks_sector", "sector"),
        Index("idx_stocks_updated_at", "updated_at"),
    )


class KlineDaily(BaseModel):
    """日 K 線模型"""
    __tablename__ = "klines_daily"
    
    symbol = Column(String(10), nullable=False, index=True)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id"), nullable=False)
    
    # 時間
    date = Column(String(10), nullable=False)
    
    # OHLC
    open = Column(DECIMAL(12, 2), nullable=False)
    high = Column(DECIMAL(12, 2), nullable=False)
    low = Column(DECIMAL(12, 2), nullable=False)
    close = Column(DECIMAL(12, 2), nullable=False)
    
    # 成交資訊
    volume = Column(BIGINT, nullable=False)
    amount = Column(BIGINT, nullable=False)
    
    # 衍生欄位
    change = Column(DECIMAL(12, 2))
    change_percent = Column(DECIMAL(6, 2))
    
    # 技術指標
    sma_20 = Column(DECIMAL(12, 2))
    sma_50 = Column(DECIMAL(12, 2))
    sma_200 = Column(DECIMAL(12, 2))
    rsi_14 = Column(DECIMAL(6, 2))
    macd = Column(DECIMAL(12, 4))
    macd_signal = Column(DECIMAL(12, 4))
    macd_histogram = Column(DECIMAL(12, 4))
    
    # 關係
    stock = relationship("Stock", back_populates="klines")
    
    __table_args__ = (
        Index("idx_klines_daily_symbol_date", "symbol", "date"),
        Index("idx_klines_daily_stock_id", "stock_id"),
        Index("idx_klines_daily_date", "date"),
    )


# ==================== 投資組合相關模型 ====================

class Portfolio(BaseModel):
    """投資組合模型"""
    __tablename__ = "portfolios"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 基本資訊
    name = Column(String(255), nullable=False)
    description = Column(Text)
    visibility = Column(String(20), default="private")  # private, public, shared
    
    # 財務資訊
    budget = Column(DECIMAL(15, 2))
    current_value = Column(DECIMAL(15, 2), default=0)
    cost_basis = Column(DECIMAL(15, 2), default=0)
    gain = Column(DECIMAL(15, 2), default=0)
    gain_percent = Column(DECIMAL(8, 2), default=0)
    
    # 目標
    target_return = Column(DECIMAL(8, 2))
    actual_return = Column(DECIMAL(8, 2))
    
    # 風險指標
    volatility = Column(DECIMAL(6, 2))
    sharpe_ratio = Column(DECIMAL(6, 2))
    beta = Column(DECIMAL(6, 2))
    max_drawdown = Column(DECIMAL(8, 2))
    
    # 狀態
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)
    
    # 關係
    user = relationship("User", back_populates="portfolios")
    holdings = relationship("PortfolioHolding", back_populates="portfolio", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_portfolios_user_id", "user_id"),
        Index("idx_portfolios_created_at", "created_at"),
        Index("idx_portfolios_is_active", "is_active"),
    )


class PortfolioHolding(BaseModel):
    """投資組合持倉模型"""
    __tablename__ = "portfolio_holdings"
    
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id"), nullable=False)
    
    symbol = Column(String(10), nullable=False)
    
    # 持倉資訊
    quantity = Column(Integer, nullable=False)
    purchase_price = Column(DECIMAL(12, 2), nullable=False)
    purchase_date = Column(String(10), nullable=False)
    
    # 成本與收益
    cost_basis = Column(DECIMAL(15, 2), nullable=False)
    current_price = Column(DECIMAL(12, 2))
    current_value = Column(DECIMAL(15, 2))
    gain = Column(DECIMAL(15, 2))
    gain_percent = Column(DECIMAL(8, 2))
    
    # 股利
    dividends_received = Column(DECIMAL(15, 2), default=0)
    
    # 狀態
    status = Column(String(20), default="active")  # active, sold, disposed
    
    sold_at = Column(DateTime(timezone=True), nullable=True)
    
    # 關係
    portfolio = relationship("Portfolio", back_populates="holdings")
    
    __table_args__ = (
        Index("idx_portfolio_holdings_portfolio_id", "portfolio_id"),
        Index("idx_portfolio_holdings_stock_id", "stock_id"),
        Index("idx_portfolio_holdings_created_at", "created_at"),
    )


# ==================== 交易相關模型 ====================

class Transaction(BaseModel):
    """交易記錄模型"""
    __tablename__ = "transactions"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False)
    holding_id = Column(UUID(as_uuid=True), nullable=True)
    
    # 交易資訊
    symbol = Column(String(10), nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False)  # buy, sell, dividend
    quantity = Column(Integer)
    price = Column(DECIMAL(12, 2))
    amount = Column(DECIMAL(15, 2))
    fee = Column(DECIMAL(12, 2), default=0)
    tax = Column(DECIMAL(12, 2), default=0)
    
    # 執行資訊
    status = Column(String(20), default="completed")  # pending, completed, cancelled, failed
    execution_date = Column(DateTime(timezone=True))
    
    # 備註
    notes = Column(Text)
    
    # 關係
    user = relationship("User", back_populates="transactions")
    
    __table_args__ = (
        Index("idx_transactions_user_id", "user_id"),
        Index("idx_transactions_portfolio_id", "portfolio_id"),
        Index("idx_transactions_symbol", "symbol"),
        Index("idx_transactions_execution_date", "execution_date"),
        Index("idx_transactions_created_at", "created_at"),
    )


# ==================== 告警相關模型 ====================

class Alert(BaseModel):
    """告警規則模型"""
    __tablename__ = "alerts"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=True)
    
    # 告警配置
    symbol = Column(String(10), index=True)
    alert_type = Column(String(50), nullable=False)  # price, performance, technical, risk
    condition = Column(JSONB, nullable=False)
    
    # 觸發狀態
    is_active = Column(Boolean, default=True)
    is_triggered = Column(Boolean, default=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    
    # 通知方式
    notify_email = Column(Boolean, default=True)
    notify_push = Column(Boolean, default=False)
    
    __table_args__ = (
        Index("idx_alerts_user_id", "user_id"),
        Index("idx_alerts_portfolio_id", "portfolio_id"),
        Index("idx_alerts_symbol", "symbol"),
        Index("idx_alerts_is_active", "is_active"),
        Index("idx_alerts_created_at", "created_at"),
    )


class StockAnnouncement(BaseModel):
    """重大訊息模型"""
    __tablename__ = "stock_announcements"

    symbol = Column(String(10), nullable=False, index=True)
    announce_date = Column(Date, nullable=False)
    subject = Column(Text)
    content = Column(Text)
    source = Column(String(10))   # 'TWSE' or 'TPEx'

    # 關係
    stock = relationship("Stock", back_populates="announcements",
                         primaryjoin="StockAnnouncement.symbol == foreign(Stock.symbol)",
                         foreign_keys="[StockAnnouncement.symbol]")

    __table_args__ = (
        Index("idx_ann_symbol_date", "symbol", "announce_date"),
    )


if __name__ == "__main__":
    print("✅ 所有模型已定義")
    print(f"已定義 {len(Base.metadata.tables)} 個表")
