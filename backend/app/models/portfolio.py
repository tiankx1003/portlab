"""组合回测（022）持久化模型。

- ``CalcPortfolioNav``：逐日组合净值（归一化起点=1）+ 回撤。
- ``ResultPortfolioSummary``：汇总（年化收益/波动/夏普/回撤 + 权重/再平衡等参数）。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CalcPortfolioNav(Base):
    """组合回测逐日净值。"""

    __tablename__ = "calc_portfolio_nav"

    task_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=1)  # 归一化净值
    drawdown: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)


class ResultPortfolioSummary(Base):
    """组合回测汇总指标。"""

    __tablename__ = "result_portfolio_summary"

    task_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    symbols: Mapped[str] = mapped_column(String(255), nullable=False)  # 逗号分隔
    mode: Mapped[str] = mapped_column(String(8), nullable=False)  # fixed/frontier
    weights: Mapped[str] = mapped_column(String(255), nullable=False)  # 逗号分隔
    rebalance: Mapped[str] = mapped_column(String(8), nullable=False)  # monthly/quarterly/none
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    annual_return: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)  # %
    annual_volatility: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)  # %
    sharpe: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)  # %
    total_return: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)  # %
    rf: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)  # 无风险利率
    allow_short: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
