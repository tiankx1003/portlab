"""ETF 每日总份额（Tushare ``fund_share.fd_share``）原始数据模型。

落库份额**绝对值**（万份），供 PCF 联动「申赎→成份股压力」按 ``(symbol, trade_date)``
取连续两日算份额变动：``shares_change = fd_share[T] - fd_share[T-1]``（万份）。
与 ``raw_pcf_basket`` / ``raw_pcf_day_info`` 按 ``(fund_code, trading_day)`` 关联。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import TIMESTAMP, Date, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RawEtfShareDaily(Base):
    """ETF 每日总份额（万份）。"""

    __tablename__ = "raw_etf_share_daily"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    fd_share: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'tushare'")
    )
    updated_at: Mapped[date | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
