"""ETF 申购赎回清单 (PCF) 原始数据模型（多源统一宽表）。

- ``RawPcfBasket``：成份券篮子。各家基金公司字段取并集，缺失列 NULL，
  用 ``source`` 列区分来源（fsfund / huatai_pb / ...）。加新公司只加行，
  仅当出现全新字段时才需 ALTER 加列。
- ``RawPcfDayInfo``：基金级 PCF 头部（净值/现金差额/申赎上限等）。华宝 fsfund
  接口不返回头部信息，故该表对 fsfund 无行；华泰柏瑞等有头部的源写入此表。

注意：部分字段名两家语义略有差异（如 ``tdje``：华宝为"退订金额"、华泰为"替代金额"），
统一存同一列，含义随 ``source``，详见各列 COMMENT。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Date,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RawPcfBasket(Base):
    """ETF PCF 成份券篮子（每只成份股一行，多源统一宽表）。"""

    __tablename__ = "raw_pcf_basket"

    # 主键：来源 + 基金 + 交易日 + 成份股代码（三维前缀覆盖按日查询）
    source: Mapped[str] = mapped_column(String(16), primary_key=True)
    fund_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trading_day: Mapped[date] = mapped_column(Date, primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(16), primary_key=True)

    # 基金信息
    fund_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fund_codes: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fund_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scid: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # 成份股信息
    stock_short: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gpsc: Mapped[str | None] = mapped_column(String(16), nullable=True)
    stock_codesrc: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # 数量金额
    number: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    tdje: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    sgtdje: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    shtdje: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # 比例
    yjbl: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    sg_yjbl: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    sh_zjbl: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    discount_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    premium_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    # 标志
    tdbz: Mapped[str | None] = mapped_column(String(16), nullable=True)
    buyorsell: Mapped[str | None] = mapped_column(String(8), nullable=True)
    mmbz: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # 华宝独有
    record_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reserved: Mapped[str | None] = mapped_column(String(64), nullable=True)
    procflag: Mapped[str | None] = mapped_column(String(16), nullable=True)

    updated_at: Mapped[date | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class RawPcfDayInfo(Base):
    """ETF PCF 基金级头部信息（每个 基金×日期 一行；华宝 fsfund 无 → 不入）。"""

    __tablename__ = "raw_pcf_day_info"

    source: Mapped[str] = mapped_column(String(16), primary_key=True)
    fund_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trading_day: Mapped[date] = mapped_column(Date, primary_key=True)

    fund_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nav: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    cash_component: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    estimate_cash_component: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    cash_dividend: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    creation_redemption_unit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    creation_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    redemption_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_cash_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    record_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    underlying_index: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nav_per_cu: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    pbuid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    investor_account_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    creation_redemption: Mapped[str | None] = mapped_column(String(16), nullable=True)
    creation_redemption_mechanism: Mapped[str | None] = mapped_column(String(32), nullable=True)
    publish: Mapped[str | None] = mapped_column(String(16), nullable=True)
    all_cash_flag_str: Mapped[str | None] = mapped_column(String(32), nullable=True)

    updated_at: Mapped[date | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
